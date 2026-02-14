from fastapi import APIRouter
from app.api.v1.endpoints import auth, rooms, songs, queue, search

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(rooms.router, prefix="/rooms", tags=["rooms"])
api_router.include_router(songs.router, prefix="/songs", tags=["songs"])
api_router.include_router(queue.router, prefix="/rooms", tags=["queue"])
api_router.include_router(search.router, prefix="/search", tags=["search"])
from app.api.v1.endpoints import ws
api_router.include_router(ws.router, prefix="/ws", tags=["ws"])


