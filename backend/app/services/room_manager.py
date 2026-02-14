from datetime import datetime
from typing import Optional, List, Dict, Any
import json
from redis.asyncio import Redis
from app.core.redis import get_redis_client

class RoomManager:
    def __init__(self, redis: Redis):
        self.redis = redis

    def _key_meta(self, room_id: str) -> str:
        return f"room:{room_id}:meta"

    def _key_state(self, room_id: str) -> str:
        return f"room:{room_id}:state"

    def _key_users(self, room_id: str) -> str:
        return f"room:{room_id}:users"
    
    def _key_queue(self, room_id: str) -> str:
        return f"room:{room_id}:queue"

    async def initialize_room(self, room_id: str, host_id: str, settings: Dict[str, Any]):
        """Initialize redis state for a new room."""
        try:
            # Metadata
            mapping = {
                "host_id": str(host_id),
                "active": "1",
                "settings": json.dumps(settings)
            }
            for k, v in mapping.items():
                await self.redis.hset(self._key_meta(room_id), k, v)
            
            # Clean/Empty State
            await self.redis.delete(self._key_state(room_id))
            await self.redis.delete(self._key_users(room_id))
            await self.redis.delete(self._key_queue(room_id))
        except Exception as e:
            print(f"Redis Error in initialize_room: {e}")
            raise e

    async def add_participant(self, room_id: str, user_id: str):
        """Add user to the room's participant set."""
        await self.redis.sadd(self._key_users(room_id), str(user_id))

    async def remove_participant(self, room_id: str, user_id: str):
        """Remove user from participant set."""
        await self.redis.srem(self._key_users(room_id), str(user_id))

    async def get_participant_count(self, room_id: str) -> int:
        return await self.redis.scard(self._key_users(room_id))

    async def get_room_state(self, room_id: str) -> Dict[str, Any]:
        """Fetch full playback state."""
        state = await self.redis.hgetall(self._key_state(room_id))
        if not state:
            return {
                "status": "idle",
                "current_song_id": "",
                "position_ms": 0,
                "updated_at": 0,
                "speed": 1.0
            }
        return state
    
    async def update_playback_state(self, room_id: str, updates: Dict[str, Any]):
        """Update specific fields in playback state."""
        # Convert non-string values
        clean_updates = {k: str(v) for k, v in updates.items()}
        # Use simple HSET (Last Write Wins)
        if clean_updates:
            for k, v in clean_updates.items():
                await self.redis.hset(self._key_state(room_id), k, v)

    def _get_server_time(self) -> int:
        """Return current server time in milliseconds."""
        return int(datetime.utcnow().timestamp() * 1000)

    async def play(self, room_id: str, song_id: str, position_ms: int = 0):
        """Start or resume playback."""
        now = self._get_server_time()
        updates = {
            "status": "playing",
            "current_song_id": song_id,
            "position_ms": position_ms,
            "updated_at": now,
            "speed": 1.0
        }
        await self.update_playback_state(room_id, updates)
        return updates

    async def pause(self, room_id: str):
        """Pause playback."""
        # To pause accurately, we need to calculate the current position based on the previous 'updated_at'
        # But for 'Last Write Wins' simplicity from the client (Host), the Host usually sends the position they paused at.
        # However, to be Server-Authoritative, the server should calculate it OR trust the Host's position if it's within tolerance.
        # For Phase 4, we will TRUST the Host's current position for Pause, 
        # because the Host is the source of truth for the audio player state.
        # Wait, the instruction says "Server-Authoritative". 
        # If we calculate it on the server:
        # current_state = await self.get_room_state(room_id)
        # if current_state['status'] == 'playing':
        #    elapsed = now - current_state['updated_at']
        #    new_pos = current_state['position_ms'] + elapsed
        #    ...
        # But this might drift from what the Host actually heard.
        # Recommendation: Host sends 'pause' event with their current position. Server accepts it.
        # Let's change the signature to accept position if provided, else calculate.
        
        # Actually, let's keep it simple: Host sends the command, Server marks as paused at NOW. 
        # But we need the position. 
        # Let's assume the API will pass the position_ms from the request.
        pass # Placeholder to be overridden by implementation below that accepts position_ms

    async def pause_at(self, room_id: str, position_ms: int):
        """Pause playback at specific position."""
        now = self._get_server_time()
        updates = {
            "status": "paused",
            "position_ms": position_ms,
            "updated_at": now
        }
        await self.update_playback_state(room_id, updates)
        return updates

    async def seek(self, room_id: str, position_ms: int):
        """Seek to position."""
        now = self._get_server_time()
        updates = {
            "position_ms": position_ms,
            "updated_at": now
        }
        await self.update_playback_state(room_id, updates)
        return updates

    # --- Vote-Skip Helpers ---

    def _key_votes(self, room_id: str, song_id: int) -> str:
        return f"room:{room_id}:votes:{song_id}"

    async def add_vote(self, room_id: str, song_id: int, user_id: str) -> int:
        """Add a skip vote. Returns new vote count. SADD is atomic and idempotent."""
        await self.redis.sadd(self._key_votes(room_id, song_id), str(user_id))
        return await self.redis.scard(self._key_votes(room_id, song_id))

    async def get_vote_count(self, room_id: str, song_id: int) -> int:
        return await self.redis.scard(self._key_votes(room_id, song_id))

    async def clear_votes(self, room_id: str, song_id: int):
        """Clean up vote set after song transitions."""
        await self.redis.delete(self._key_votes(room_id, song_id))

    # --- Current Song DB ID Tracking ---

    async def set_current_song_db_id(self, room_id: str, song_db_id: int):
        await self.redis.hset(self._key_state(room_id), "current_song_db_id", str(song_db_id))

    async def get_current_song_db_id(self, room_id: str) -> Optional[int]:
        val = await self.redis.hget(self._key_state(room_id), "current_song_db_id")
        return int(val) if val else None

    async def set_idle(self, room_id: str):
        """Set room to idle (no song playing)."""
        now = self._get_server_time()
        updates = {
            "status": "idle",
            "current_song_id": "",
            "current_song_db_id": "0",
            "position_ms": 0,
            "updated_at": now,
        }
        await self.update_playback_state(room_id, updates)
        return updates

    # --- Stream URL Helpers ---

    async def set_stream_url(self, room_id: str, url: str):
        """Store current stream URL in playback state for late joiners."""
        await self.redis.hset(self._key_state(room_id), "stream_url", url)

    async def get_stream_url(self, room_id: str) -> Optional[str]:
        val = await self.redis.hget(self._key_state(room_id), "stream_url")
        return val if val else None

# Global helper to get manager
async def get_room_manager() -> RoomManager:
    redis = await get_redis_client()
    return RoomManager(redis)
