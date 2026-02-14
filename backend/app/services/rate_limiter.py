"""
Redis sliding-window rate limiter.

Uses a ZSET per key with timestamps as scores.
Pattern: ZREMRANGEBYSCORE → ZADD → ZCARD → EXPIRE (pipeline, atomic).
"""
import time
import logging
from redis.asyncio import Redis
from fastapi import HTTPException

from app.core.redis import get_redis_client

logger = logging.getLogger(__name__)


async def check_rate_limit(
    key: str,
    limit: int,
    window_s: int,
    redis: Redis | None = None,
) -> bool:
    """
    Check if request is within rate limit.
    Returns True if allowed, False if exceeded.
    """
    if redis is None:
        redis = await get_redis_client()

    now = time.time()
    pipe = redis.pipeline()
    pipe.zremrangebyscore(key, 0, now - window_s)
    pipe.zadd(key, {f"{now}:{id(key)}": now})
    pipe.zcard(key)
    pipe.expire(key, window_s + 1)
    results = await pipe.execute()
    count = results[2]

    if count > limit:
        logger.warning(f"Rate limit exceeded: {key} ({count}/{limit})")
        return False
    return True


async def enforce_rate_limit(
    key: str,
    limit: int,
    window_s: int,
    redis: Redis | None = None,
    message: str = "Rate limit exceeded. Try again later.",
):
    """Check rate limit and raise 429 if exceeded."""
    allowed = await check_rate_limit(key, limit, window_s, redis)
    if not allowed:
        raise HTTPException(status_code=429, detail=message)
