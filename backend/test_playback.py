import asyncio
import aiohttp
import websockets
import json
from datetime import datetime, timedelta
from jose import jwt

# Hardcoded from .env or default
SECRET_KEY = "replace_this_with_a_secure_random_string" 
ALGORITHM = "HS256"

BASE_URL = "http://127.0.0.1:8000/api/v1"
WS_URL = "ws://127.0.0.1:8000/api/v1/ws"

def create_test_token():
    expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode = {"exp": expire, "sub": "test@example.com"}
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def test_playback_flow():
    token = create_test_token()
    headers = {"Authorization": f"Bearer {token}"}
    
    async with aiohttp.ClientSession() as session:
        # 1. Create Room
        print("Creating Room...")
        async with session.post(f"{BASE_URL}/rooms/", json={"name": "Playback Test"}, headers=headers) as resp:
            if resp.status != 200:
                print(f"Failed to create room: {await resp.text()}")
                return
            room = await resp.json()
            slug = room["id"]
            print(f"Room Created: {slug}")

        # 2. Connect WS
        print(f"Connecting to WS: {WS_URL}/{slug}")
        # WS might not support headers in browser JS easily, but websockets lib does.
        # Our WS endpoint doesn't enforce auth YET (commented out).
        async with websockets.connect(f"{WS_URL}/{slug}") as websocket:
            print("WS Connected")
            
            # 3. Play Music
            print("Sending Play Command...")
            play_payload = {"song_id": "test-song", "position_ms": 0}
            async with session.post(f"{BASE_URL}/rooms/{slug}/player/play", json=play_payload, headers=headers) as resp:
                print(f"Play Resp: {resp.status}")
                if resp.status != 200:
                   print(await resp.text())
                assert resp.status == 200

            # 4. Wait for WS Update (Playing)
            print("Waiting for WS Playing Event...")
            while True:
                msg = await websocket.recv()
                data = json.loads(msg)
                if data['type'] == 'playback_update':
                    print(f"Received Update: {data['data']['status']}")
                    if data['data']['status'] == 'playing':
                        print("SUCCESS: State is Playing")
                        break
            
            # 5. Pause Music
            await asyncio.sleep(1)
            print("Sending Pause Command...")
            pause_payload = {"position_ms": 1000}
            async with session.post(f"{BASE_URL}/rooms/{slug}/player/pause", json=pause_payload, headers=headers) as resp:
                print(f"Pause Resp: {resp.status}")
                assert resp.status == 200

            # 6. Wait for WS Update (Paused)
            print("Waiting for WS Paused Event...")
            while True:
                msg = await websocket.recv()
                data = json.loads(msg)
                if data['type'] == 'playback_update':
                    print(f"Received Update: {data['data']['status']}")
                    if data['data']['status'] == 'paused':
                        print("SUCCESS: State is Paused")
                        break
    
    print("Test Complete!")

if __name__ == "__main__":
    asyncio.run(test_playback_flow())
