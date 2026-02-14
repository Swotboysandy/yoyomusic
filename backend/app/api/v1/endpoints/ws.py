from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from app.services.ws_manager import manager
from app.services.room_manager import get_room_manager, RoomManager

router = APIRouter()

@router.websocket("/{slug}")
async def websocket_endpoint(
    websocket: WebSocket,
    slug: str,
    # token: str = Query(...) # Auth later
):
    # Retrieve managers
    room_manager = await get_room_manager()
    
    # 1. Accept Connection
    await manager.connect(websocket, slug)
    
    try:
        # 2. Add to Redis Participants (if not already handled by Join API)
        # Actually, Join API adds them. WS just reflects presence.
        # But if they disconnect, we need to remove them?
        # For Phase 3, let's assume specific "user_id" is passed or generated.
        # Since we don't have Auth in WS handshake yet, let's generate a temporary ID or use a query param
        
        # Simulating a user ID for the socket session
        # In real app: user_id = verify_token(token).id
        import uuid
        user_id = str(uuid.uuid4())[:8] 
        
        # Broadcast Join Event
        await manager.publish_event(slug, "participant_joined", {"user_id": user_id, "count": await room_manager.get_participant_count(slug)})
        
        while True:
            data = await websocket.receive_text()
            # Handle incoming messages (Ping/Pong, or Chat in future)
            # For now, echo or ignore.
            pass
            
    except WebSocketDisconnect:
        manager.disconnect(websocket, slug)
        # Remove from Redis
        # await room_manager.remove_participant(slug, user_id) 
        # Broadcast Leave Event
        # await manager.publish_event(slug, "participant_left", {"user_id": user_id, "count": await room_manager.get_participant_count(slug)})
        pass
