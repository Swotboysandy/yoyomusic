"""
Phase 6+Hardening: YouTube Search Endpoint with rate limiting.
"""
from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.api import deps
from app.models.user import User
from app.services.yt_service import yt_service, ExtractionError
from app.services.rate_limiter import enforce_rate_limit
from app.core.redis import get_redis_client

router = APIRouter()


class SearchResultResponse(BaseModel):
    video_id: str
    title: str
    duration_s: int
    thumbnail: str | None = None


@router.get("/", response_model=List[SearchResultResponse])
async def search_youtube(
    q: str = Query(..., min_length=1, max_length=200, description="Search query"),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """Search YouTube for songs. Returns top 5 results.
    Rate limited: 10 searches per 60 seconds per user.
    """
    redis = await get_redis_client()
    await enforce_rate_limit(
        key=f"rl:search:{current_user.id}",
        limit=10,
        window_s=60,
        redis=redis,
        message="Search rate limit exceeded (10/min). Try again shortly.",
    )

    try:
        results = await yt_service.search(q, max_results=5)
    except ExtractionError as e:
        raise HTTPException(status_code=502, detail=f"YouTube search failed: {str(e)}")

    return [
        SearchResultResponse(
            video_id=r.video_id,
            title=r.title,
            duration_s=r.duration_s,
            thumbnail=r.thumbnail,
        )
        for r in results
    ]


@router.get("/stream/{video_id}")
async def get_stream_url(
    video_id: str,
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Get audio stream URL for a video (cache-first).
    Used by late joiners or when stream URL expires.
    """
    try:
        url = await yt_service.get_or_extract_stream(video_id)
    except ExtractionError as e:
        raise HTTPException(status_code=502, detail=f"Stream extraction failed: {str(e)}")

    return {"video_id": video_id, "stream_url": url}
