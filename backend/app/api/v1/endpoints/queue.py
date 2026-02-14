"""
Phase 5+6: Queue & Voting Endpoints with yt-dlp integration.

All queue operations use the DB (Song table) as the source of truth.
Redis is used for vote-skip sets, real-time playback state, and stream URL cache.
"""
import logging
from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException, Body
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select, func, col

from app.api import deps
from app.db.session import get_session
from app.models.room import Room
from app.models.user import User
from app.models.song import Song, SongStatus
from app.models.vote import Vote, VoteType
from app.schemas.queue import QueueAddRequest, QueueSongResponse, QueueListResponse, VoteSkipResponse
from app.services.room_manager import get_room_manager, RoomManager
from app.services.ws_manager import manager as ws_manager
from app.services.yt_service import yt_service, ExtractionError
from app.services.rate_limiter import enforce_rate_limit
from app.core.redis import get_redis_client

logger = logging.getLogger(__name__)

router = APIRouter()


# ──────────────────────────────────────────────
#  Core transition function (idempotent)
# ──────────────────────────────────────────────

async def transition_to_next(
    slug: str,
    session: AsyncSession,
    room_manager: RoomManager,
):
    """
    Advance playback to the next QUEUED song.
    Extracts stream URL via yt-dlp before broadcasting.
    Idempotent: if queue is empty, sets room to idle.
    Returns the playback_update dict that was broadcast.
    """
    # 1. Find next queued song
    result = await session.execute(
        select(Song)
        .where(Song.room_id == slug, Song.status == SongStatus.QUEUED)
        .order_by(Song.position.asc())
        .limit(1)
    )
    next_song = result.scalar_one_or_none()

    if next_song:
        # 2a. Mark as PLAYING in DB
        next_song.status = SongStatus.PLAYING
        session.add(next_song)
        await session.commit()
        await session.refresh(next_song)

        # 2b. Update Redis playback state
        updates = await room_manager.play(slug, next_song.yt_id, 0)
        await room_manager.set_current_song_db_id(slug, next_song.id)

        # 2c. Phase 6: Extract stream URL via yt-dlp
        stream_url = None
        try:
            stream_url = await yt_service.get_or_extract_stream(next_song.yt_id)
            await room_manager.set_stream_url(slug, stream_url)
            updates["stream_url"] = stream_url
            logger.info(f"Stream URL extracted for {next_song.yt_id}")
        except ExtractionError as e:
            logger.error(f"Failed to extract stream for {next_song.yt_id}: {e}")
            updates["stream_url"] = None

        # 2d. Broadcast
        await ws_manager.publish_event(slug, "playback_update", updates)
        await _broadcast_queue(slug, session, room_manager)
        return updates
    else:
        # 3. Queue is empty → idle
        updates = await room_manager.set_idle(slug)
        await ws_manager.publish_event(slug, "playback_update", updates)
        await _broadcast_queue(slug, session, room_manager)
        return updates


async def _broadcast_queue(slug: str, session: AsyncSession, room_manager: RoomManager = None):
    """Helper to broadcast the current queue state."""
    result = await session.execute(
        select(Song)
        .where(Song.room_id == slug, Song.status == SongStatus.QUEUED)
        .order_by(Song.position.asc())
    )
    queued = result.scalars().all()

    result2 = await session.execute(
        select(Song)
        .where(Song.room_id == slug, Song.status == SongStatus.PLAYING)
        .limit(1)
    )
    now_playing = result2.scalar_one_or_none()

    # Include stream_url for now_playing
    np_dict = None
    if now_playing:
        np_dict = _song_to_dict(now_playing)
        if room_manager:
            stream_url = await room_manager.get_stream_url(slug)
            np_dict["stream_url"] = stream_url

    payload = {
        "now_playing": np_dict,
        "queue": [_song_to_dict(s) for s in queued],
    }
    await ws_manager.publish_event(slug, "queue_update", payload)


def _song_to_dict(song: Song) -> dict:
    return {
        "id": song.id,
        "room_id": song.room_id,
        "user_id": str(song.user_id),
        "yt_id": song.yt_id,
        "title": song.title,
        "duration": song.duration,
        "status": song.status.value,
        "position": song.position,
        "created_at": song.created_at.isoformat(),
    }


# ──────────────────────────────────────────────
#  API ENDPOINTS
# ──────────────────────────────────────────────

@router.post("/{slug}/queue", response_model=QueueSongResponse)
async def add_to_queue(
    slug: str,
    *,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(deps.get_current_user),
    room_manager: RoomManager = Depends(get_room_manager),
    payload: QueueAddRequest,
) -> Any:
    """Add a song to the queue.
    
    Accepts either:
      - query: search string → auto-resolves via yt-dlp
      - yt_id + title: direct add (legacy / pre-searched)
    
    Auto-plays if room is idle.
    """
    # Rate limit: 5 adds per 30s per room
    redis = await get_redis_client()
    await enforce_rate_limit(
        key=f"rl:queue:{slug}",
        limit=5,
        window_s=30,
        redis=redis,
        message="Queue rate limit exceeded (5 adds per 30s). Slow down!",
    )

    room = await session.get(Room, slug)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    yt_id = payload.yt_id
    title = payload.title
    duration = payload.duration

    # Phase 6: search-then-add
    if payload.query and not yt_id:
        try:
            results = await yt_service.search(payload.query, max_results=1)
            if not results:
                raise HTTPException(status_code=404, detail="No YouTube results found")
            top = results[0]
            yt_id = top.video_id
            title = top.title
            duration = top.duration_s * 1000  # convert seconds → ms
        except ExtractionError as e:
            raise HTTPException(status_code=502, detail=f"YouTube search failed: {e}")

    if not yt_id or not title:
        raise HTTPException(status_code=400, detail="Provide query or yt_id+title")

    # Calculate next position (max + 1)
    result = await session.execute(
        select(func.max(Song.position)).where(Song.room_id == slug)
    )
    max_pos = result.scalar_one_or_none()
    next_pos = (max_pos or 0) + 1

    song = Song(
        room_id=slug,
        user_id=current_user.id,
        yt_id=yt_id,
        title=title,
        duration=duration,
        status=SongStatus.QUEUED,
        position=next_pos,
    )
    session.add(song)
    await session.commit()
    await session.refresh(song)

    # Auto-play if room is idle
    state = await room_manager.get_room_state(slug)
    if state.get("status") == "idle" or state.get("status") is None:
        await transition_to_next(slug, session, room_manager)
    else:
        await _broadcast_queue(slug, session, room_manager)

    return song


@router.get("/{slug}/queue", response_model=QueueListResponse)
async def get_queue(
    slug: str,
    *,
    session: AsyncSession = Depends(get_session),
    room_manager: RoomManager = Depends(get_room_manager),
) -> Any:
    """Get the current queue for a room."""
    # Now playing
    result_playing = await session.execute(
        select(Song)
        .where(Song.room_id == slug, Song.status == SongStatus.PLAYING)
        .limit(1)
    )
    now_playing = result_playing.scalar_one_or_none()

    # Queued
    result_queued = await session.execute(
        select(Song)
        .where(Song.room_id == slug, Song.status == SongStatus.QUEUED)
        .order_by(Song.position.asc())
    )
    queued = result_queued.scalars().all()

    # Attach stream URL to now_playing
    np_response = None
    if now_playing:
        stream_url = await room_manager.get_stream_url(slug)
        np_response = QueueSongResponse(
            id=now_playing.id,
            room_id=now_playing.room_id,
            user_id=now_playing.user_id,
            yt_id=now_playing.yt_id,
            title=now_playing.title,
            duration=now_playing.duration,
            status=now_playing.status.value,
            position=now_playing.position,
            created_at=now_playing.created_at,
            stream_url=stream_url,
        )

    return QueueListResponse(
        now_playing=np_response,
        queue=queued,
    )


@router.post("/{slug}/queue/skip")
async def host_skip(
    slug: str,
    *,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(deps.get_current_user),
    room_manager: RoomManager = Depends(get_room_manager),
) -> Any:
    """Host only: skip the current song."""
    room = await session.get(Room, slug)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    if str(room.host_id) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Only host can skip")

    # Mark current song as SKIPPED
    current_song_id = await room_manager.get_current_song_db_id(slug)
    if current_song_id:
        current_song = await session.get(Song, current_song_id)
        if current_song and current_song.status == SongStatus.PLAYING:
            current_song.status = SongStatus.SKIPPED
            session.add(current_song)
            await session.commit()
            await room_manager.clear_votes(slug, current_song_id)

    updates = await transition_to_next(slug, session, room_manager)
    return {"status": "skipped", "playback": updates}


@router.post("/{slug}/queue/vote-skip", response_model=VoteSkipResponse)
async def vote_skip(
    slug: str,
    *,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(deps.get_current_user),
    room_manager: RoomManager = Depends(get_room_manager),
) -> Any:
    """Any member: vote to skip the current song."""
    room = await session.get(Room, slug)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    current_song_id = await room_manager.get_current_song_db_id(slug)
    if not current_song_id:
        raise HTTPException(status_code=400, detail="No song is currently playing")

    # Atomic vote via Redis SADD
    vote_count = await room_manager.add_vote(slug, current_song_id, str(current_user.id))
    participant_count = await room_manager.get_participant_count(slug)

    # Also persist to DB (backup, idempotent due to composite PK)
    try:
        vote_record = Vote(
            song_id=current_song_id,
            user_id=current_user.id,
            type=VoteType.SKIP,
        )
        session.add(vote_record)
        await session.commit()
    except Exception:
        # Duplicate vote — already exists in DB, ignore
        await session.rollback()

    # Threshold check
    threshold = 0.5
    if room.settings and isinstance(room.settings, dict):
        threshold = room.settings.get("vote_skip_threshold", 0.5)

    skipped = False
    if participant_count > 0 and (vote_count / participant_count) >= threshold:
        # Auto-skip triggered
        current_song = await session.get(Song, current_song_id)
        if current_song and current_song.status == SongStatus.PLAYING:
            current_song.status = SongStatus.SKIPPED
            session.add(current_song)
            await session.commit()
            await room_manager.clear_votes(slug, current_song_id)
            await transition_to_next(slug, session, room_manager)
            skipped = True

    # Broadcast vote update
    await ws_manager.publish_event(slug, "vote_update", {
        "song_id": current_song_id,
        "vote_count": vote_count,
        "threshold": threshold,
        "participant_count": participant_count,
        "skipped": skipped,
    })

    return VoteSkipResponse(
        vote_count=vote_count,
        threshold=threshold,
        participant_count=participant_count,
        skipped=skipped,
    )


@router.post("/{slug}/queue/song-ended")
async def song_ended(
    slug: str,
    *,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(deps.get_current_user),
    room_manager: RoomManager = Depends(get_room_manager),
) -> Any:
    """Signal that the current song has finished playing."""
    room = await session.get(Room, slug)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    # Mark current song as PLAYED
    current_song_id = await room_manager.get_current_song_db_id(slug)
    if current_song_id:
        current_song = await session.get(Song, current_song_id)
        if current_song and current_song.status == SongStatus.PLAYING:
            current_song.status = SongStatus.PLAYED
            session.add(current_song)
            await session.commit()
            await room_manager.clear_votes(slug, current_song_id)

    updates = await transition_to_next(slug, session, room_manager)
    return {"status": "transitioned", "playback": updates}
