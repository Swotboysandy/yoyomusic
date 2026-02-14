from datetime import datetime
from uuid import UUID
from typing import Optional
from sqlmodel import Field, SQLModel
from enum import Enum

class SongStatus(str, Enum):
    QUEUED = "queued"
    PLAYING = "playing"
    PLAYED = "played"
    SKIPPED = "skipped"

class Song(SQLModel, table=True):
    __tablename__ = "songs"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    room_id: str = Field(foreign_key="rooms.id", index=True)
    user_id: UUID = Field(foreign_key="users.id")
    yt_id: str
    title: str
    duration: Optional[int] = None
    status: SongStatus = Field(default=SongStatus.QUEUED, index=True)
    position: int = Field(default=0)
    created_at: datetime = Field(default_factory=datetime.utcnow)
