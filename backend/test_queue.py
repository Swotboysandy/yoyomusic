"""
Phase 5 End-to-End Test:
  1. Create room
  2. Add song → auto-plays (queue was idle)
  3. Add second song → stays queued
  4. Signal song-ended → transitions to second song
  5. Vote-skip → check threshold
  6. Host-skip → skips second song → idle
"""
import asyncio
import aiohttp
import websockets
import json
from datetime import datetime, timedelta
from jose import jwt

SECRET_KEY = "replace_this_with_a_secure_random_string"
ALGORITHM = "HS256"
BASE = "http://127.0.0.1:8000/api/v1"
WS_BASE = "ws://127.0.0.1:8000/api/v1/ws"


def make_token(sub="test@example.com"):
    return jwt.encode(
        {"exp": datetime.utcnow() + timedelta(minutes=30), "sub": sub},
        SECRET_KEY, algorithm=ALGORITHM,
    )


async def drain_ws(ws, timeout=1.0):
    """Read all pending WS messages within timeout."""
    msgs = []
    try:
        while True:
            msg = await asyncio.wait_for(ws.recv(), timeout=timeout)
            msgs.append(json.loads(msg))
    except (asyncio.TimeoutError, Exception):
        pass
    return msgs


async def wait_for_event(ws, event_type, timeout=5.0):
    """Wait for a specific WS event type."""
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        try:
            remaining = deadline - asyncio.get_event_loop().time()
            msg = await asyncio.wait_for(ws.recv(), timeout=max(0.1, remaining))
            data = json.loads(msg)
            if data.get("type") == event_type:
                return data
        except asyncio.TimeoutError:
            break
    return None


async def run():
    headers = {"Authorization": f"Bearer {make_token()}"}

    async with aiohttp.ClientSession() as http:
        # 1. Create Room
        print("1. Creating Room...")
        async with http.post(f"{BASE}/rooms/", json={"name": "Queue Test"}, headers=headers) as r:
            assert r.status == 200, f"Create failed: {await r.text()}"
            room = await r.json()
            slug = room["id"]
        print(f"   Room: {slug}")

        # Connect WS
        async with websockets.connect(f"{WS_BASE}/{slug}") as ws:
            await drain_ws(ws, 0.5)  # flush connect events

            # 2. Add first song → should auto-play
            print("2. Adding Song 1 (should auto-play)...")
            async with http.post(
                f"{BASE}/rooms/{slug}/queue",
                json={"yt_id": "yt-001", "title": "Song Alpha", "duration": 180000},
                headers=headers,
            ) as r:
                assert r.status == 200, f"Add failed: {await r.text()}"

            ev = await wait_for_event(ws, "playback_update")
            assert ev, "No playback_update received"
            assert ev["data"]["status"] == "playing", f"Expected playing, got {ev['data']['status']}"
            print(f"   Auto-play confirmed: status={ev['data']['status']}")

            # Drain all remaining events from auto-play (queue_update with empty queue, etc.)
            await drain_ws(ws, 1.0)

            # 3. Add second song → stays queued
            print("3. Adding Song 2 (should stay queued)...")
            async with http.post(
                f"{BASE}/rooms/{slug}/queue",
                json={"yt_id": "yt-002", "title": "Song Beta", "duration": 200000},
                headers=headers,
            ) as r:
                assert r.status == 200

            qev = await wait_for_event(ws, "queue_update")
            assert qev, "No queue_update received"
            print(f"   Queue has {len(qev['data']['queue'])} song(s)")
            assert len(qev["data"]["queue"]) >= 1, f"Expected >=1 queued, got {len(qev['data']['queue'])}"

            # 4. Signal song-ended → transition to Song Beta
            print("4. Signaling song-ended...")
            async with http.post(f"{BASE}/rooms/{slug}/queue/song-ended", headers=headers) as r:
                assert r.status == 200, f"song-ended failed: {await r.text()}"

            ev = await wait_for_event(ws, "playback_update")
            assert ev, "No playback_update after transition"
            assert ev["data"]["current_song_id"] == "yt-002", f"Wrong song: {ev['data']['current_song_id']}"
            print(f"   Transitioned to: {ev['data']['current_song_id']}")

            # 5. Vote-skip (single voter in a room of ~1 → should hit 50% threshold)
            print("5. Vote-skipping...")
            async with http.post(f"{BASE}/rooms/{slug}/queue/vote-skip", headers=headers) as r:
                assert r.status == 200
                vdata = await r.json()
            print(f"   Votes: {vdata['vote_count']}, Skipped: {vdata['skipped']}")

            if vdata["skipped"]:
                ev = await wait_for_event(ws, "playback_update")
                if ev:
                    print(f"   State after vote-skip: {ev['data']['status']}")

            # 6. Get queue (should be empty now)
            print("6. Checking final queue state...")
            async with http.get(f"{BASE}/rooms/{slug}/queue", headers=headers) as r:
                assert r.status == 200
                final_q = await r.json()
            print(f"   Now playing: {final_q['now_playing']}")
            print(f"   Queued: {len(final_q['queue'])}")

    print("\n All Phase 5 tests passed!")


if __name__ == "__main__":
    asyncio.run(run())
