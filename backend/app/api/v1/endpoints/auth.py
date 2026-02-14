from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api import deps
from app.core import security
from app.db.session import get_session
from app.schemas.token import Token
from app.schemas.user import UserCreate, UserRead

router = APIRouter()

@router.post("/login/access-token", response_model=Token)
async def login_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: AsyncSession = Depends(get_session)
) -> Any:
    """
    OAuth2 compatible token login, get an access token for future requests
    """
    # Mock auth for Phase 1
    # In real impl, check user against DB
    if form_data.username == "test" and form_data.password == "test":
        return {
            "access_token": security.create_access_token(subject="test_user_id"),
            "token_type": "bearer",
        }
    
    # Real DB check skeleton
    # user = await crud.user.authenticate(session, email=form_data.username, password=form_data.password)
    # if not user:
    #     raise HTTPException(status_code=400, detail="Incorrect email or password")
    
    return {
        "access_token": security.create_access_token(subject=form_data.username),
        "token_type": "bearer",
    }

@router.post("/signup", response_model=UserRead)
async def create_user(
    *,
    session: AsyncSession = Depends(get_session),
    user_in: UserCreate,
) -> Any:
    """
    Create new user.
    """
    # Mock functionality
    return UserRead(id="00000000-0000-0000-0000-000000000000", username=user_in.username, created_at="2024-01-01T00:00:00")

@router.get("/dev-token")
async def get_dev_token() -> Any:
    """
    DEV ONLY: Get a valid token without credentials.
    Remove this in production.
    """
    return {
        "access_token": security.create_access_token(subject="dev@yoyomusic.local"),
        "token_type": "bearer",
    }
