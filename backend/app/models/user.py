from datetime import datetime
from uuid import UUID, uuid4
from sqlmodel import Field, SQLModel
from typing import Optional

class User(SQLModel, table=True):
    __tablename__ = "users"
    
    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    username: str = Field(index=True, unique=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
