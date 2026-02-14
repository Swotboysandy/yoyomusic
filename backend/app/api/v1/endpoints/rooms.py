from typing import Any, List
import uuid
import random
import string
from fastapi import APIRouter, Depends, HTTPException, Body
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select

from app.api import deps
from app.db.session import get_session
from app.models.room import Room, RoomMember, RoomMemberRole
from app.models.user import User
from app.schemas.room import RoomCreate, RoomRead, RoomJoin, RoomState
from app.services.room_manager import get_room_manager, RoomManager
from app.services.ws_manager import manager as ws_manager

router = APIRouter()

def generate_slug(length=6):
    chars = string.ascii_uppercase + string.digits
    return ''.join(random.choice(chars) for _ in range(length))

@router.post("/", response_model=RoomRead)
async def create_room(
    *,
    session: AsyncSession = Depends(get_session),
    room_in: RoomCreate,
    current_user: User = Depends(deps.get_current_user), # Assuming auth is working or mocked
    room_manager: RoomManager = Depends(get_room_manager)
) -> Any:
    """
    Create new room.
    """
    # 1. Generate Slug
    slug = generate_slug()
    while await session.get(Room, slug):
        slug = generate_slug()

    # 2. Create Room DB Entry
    room = Room(
        id=slug,
        name=room_in.name,
        host_id=current_user.id,
        settings=room_in.settings
    )
    session.add(room)
    
    # 3. Add Host as Member
    member = RoomMember(
        room_id=slug,
        user_id=current_user.id,
        role=RoomMemberRole.HOST
    )
    session.add(member)
    
    await session.commit()
    await session.refresh(room)
    
    # 4. Initialize Redis State
    await room_manager.initialize_room(slug, str(current_user.id), room.settings)
    
    return room

@router.post("/{slug}/join", response_model=RoomState)
async def join_room(
    slug: str,
    *,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(deps.get_current_user),
    room_manager: RoomManager = Depends(get_room_manager)
) -> Any:
    """
    Join a room.
    """
    room = await session.get(Room, slug)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
        
    # Check if already member
    result = await session.execute(
        select(RoomMember).where(RoomMember.room_id == slug, RoomMember.user_id == current_user.id)
    )
    member = result.scalar_one_or_none()
    
    if not member:
        member = RoomMember(
            room_id=slug,
            user_id=current_user.id,
            role=RoomMemberRole.LISTENER
        )
        session.add(member)
        await session.commit()
    
    # Add to Redis Participants
    await room_manager.add_participant(slug, str(current_user.id))
    
    # Fetch State
    playback_state = await room_manager.get_room_state(slug)
    count = await room_manager.get_participant_count(slug)
    
    return RoomState(
        meta=room,
        playback=playback_state,
        participant_count=count
    )

@router.get("/{slug}", response_model=RoomState)
async def get_room(
    slug: str,
    *,
    session: AsyncSession = Depends(get_session),
    room_manager: RoomManager = Depends(get_room_manager)
) -> Any:
    """
    Get room info and state.
    """
    room = await session.get(Room, slug)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
        
    playback_state = await room_manager.get_room_state(slug)
    count = await room_manager.get_participant_count(slug)
    
    return RoomState(
        meta=room,
        playback=playback_state,
        participant_count=count
    )

# --- Player Endpoints ---

@router.post("/{slug}/player/play")
async def play_music(
    slug: str,
    *,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(deps.get_current_user),
    room_manager: RoomManager = Depends(get_room_manager),
    payload: dict = Body(...)
):
    """
    Host only: Play music.
    Payload: { "song_id": str, "position_ms": int }
    """
    room = await session.get(Room, slug)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    
    # Host Check
    if str(room.host_id) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Only host can control playback")

    song_id = payload.get("song_id")
    position_ms = payload.get("position_ms", 0)
    
    updates = await room_manager.play(slug, song_id, position_ms)
    
    # Broadcast
    await ws_manager.publish_event(slug, "playback_update", updates)
    return updates

@router.post("/{slug}/player/pause")
async def pause_music(
    slug: str,
    *,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(deps.get_current_user),
    room_manager: RoomManager = Depends(get_room_manager),
    payload: dict = Body(...)
):
    """
    Host only: Pause music.
    Payload: { "position_ms": int }
    """
    room = await session.get(Room, slug)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    
    if str(room.host_id) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Only host can control playback")

    position_ms = payload.get("position_ms", 0)
    
    updates = await room_manager.pause_at(slug, position_ms)
    
    await ws_manager.publish_event(slug, "playback_update", updates)
    return updates

@router.post("/{slug}/player/seek")
async def seek_music(
    slug: str,
    *,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(deps.get_current_user),
    room_manager: RoomManager = Depends(get_room_manager),
    payload: dict = Body(...)
):
    """
    Host only: Seek.
    Payload: { "position_ms": int }
    """
    room = await session.get(Room, slug)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    
    if str(room.host_id) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Only host can control playback")

    position_ms = payload.get("position_ms", 0)
    
    updates = await room_manager.seek(slug, position_ms)
    
    await ws_manager.publish_event(slug, "playback_update", updates)
    return updates
