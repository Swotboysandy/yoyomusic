from datetime import datetime
from uuid import UUID
from typing import Optional, List
from pydantic import BaseModel


class QueueAddRequest(BaseModel):
    """Request to add a song to the queue.
    
    Either provide yt_id+title (direct add) OR query (search-then-add).
    """
    yt_id: Optional[str] = None
    title: Optional[str] = None
    duration: Optional[int] = None  # milliseconds
    query: Optional[str] = None     # Phase 6: search query


class QueueSongResponse(BaseModel):
    """A single song in the queue."""
    id: int
    room_id: str
    user_id: UUID
    yt_id: str
    title: str
    duration: Optional[int] = None
    status: str
    position: int
    created_at: datetime
    stream_url: Optional[str] = None  # Phase 6: only for now_playing

    class Config:
        from_attributes = True


class QueueListResponse(BaseModel):
    """Full queue state for a room."""
    now_playing: Optional[QueueSongResponse] = None
    queue: List[QueueSongResponse]


class VoteSkipResponse(BaseModel):
    """Response after casting a vote-skip."""
    vote_count: int
    threshold: float
    participant_count: int
    skipped: bool
