from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel

class SongBase(BaseModel):
    yt_id: str
    title: str
    duration: Optional[int] = None

class SongCreate(SongBase):
    room_id: str

class SongRead(SongBase):
    id: int
    room_id: str
    user_id: UUID
    status: str
    position: int
    created_at: datetime
    
    class Config:
        from_attributes = True
