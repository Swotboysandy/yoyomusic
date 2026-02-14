from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, EmailStr

# Shared properties
class UserBase(BaseModel):
    username: str

# Properties to receive via API on creation
class UserCreate(UserBase):
    pass

# Properties to return via API
class UserRead(UserBase):
    id: UUID
    created_at: datetime
    
    class Config:
        from_attributes = True
