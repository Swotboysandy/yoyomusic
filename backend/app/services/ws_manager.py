"""
WebSocket Connection Manager with shared Redis PubSub.

Hardened for 100 concurrent users:
  - Single shared PubSub connection (not per-room)
  - Dynamic subscribe/unsubscribe as rooms activate/empty
  - Dead connection cleanup on send failure
  - Room-scoped broadcasts
"""
import asyncio
import json
import logging
from typing import Dict, List
from fastapi import WebSocket
from redis.asyncio import Redis

from app.core.redis import get_redis_client

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}
        self._pubsub: Redis = None
        self._listener_task: asyncio.Task | None = None
        self._subscribed_rooms: set[str] = set()

    async def connect(self, websocket: WebSocket, room_slug: str):
        await websocket.accept()
        if room_slug not in self.active_connections:
            self.active_connections[room_slug] = []
        self.active_connections[room_slug].append(websocket)

        # Subscribe to room channel if first connection
        if room_slug not in self._subscribed_rooms:
            await self._ensure_pubsub()
            channel = f"room_events:{room_slug}"
            await self._pubsub.subscribe(channel)
            self._subscribed_rooms.add(room_slug)
            logger.info(f"PubSub subscribed: {room_slug} (total: {len(self._subscribed_rooms)})")

    def disconnect(self, websocket: WebSocket, room_slug: str):
        if room_slug in self.active_connections:
            try:
                self.active_connections[room_slug].remove(websocket)
            except ValueError:
                pass

            # Unsubscribe if no connections left for this room
            if not self.active_connections[room_slug]:
                del self.active_connections[room_slug]
                asyncio.create_task(self._unsubscribe_room(room_slug))

    async def _unsubscribe_room(self, room_slug: str):
        """Remove PubSub subscription when room empties."""
        if room_slug in self._subscribed_rooms and self._pubsub:
            try:
                await self._pubsub.unsubscribe(f"room_events:{room_slug}")
                self._subscribed_rooms.discard(room_slug)
                logger.info(f"PubSub unsubscribed: {room_slug} (total: {len(self._subscribed_rooms)})")
            except Exception as e:
                logger.warning(f"Unsubscribe error for {room_slug}: {e}")

    async def broadcast_local(self, room_slug: str, message: dict):
        """Send message to all local connections for this room, cleaning dead ones."""
        if room_slug not in self.active_connections:
            return

        dead = []
        for ws in list(self.active_connections.get(room_slug, [])):
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)

        # Clean dead connections
        for ws in dead:
            logger.info(f"Removing dead WS connection in {room_slug}")
            self.disconnect(ws, room_slug)

    async def publish_event(self, room_slug: str, event_type: str, data: dict):
        """Publish event to Redis for all instances to broadcast."""
        redis = await get_redis_client()
        message = {
            "type": event_type,
            "data": data,
            "room_slug": room_slug,
        }
        await redis.publish(f"room_events:{room_slug}", json.dumps(message))

    # ─────────────────── shared PubSub ───────────────────

    async def _ensure_pubsub(self):
        """Create shared PubSub connection and listener if not running."""
        if self._pubsub is None:
            redis = await get_redis_client()
            self._pubsub = redis.pubsub()

        if self._listener_task is None or self._listener_task.done():
            self._listener_task = asyncio.create_task(self._shared_listener())
            logger.info("Shared PubSub listener started")

    async def _shared_listener(self):
        """Single background task that receives ALL room events."""
        try:
            async for message in self._pubsub.listen():
                if message["type"] == "message":
                    try:
                        payload = json.loads(message["data"])
                        room_slug = payload.get("room_slug", "")
                        await self.broadcast_local(room_slug, payload)
                    except (json.JSONDecodeError, KeyError) as e:
                        logger.warning(f"PubSub parse error: {e}")
        except asyncio.CancelledError:
            logger.info("PubSub listener cancelled")
        except Exception as e:
            logger.error(f"PubSub listener crashed: {e}")
            # Auto-restart after brief delay
            await asyncio.sleep(1)
            self._listener_task = asyncio.create_task(self._shared_listener())

    def get_stats(self) -> dict:
        """Return connection statistics for monitoring."""
        total_ws = sum(len(conns) for conns in self.active_connections.values())
        return {
            "rooms": len(self.active_connections),
            "subscriptions": len(self._subscribed_rooms),
            "total_connections": total_ws,
        }


manager = ConnectionManager()
