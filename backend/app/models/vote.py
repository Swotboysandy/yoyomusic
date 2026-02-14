from uuid import UUID
from sqlmodel import Field, SQLModel
from enum import Enum

class VoteType(str, Enum):
    SKIP = "skip"
    LIKE = "like"

class Vote(SQLModel, table=True):
    __tablename__ = "votes"
    
    song_id: int = Field(foreign_key="songs.id", primary_key=True)
    user_id: UUID = Field(foreign_key="users.id", primary_key=True)
    type: VoteType = Field(primary_key=True)
