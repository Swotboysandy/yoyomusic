from datetime import datetime
from uuid import UUID
from typing import Optional, Dict, Any, List
from sqlmodel import Field, SQLModel, JSON, Relationship
from sqlalchemy import Column
from enum import Enum

class RoomMemberRole(str, Enum):
    HOST = "host"
    DJ = "dj"
    LISTENER = "listener"

class RoomMember(SQLModel, table=True):
    __tablename__ = "room_members"
    
    room_id: str = Field(foreign_key="rooms.id", primary_key=True)
    user_id: UUID = Field(foreign_key="users.id", primary_key=True)
    role: RoomMemberRole = Field(default=RoomMemberRole.LISTENER, index=True)
    joined_at: datetime = Field(default_factory=datetime.utcnow)

class Room(SQLModel, table=True):
    __tablename__ = "rooms"
    
    id: str = Field(primary_key=True, index=True, max_length=8, description="Unique 8-char slug")
    name: str
    host_id: UUID = Field(foreign_key="users.id")
    is_active: bool = Field(default=True)
    settings: Dict[str, Any] = Field(default={"vote_skip_threshold": 0.5, "allow_guests": True}, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=datetime.utcnow)

