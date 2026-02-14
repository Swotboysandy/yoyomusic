"""
YoYoMusic Load Test — 100 users × 10 rooms × 60 seconds

Validates:
  - Rate limiting (search: 10/min per user, queue: 5/30s per room)
  - Extraction concurrency (Semaphore(2) + Redis lock dedup)
  - WebSocket stability under load
  - Response times and error rates
  - Server health (CPU, memory, WS connections)

Usage:
    venv\\Scripts\\python test_load.py

Requires: httpx, websockets (already in venv)
"""

import asyncio
import time
import random
import statistics
import traceback
from dataclasses import dataclass, field

import httpx

# ─── Configuration ───────────────────────────────────────────
BASE_URL = "http://127.0.0.1:8000"
API = f"{BASE_URL}/api/v1"
WS_URL = "ws://127.0.0.1:8000/api/v1/ws"

NUM_USERS = 100
NUM_ROOMS = 10
TEST_DURATION = 60  # seconds
RAMP_UP_SECONDS = 5  # stagger user starts over this period

SEARCH_QUERIES = [
    "never gonna give you up", "bohemian rhapsody", "hotel california",
    "stairway to heaven", "imagine john lennon", "billie jean",
    "smells like teen spirit", "hey jude", "like a rolling stone",
    "sweet child o mine", "yesterday beatles", "let it be",
    "purple rain", "superstition stevie wonder", "take on me",
]

# Same video_id used by multiple users to test dedup
SHARED_VIDEO_IDS = ["dQw4w9WgXcQ", "fJ9rUzIMcZQ", "bx1Bh8ZvH84"]


# ─── Metrics Collector ───────────────────────────────────────
@dataclass
class Metrics:
    total_requests: int = 0
    success_count: int = 0
    error_429: int = 0
    error_5xx: int = 0
    error_other: int = 0
    ws_connected: int = 0
    ws_failed: int = 0
    ws_messages_received: int = 0
    response_times: list = field(default_factory=list)
    search_times: list = field(default_factory=list)
    queue_add_times: list = field(default_factory=list)
    extraction_times: list = field(default_factory=list)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def record(self, category: str, status: int, elapsed: float):
        async with self._lock:
            self.total_requests += 1
            self.response_times.append(elapsed)

            if 200 <= status < 300:
                self.success_count += 1
            elif status == 429:
                self.error_429 += 1
            elif status >= 500:
                self.error_5xx += 1
            else:
                self.error_other += 1

            if category == "search":
                self.search_times.append(elapsed)
            elif category == "queue_add":
                self.queue_add_times.append(elapsed)
            elif category == "extract":
                self.extraction_times.append(elapsed)


metrics = Metrics()


# ─── Auth Helper ─────────────────────────────────────────────
async def get_token(client: httpx.AsyncClient) -> str:
    resp = await client.get(f"{API}/auth/dev-token")
    resp.raise_for_status()
    return resp.json()["access_token"]


# ─── Room Creation ───────────────────────────────────────────
async def create_rooms(client: httpx.AsyncClient, token: str, n: int) -> list[str]:
    headers = {"Authorization": f"Bearer {token}"}
    slugs = []
    for i in range(n):
        resp = await client.post(
            f"{API}/rooms/",
            json={"name": f"LoadTest Room {i+1}"},
            headers=headers,
        )
        if resp.status_code == 200:
            slugs.append(resp.json()["id"])
        else:
            print(f"  ⚠ Room creation failed: {resp.status_code}")
    return slugs


# ─── Single User Simulation ─────────────────────────────────
async def simulate_user(
    user_id: int,
    room_slug: str,
    stop_event: asyncio.Event,
):
    """Simulate one user: get token, join room, WS connect, search, add songs."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Get auth token
        try:
            token = await get_token(client)
        except Exception as e:
            print(f"  User {user_id}: auth failed: {e}")
            return
        headers = {"Authorization": f"Bearer {token}"}

        # Join room
        try:
            resp = await client.post(
                f"{API}/rooms/{room_slug}/join",
                json={"username": f"user_{user_id}"},
                headers=headers,
            )
        except Exception:
            pass

        # Start WebSocket listener in background
        ws_task = asyncio.create_task(
            ws_listener(user_id, room_slug, token, stop_event)
        )

        # Action loop
        action_count = 0
        while not stop_event.is_set():
            try:
                action = random.choice(["search", "search", "queue_add", "get_queue"])

                if action == "search":
                    query = random.choice(SEARCH_QUERIES)
                    start = time.monotonic()
                    resp = await client.get(
                        f"{API}/search/",
                        params={"q": query},
                        headers=headers,
                    )
                    elapsed = time.monotonic() - start
                    await metrics.record("search", resp.status_code, elapsed)

                elif action == "queue_add":
                    # Alternate between query-based and direct video_id
                    if random.random() < 0.3:
                        # Direct add with shared video_id (tests dedup)
                        vid = random.choice(SHARED_VIDEO_IDS)
                        body = {"yt_id": vid, "title": f"Shared Song {vid}", "duration": 200000}
                    else:
                        body = {"query": random.choice(SEARCH_QUERIES)}

                    start = time.monotonic()
                    resp = await client.post(
                        f"{API}/rooms/{room_slug}/queue",
                        json=body,
                        headers=headers,
                    )
                    elapsed = time.monotonic() - start
                    await metrics.record("queue_add", resp.status_code, elapsed)

                elif action == "get_queue":
                    start = time.monotonic()
                    resp = await client.get(
                        f"{API}/rooms/{room_slug}/queue",
                        headers=headers,
                    )
                    elapsed = time.monotonic() - start
                    await metrics.record("get_queue", resp.status_code, elapsed)

                action_count += 1

            except httpx.ReadTimeout:
                async with metrics._lock:
                    metrics.total_requests += 1
                    metrics.error_other += 1
            except Exception as e:
                if not stop_event.is_set():
                    async with metrics._lock:
                        metrics.total_requests += 1
                        metrics.error_other += 1

            # Random delay between actions (1-5s)
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=random.uniform(1.0, 5.0))
                break
            except asyncio.TimeoutError:
                pass

        # Clean up WS
        ws_task.cancel()
        try:
            await ws_task
        except asyncio.CancelledError:
            pass


# ─── WebSocket Listener ─────────────────────────────────────
async def ws_listener(
    user_id: int,
    room_slug: str,
    token: str,
    stop_event: asyncio.Event,
):
    """Maintain WebSocket connection, count received messages."""
    import websockets

    url = f"{WS_URL}/{room_slug}?token={token}"
    try:
        async with websockets.connect(url) as ws:
            async with metrics._lock:
                metrics.ws_connected += 1

            while not stop_event.is_set():
                try:
                    await asyncio.wait_for(ws.recv(), timeout=2.0)
                    async with metrics._lock:
                        metrics.ws_messages_received += 1
                except asyncio.TimeoutError:
                    continue
                except websockets.exceptions.ConnectionClosed:
                    break
    except Exception:
        async with metrics._lock:
            metrics.ws_failed += 1


# ─── Health Poller ───────────────────────────────────────────
async def poll_health(stop_event: asyncio.Event):
    """Poll /health every 5s and print stats."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        while not stop_event.is_set():
            try:
                resp = await client.get(f"{BASE_URL}/health")
                data = resp.json()
                ws = data.get("websockets", {})
                print(
                    f"  📊 Health: rooms={ws.get('rooms', '?')} "
                    f"ws_conns={ws.get('total_connections', '?')} "
                    f"subs={ws.get('subscriptions', '?')} | "
                    f"Reqs: {metrics.total_requests} "
                    f"✅{metrics.success_count} "
                    f"🚫{metrics.error_429} "
                    f"💥{metrics.error_5xx}"
                )
            except Exception as e:
                print(f"  ⚠ Health poll failed: {e}")

            try:
                await asyncio.wait_for(stop_event.wait(), timeout=5.0)
                break
            except asyncio.TimeoutError:
                pass


# ─── Extraction Dedup Test ───────────────────────────────────
async def test_extraction_dedup(token: str):
    """
    Burst test: 20 simultaneous requests for the SAME video_id.
    Should result in only 1 actual extraction (Redis lock).
    """
    print("\n🔬 Extraction Dedup Test: 20 concurrent requests for same video...")
    vid = SHARED_VIDEO_IDS[0]

    async def fetch_stream(client, headers):
        start = time.monotonic()
        resp = await client.get(
            f"{API}/search/stream/{vid}",
            headers=headers,
        )
        elapsed = time.monotonic() - start
        return resp.status_code, elapsed

    async with httpx.AsyncClient(timeout=30.0) as client:
        headers = {"Authorization": f"Bearer {token}"}
        tasks = [fetch_stream(client, headers) for _ in range(20)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    successes = [r for r in results if not isinstance(r, Exception) and r[0] == 200]
    errors = [r for r in results if isinstance(r, Exception) or (not isinstance(r, Exception) and r[0] >= 400)]
    times = [r[1] for r in results if not isinstance(r, Exception)]

    print(f"  ✅ Success: {len(successes)}/20")
    print(f"  ❌ Errors: {len(errors)}/20")
    if times:
        print(f"  ⏱ Fastest: {min(times):.1f}s | Slowest: {max(times):.1f}s")
    print(f"  → If slowest ≈ fastest, lock dedup is working (single extraction, rest waited)")


# ─── Main ────────────────────────────────────────────────────
async def main():
    print("=" * 60)
    print("  YoYoMusic Load Test")
    print(f"  {NUM_USERS} users × {NUM_ROOMS} rooms × {TEST_DURATION}s")
    print("=" * 60)

    # Pre-flight: check server is up
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            resp = await client.get(f"{BASE_URL}/health")
            resp.raise_for_status()
            print("✅ Server is running")
        except Exception as e:
            print(f"❌ Server not reachable: {e}")
            print("   Start the backend first: venv\\Scripts\\python -m uvicorn app.main:app --port 8000")
            return

    # Get admin token
    async with httpx.AsyncClient(timeout=10.0) as client:
        token = await get_token(client)
        headers = {"Authorization": f"Bearer {token}"}

        # Create test rooms
        print(f"\n📦 Creating {NUM_ROOMS} rooms...")
        room_slugs = await create_rooms(client, token, NUM_ROOMS)
        print(f"   Created: {room_slugs}")

        if len(room_slugs) < NUM_ROOMS:
            print(f"   ⚠ Only {len(room_slugs)} rooms created, continuing...")

    # Run extraction dedup test first (before main load)
    await test_extraction_dedup(token)

    # Main load test
    print(f"\n🚀 Starting load test ({TEST_DURATION}s)...")
    stop_event = asyncio.Event()
    health_task = asyncio.create_task(poll_health(stop_event))

    # Stagger user starts
    user_tasks = []
    for i in range(NUM_USERS):
        room = room_slugs[i % len(room_slugs)]
        delay = (i / NUM_USERS) * RAMP_UP_SECONDS
        task = asyncio.create_task(delayed_start(i, room, stop_event, delay))
        user_tasks.append(task)

    # Wait for test duration
    await asyncio.sleep(TEST_DURATION)
    print("\n⏹ Stopping test...")
    stop_event.set()

    # Wait for all users to finish (with timeout)
    done, pending = await asyncio.wait(user_tasks, timeout=15.0)
    for t in pending:
        t.cancel()
    health_task.cancel()

    # Final health check
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            resp = await client.get(f"{BASE_URL}/health")
            final_health = resp.json()
        except Exception:
            final_health = {"status": "unreachable"}

    # Print Report
    print_report(final_health)


async def delayed_start(user_id, room_slug, stop_event, delay):
    await asyncio.sleep(delay)
    if not stop_event.is_set():
        await simulate_user(user_id, room_slug, stop_event)


def print_report(final_health):
    print("\n" + "=" * 60)
    print("  📊 LOAD TEST REPORT")
    print("=" * 60)

    m = metrics
    print(f"\n  Total Requests:       {m.total_requests}")
    print(f"  ✅ Success (2xx):      {m.success_count} ({pct(m.success_count, m.total_requests)})")
    print(f"  🚫 Rate Limited (429): {m.error_429} ({pct(m.error_429, m.total_requests)})")
    print(f"  💥 Server Error (5xx): {m.error_5xx} ({pct(m.error_5xx, m.total_requests)})")
    print(f"  ⚠ Other Errors:       {m.error_other} ({pct(m.error_other, m.total_requests)})")

    if m.response_times:
        print(f"\n  Response Times:")
        print(f"    Avg:  {statistics.mean(m.response_times):.2f}s")
        print(f"    P50:  {statistics.median(m.response_times):.2f}s")
        p95 = sorted(m.response_times)[int(len(m.response_times) * 0.95)]
        p99 = sorted(m.response_times)[int(len(m.response_times) * 0.99)]
        print(f"    P95:  {p95:.2f}s")
        print(f"    P99:  {p99:.2f}s")
        print(f"    Max:  {max(m.response_times):.2f}s")

    if m.search_times:
        print(f"\n  Search Times:     avg={statistics.mean(m.search_times):.2f}s  max={max(m.search_times):.2f}s  n={len(m.search_times)}")
    if m.queue_add_times:
        print(f"  Queue Add Times:  avg={statistics.mean(m.queue_add_times):.2f}s  max={max(m.queue_add_times):.2f}s  n={len(m.queue_add_times)}")

    print(f"\n  WebSocket Stats:")
    print(f"    Connected:     {m.ws_connected}")
    print(f"    Failed:        {m.ws_failed}")
    print(f"    Msgs Received: {m.ws_messages_received}")

    print(f"\n  Final Health:")
    ws = final_health.get("websockets", {})
    print(f"    Status:         {final_health.get('status', '?')}")
    print(f"    Active Rooms:   {ws.get('rooms', '?')}")
    print(f"    WS Connections: {ws.get('total_connections', '?')}")
    print(f"    Subscriptions:  {ws.get('subscriptions', '?')}")

    # Verdict
    print("\n" + "-" * 60)
    if m.error_5xx == 0 and final_health.get("status") == "ok":
        print("  ✅ PASS — No server crashes, system stable")
    elif m.error_5xx > 0:
        print(f"  ❌ FAIL — {m.error_5xx} server errors detected")
    else:
        print("  ⚠ WARN — Server health uncertain")

    if m.error_429 > 0:
        print(f"  ✅ Rate limiting active ({m.error_429} requests throttled)")
    else:
        print("  ⚠ No 429s observed — rate limits may not be triggering")

    print("=" * 60)


def pct(part, total):
    if total == 0:
        return "0%"
    return f"{(part / total) * 100:.1f}%"


if __name__ == "__main__":
    asyncio.run(main())
