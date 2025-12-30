from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit, join_room, leave_room
from threading import Lock
import yt_dlp
import uuid
import os
from datetime import datetime

app = Flask(__name__, static_folder='static', template_folder='templates')
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'yoyo-music-secret-2024')
socketio = SocketIO(app, cors_allowed_origins="*")

# Global state
rooms = {}  # room_id -> {name, password, users, queue, current_song, vote_skip, history}
users = {}  # sid -> {username, room_id}
thread_lock = Lock()

def create_room_data(name, password=None):
    return {
        'name': name,
        'password': password,  # None means no password
        'users': {},  # sid -> username
        'queue': [],
        'current_song': None,
        'playback_time': 0,  # Current playback position in seconds
        'is_playing': True,
        'vote_skip': set(),
        'history': [],
        'chat_history': []
    }

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('get_rooms')
def get_rooms():
    """Get list of available rooms"""
    room_list = []
    for room_id, room in rooms.items():
        room_list.append({
            'id': room_id,
            'name': room['name'],
            'has_password': room['password'] is not None,
            'user_count': len(room['users'])
        })
    emit('room_list', room_list)

@socketio.on('create_room')
def handle_create_room(data):
    """Create a new room"""
    room_name = data.get('name', 'My Room').strip()[:30]
    password = data.get('password', '').strip() or None
    
    if not room_name:
        emit('room_error', 'Room name required')
        return
    
    room_id = str(uuid.uuid4())[:8]
    rooms[room_id] = create_room_data(room_name, password)
    
    emit('room_created', {'id': room_id, 'name': room_name})
    # Broadcast updated room list to all users in lobby
    socketio.emit('room_list', get_room_list())

def get_room_list():
    return [{
        'id': rid,
        'name': r['name'],
        'has_password': r['password'] is not None,
        'user_count': len(r['users'])
    } for rid, r in rooms.items()]

@socketio.on('join_room')
def handle_join_room(data):
    """Join an existing room"""
    room_id = data.get('room_id')
    username = data.get('username', 'Anonymous').strip()[:20]
    password = data.get('password', '')
    
    if not room_id or room_id not in rooms:
        emit('room_error', 'Room not found')
        return
    
    room = rooms[room_id]
    
    # Check password
    if room['password'] and room['password'] != password:
        emit('room_error', 'Incorrect password')
        return
    
    sid = request.sid
    
    # Leave any existing room first
    if sid in users and users[sid].get('room_id'):
        old_room_id = users[sid]['room_id']
        leave_user_from_room(sid, old_room_id)
    
    # Join the room
    join_room(room_id)
    room['users'][sid] = username
    users[sid] = {'username': username, 'room_id': room_id}
    
    # Send room state to the joining user
    emit('joined_room', {
        'room_id': room_id,
        'room_name': room['name'],
        'has_password': room['password'] is not None
    })
    
    emit('user_list', list(room['users'].values()), room=room_id)
    emit('queue_updated', room['queue'], room=room_id)
    
    if room['current_song']:
        emit('now_playing', {
            **room['current_song'],
            'start_at': room['playback_time'],
            'is_playing': room['is_playing']
        })
    
    emit('chat_history', room['chat_history'])
    
    emit('status', f"{username} joined", room=room_id)
    
    # Update lobby room list
    socketio.emit('room_list', get_room_list())

@socketio.on('leave_current_room')
def handle_leave_room():
    """Leave the current room"""
    sid = request.sid
    if sid in users and users[sid].get('room_id'):
        room_id = users[sid]['room_id']
        leave_user_from_room(sid, room_id)
        emit('left_room')
        emit('room_list', get_room_list())

def leave_user_from_room(sid, room_id):
    """Helper to remove user from room"""
    if room_id not in rooms:
        return
    
    room = rooms[room_id]
    username = room['users'].pop(sid, 'Unknown')
    room['vote_skip'].discard(sid)
    leave_room(room_id)
    
    if sid in users:
        users[sid]['room_id'] = None
    
    emit('user_list', list(room['users'].values()), room=room_id)
    emit('status', f"{username} left", room=room_id)
    
    # Delete empty rooms
    if len(room['users']) == 0:
        del rooms[room_id]
        socketio.emit('room_list', get_room_list())

@socketio.on('disconnect')
def handle_disconnect():
    sid = request.sid
    if sid in users:
        room_id = users[sid].get('room_id')
        if room_id:
            leave_user_from_room(sid, room_id)
        del users[sid]
    socketio.emit('room_list', get_room_list())

@socketio.on('search')
def handle_search(query):
    """Fast search - just returns results"""
    if not query or not query.strip():
        emit('search_results', [])
        return
    
    results = []
    
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': True,
        'skip_download': True,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            search_results = ydl.extract_info(f"ytsearch10:{query}", download=False)
            entries = search_results.get('entries', [])
            
            for result in entries:
                if not result or not result.get('id'):
                    continue
                
                video_id = result.get('id')
                title = result.get('title', 'Unknown')
                
                skip_keywords = ['live stream', 'premiere', '24/7', 'radio']
                title_lower = title.lower()
                if any(kw in title_lower for kw in skip_keywords):
                    continue
                
                results.append({
                    "id": video_id,
                    "title": title,
                    "channel": result.get('channel', result.get('uploader', ''))
                })
        
        print(f"Search: '{query}' -> {len(results)} results")
        
    except Exception as e:
        print(f"Search error: {e}")
    
    emit('search_results', results)

@socketio.on('add_to_queue')
def add_to_queue(song):
    sid = request.sid
    if sid not in users or not users[sid].get('room_id'):
        return
    
    room_id = users[sid]['room_id']
    if room_id not in rooms:
        return
    
    room = rooms[room_id]
    
    if not song or not song.get('id'):
        return
    
    song['uuid'] = str(uuid.uuid4())
    song['added_by'] = room['users'].get(sid, 'Unknown')
    
    room['queue'].append(song)
    emit('queue_updated', room['queue'], room=room_id)
    emit('status', f"Added: {song.get('title', 'Song')[:30]}", room=room_id)
    
    if not room['current_song']:
        play_next_song_in_room(room_id)

@socketio.on('remove_from_queue')
def remove_from_queue(data):
    sid = request.sid
    if sid not in users or not users[sid].get('room_id'):
        return
    
    room_id = users[sid]['room_id']
    if room_id not in rooms:
        return
    
    song_uuid = data.get('uuid')
    if not song_uuid:
        return
        
    room = rooms[room_id]
    original_len = len(room['queue'])
    room['queue'] = [s for s in room['queue'] if s.get('uuid') != song_uuid]
    
    if len(room['queue']) != original_len:
        emit('queue_updated', room['queue'], room=room_id)
        emit('status', "Removed from queue", room=room_id)

@socketio.on('send_message')
def handle_message(data):
    sid = request.sid
    if sid not in users or not users[sid].get('room_id'):
        return
    
    room_id = users[sid]['room_id']
    username = users[sid]['username']
    message = data.get('message', '').strip()[:200]
    
    if not message:
        return
        
    msg_data = {
        'username': username,
        'message': message,
        'time': datetime.now().strftime('%H:%M'),
        'sid': sid
    }
    
    if room_id in rooms:
        rooms[room_id]['chat_history'].append(msg_data)
        if len(rooms[room_id]['chat_history']) > 100:
            rooms[room_id]['chat_history'].pop(0)
            
        emit('new_message', msg_data, room=room_id)

@socketio.on('vote_skip')
def vote_to_skip():
    sid = request.sid
    if sid not in users or not users[sid].get('room_id'):
        return
    
    room_id = users[sid]['room_id']
    if room_id not in rooms:
        return
    
    room = rooms[room_id]
    room['vote_skip'].add(sid)
    
    votes_needed = max(1, len(room['users']) // 2 + 1)
    current_votes = len(room['vote_skip'])
    
    if current_votes >= votes_needed:
        emit('status', "Skipped", room=room_id)
        play_next_song_in_room(room_id)
    else:
        emit('status', f"Skip: {current_votes}/{votes_needed}", room=room_id)

@socketio.on('play_pause')
def play_pause():
    sid = request.sid
    if sid not in users or not users[sid].get('room_id'):
        return
    
    room_id = users[sid]['room_id']
    if room_id in rooms:
        rooms[room_id]['is_playing'] = not rooms[room_id]['is_playing']
        socketio.emit('toggle_play', {'is_playing': rooms[room_id]['is_playing']}, room=room_id)

@socketio.on('sync_time')
def sync_time(data):
    """Update room's playback position (sent by clients periodically)"""
    sid = request.sid
    if sid not in users or not users[sid].get('room_id'):
        return
    
    room_id = users[sid]['room_id']
    if room_id in rooms:
        rooms[room_id]['playback_time'] = data.get('time', 0)
        rooms[room_id]['is_playing'] = data.get('is_playing', True)

@socketio.on('song_ended')
def song_ended():
    sid = request.sid
    if sid not in users or not users[sid].get('room_id'):
        return
    
    room_id = users[sid]['room_id']
    play_next_song_in_room(room_id)

def play_next_song_in_room(room_id):
    if room_id not in rooms:
        return
    
    room = rooms[room_id]
    room['vote_skip'] = set()
    
    if room['current_song']:
        room['history'].append(room['current_song'])
        if len(room['history']) > 50:
            room['history'].pop(0)
    
    if room['queue']:
        room['current_song'] = room['queue'].pop(0)
        socketio.emit('now_playing', room['current_song'], room=room_id)
        socketio.emit('queue_updated', room['queue'], room=room_id)
        socketio.emit('status', f"Playing: {room['current_song'].get('title', '')[:30]}", room=room_id)
    else:
        room['current_song'] = None
        socketio.emit('now_playing', None, room=room_id)
        socketio.emit('status', "Queue empty", room=room_id)

@app.route('/health')
def health():
    total_users = sum(len(r['users']) for r in rooms.values())
    return {'status': 'ok', 'rooms': len(rooms), 'users': total_users}

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    print(f"YoYo Music starting on port {port}...")
    socketio.run(app, host="0.0.0.0", port=port)
