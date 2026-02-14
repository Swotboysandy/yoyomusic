"""
Phase 6+Hardening: YouTube Service — search & stream extraction via yt-dlp.

Concurrency protections:
  - asyncio.Semaphore(2): max 2 parallel yt-dlp processes (~100MB on Render)
  - Redis distributed lock: SET NX EX prevents duplicate extraction across instances
  - In-flight dedup: asyncio.Event per video_id on this process
  - Execution time logging for every subprocess call
"""
import asyncio
import json
import time
import logging
from typing import Optional
from dataclasses import dataclass

from app.core.redis import get_redis_client

logger = logging.getLogger(__name__)

STREAM_TTL = 14400          # 4h — YouTube signatures last ~6h
REFRESH_TTL = 3600          # 1h — re-extraction after 403
MAX_CONCURRENT = 2          # Render free: 0.5 CPU, 512MB
SEARCH_TIMEOUT = 15.0
EXTRACT_TIMEOUT = 20.0
LOCK_TTL = 30               # seconds — extraction lock expiry
LOCK_POLL_INTERVAL = 0.5    # seconds — poll cache while locked
LOCK_POLL_MAX = 50           # max polls (25s total)


class ExtractionError(Exception):
    """Raised when yt-dlp fails or times out."""
    pass


@dataclass
class SearchResult:
    video_id: str
    title: str
    duration_s: int
    thumbnail: str | None = None


class YouTubeService:
    def __init__(self):
        self._semaphore = asyncio.Semaphore(MAX_CONCURRENT)
        self._inflight: dict[str, asyncio.Event] = {}
        self._inflight_lock = asyncio.Lock()

    # ─────────────────── low-level runner ───────────────────

    async def _run_ytdlp(self, args: list[str], timeout: float = 15.0) -> str:
        """Run yt-dlp as async subprocess, guarded by semaphore."""
        async with self._semaphore:
            start = time.monotonic()
            logger.info(f"yt-dlp spawning: {' '.join(args[:6])}...")
            proc = await asyncio.create_subprocess_exec(
                "yt-dlp", *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(), timeout=timeout
                )
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                elapsed = time.monotonic() - start
                logger.error(f"yt-dlp TIMEOUT after {elapsed:.1f}s")
                raise ExtractionError("yt-dlp timed out")

            elapsed = time.monotonic() - start

            if proc.returncode != 0:
                err_msg = stderr.decode(errors="replace").strip()
                logger.error(f"yt-dlp FAILED in {elapsed:.1f}s: {err_msg[:200]}")
                raise ExtractionError(f"yt-dlp failed: {err_msg[:200]}")

            logger.info(f"yt-dlp completed in {elapsed:.1f}s")
            return stdout.decode(errors="replace").strip()

    # ─────────────────── search ───────────────────

    async def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        """Search YouTube via ytsearch, return metadata only (no download)."""
        raw = await self._run_ytdlp([
            f"ytsearch{max_results}:{query}",
            "--dump-json",
            "--flat-playlist",
            "--no-download",
            "--no-warnings",
            "--skip-download",
        ], timeout=SEARCH_TIMEOUT)

        results = []
        for line in raw.splitlines():
            if not line.strip():
                continue
            try:
                data = json.loads(line)
                results.append(SearchResult(
                    video_id=data.get("id", ""),
                    title=data.get("title", "Unknown"),
                    duration_s=int(data.get("duration", 0) or 0),
                    thumbnail=data.get("thumbnail") or data.get("thumbnails", [{}])[0].get("url"),
                ))
            except (json.JSONDecodeError, KeyError, IndexError):
                continue

        return results

    # ─────────────────── extract stream URL ───────────────────

    async def extract_stream_url(self, video_id: str) -> str:
        """Extract the best audio-only stream URL (no download)."""
        url = await self._run_ytdlp([
            f"https://www.youtube.com/watch?v={video_id}",
            "-f", "bestaudio",
            "--get-url",
            "--no-download",
            "--no-warnings",
            "--no-playlist",
        ], timeout=EXTRACT_TIMEOUT)

        if not url or not url.startswith("http"):
            raise ExtractionError(f"Invalid URL returned for {video_id}")

        return url.split("\n")[0]

    # ─────────────────── cache-first with dedup ───────────────────

    async def get_or_extract_stream(self, video_id: str) -> str:
        """
        Cache-first stream URL retrieval with distributed locking:

        1. Check Redis cache → return if hit
        2. Check in-flight map → wait if another coroutine is extracting
        3. Acquire Redis lock (SET NX EX 30)
            - If acquired → extract → cache → release → notify waiters
            - If NOT acquired → poll cache until available
        """
        redis = await get_redis_client()
        cache_key = f"stream:{video_id}"
        lock_key = f"lock:extract:{video_id}"

        # ── Step 1: cache check ──
        cached = await redis.get(cache_key)
        if cached:
            logger.info(f"Stream cache HIT: {video_id}")
            return cached

        # ── Step 2: in-flight dedup on this process ──
        async with self._inflight_lock:
            if video_id in self._inflight:
                event = self._inflight[video_id]
                logger.info(f"Stream in-flight DEDUP: waiting for {video_id}")
        
        # If found in-flight, wait outside the lock
        if video_id in self._inflight:
            event = self._inflight[video_id]
            await asyncio.wait_for(event.wait(), timeout=EXTRACT_TIMEOUT + 5)
            cached = await redis.get(cache_key)
            if cached:
                return cached
            raise ExtractionError(f"In-flight extraction failed for {video_id}")

        # ── Step 3: try to acquire distributed lock ──
        acquired = await redis.set(lock_key, "1", nx=True, ex=LOCK_TTL)

        if not acquired:
            # Another instance is extracting — poll cache
            logger.info(f"Stream lock WAIT: {video_id} (another instance extracting)")
            for _ in range(LOCK_POLL_MAX):
                await asyncio.sleep(LOCK_POLL_INTERVAL)
                cached = await redis.get(cache_key)
                if cached:
                    return cached
            raise ExtractionError(f"Timed out waiting for extraction of {video_id}")

        # ── Step 4: we have the lock — extract ──
        event = asyncio.Event()
        async with self._inflight_lock:
            self._inflight[video_id] = event

        try:
            logger.info(f"Stream cache MISS: extracting {video_id}")
            url = await self.extract_stream_url(video_id)
            await redis.set(cache_key, url, ex=STREAM_TTL)
            return url
        except Exception:
            raise
        finally:
            # Release lock + notify waiters
            await redis.delete(lock_key)
            event.set()
            async with self._inflight_lock:
                self._inflight.pop(video_id, None)

    async def refresh_stream(self, video_id: str) -> str:
        """Force re-extraction (e.g., after 403). Uses shorter TTL."""
        redis = await get_redis_client()
        await redis.delete(f"stream:{video_id}")
        url = await self.extract_stream_url(video_id)
        await redis.set(f"stream:{video_id}", url, ex=REFRESH_TTL)
        return url

    async def invalidate_cache(self, video_id: str):
        """Remove cached URL."""
        redis = await get_redis_client()
        await redis.delete(f"stream:{video_id}")


# Module-level singleton
yt_service = YouTubeService()
