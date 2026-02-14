from datetime import datetime
from uuid import UUID
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, field_validator


class RoomBase(BaseModel):
    name: str
    settings: Optional[Dict[str, Any]] = {"vote_skip_threshold": 0.5, "allow_guests": True}

class RoomCreate(RoomBase):
    pass

class RoomUpdate(RoomBase):
    is_active: Optional[bool] = None

class RoomRead(RoomBase):
    id: str
    host_id: UUID

    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True

    @field_validator("settings", mode="before")
    @classmethod
    def parse_settings(cls, v: Any) -> Dict[str, Any]:
        if isinstance(v, str):
            import json
            return json.loads(v)
        return v


class RoomState(BaseModel):
    meta: RoomRead
    playback: Dict[str, Any]
    participant_count: int

class RoomJoin(BaseModel):
    username: str

