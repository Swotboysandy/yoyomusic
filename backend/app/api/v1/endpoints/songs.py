from typing import Any, List
from fastapi import APIRouter, Depends
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api import deps
from app.db.session import get_session
from app.schemas.song import SongCreate, SongRead

router = APIRouter()

@router.get("/{room_id}", response_model=List[SongRead])
async def read_songs(
    room_id: str,
    session: AsyncSession = Depends(get_session),
) -> Any:
    """
    Get songs for a room.
    """
    return []

@router.post("/", response_model=SongRead)
async def add_song(
    *,
    session: AsyncSession = Depends(get_session),
    song_in: SongCreate,
) -> Any:
    """
    Add song to queue.
    """
    return SongRead(
        id=1, 
        room_id=song_in.room_id, 
        user_id="00000000-0000-0000-0000-000000000000", 
        yt_id=song_in.yt_id, 
        title=song_in.title, 
        status="queued", 
        position=0, 
        created_at="2024-01-01T00:00:00"
    )
