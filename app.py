from flask import Flask, render_template, request, redirect, url_for
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask_sqlalchemy import SQLAlchemy
from threading import Lock
import yt_dlp
import uuid
import os
from datetime import datetime

app = Flask(__name__, static_folder='static', template_folder='templates')
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'yoyo-music-secret-2024')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///yoyomusic.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Models
class Room(db.Model):
    id = db.Column(db.String(8), primary_key=True)
    name = db.Column(db.String(30), nullable=False)
    password = db.Column(db.String(20), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_playing = db.Column(db.Boolean, default=True)
    playback_time = db.Column(db.Float, default=0.0)
    repeat_mode = db.Column(db.String(10), default='off') # 'off', 'one', 'all'
    shuffle_enabled = db.Column(db.Boolean, default=False)
    theme = db.Column(db.String(20), default='default')
    
    # We store the YT ID of the current song for easy access
    current_song_id = db.Column(db.String(20), nullable=True)
    current_song_title = db.Column(db.String(200), nullable=True)

    songs = db.relationship('Song', backref='room', lazy=True, cascade="all, delete-orphan")
    chat_messages = db.relationship('ChatMessage', backref='room', lazy=True, cascade="all, delete-orphan")

class Song(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    room_id = db.Column(db.String(8), db.ForeignKey('room.id'), nullable=False)
    yt_id = db.Column(db.String(20), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    channel = db.Column(db.String(100), nullable=True)
    added_by = db.Column(db.String(20), nullable=False)
    uuid = db.Column(db.String(36), nullable=False)
    order = db.Column(db.Integer, default=0)
    is_queued = db.Column(db.Boolean, default=True)

class ChatMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    room_id = db.Column(db.String(8), db.ForeignKey('room.id'), nullable=False)
    username = db.Column(db.String(20), nullable=False)
    message = db.Column(db.String(200), nullable=False)
    time = db.Column(db.String(5), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

socketio = SocketIO(app, cors_allowed_origins="*")

# Runtime state (Non-persistent real-time data)
active_rooms = {}  # room_id -> {users: {sid: username}, vote_skip: set()}
users = {}  # sid -> {username, room_id}
thread_lock = Lock()

with app.app_context():
    db.create_all()

def get_room_list():
    rooms = Room.query.all()
    return [{
        'id': r.id,
        'name': r.name,
        'has_password': r.password is not None,
        'user_count': len(active_rooms.get(r.id, {}).get('users', {})),
        'now_playing': r.current_song_title or 'Silent',
        'theme': r.theme
    } for r in rooms]

@app.route('/')
def lobby():
    return render_template('lobby.html')

@app.route('/room/<room_id>')
def room(room_id):
    room = Room.query.get(room_id)
    if not room:
        return redirect(url_for('lobby'))
    return render_template('room.html')

@socketio.on('get_rooms')
def handle_get_rooms():
    emit('room_list', get_room_list())

@socketio.on('create_room')
def handle_create_room(data):
    room_name = data.get('name', 'My Room').strip()[:30]
    password = data.get('password', '').strip() or None
    
    if not room_name:
        emit('room_error', 'Room name required')
        return
    
    room_id = str(uuid.uuid4())[:8]
    new_room = Room(id=room_id, name=room_name, password=password)
    db.session.add(new_room)
    db.session.commit()
    
    emit('room_created', {'id': room_id, 'name': room_name})
    socketio.emit('room_list', get_room_list())

@socketio.on('join_room')
def handle_join_room(data):
    room_id = data.get('room_id')
    username = data.get('username', 'Anonymous').strip()[:20]
    password = data.get('password', '')
    
    room = Room.query.get(room_id)
    if not room:
        emit('room_error', 'Room not found')
        return
    
    if room.password and room.password != password:
        emit('room_error', 'Incorrect password')
        return
    
    sid = request.sid
    if sid in users and users[sid].get('room_id'):
        leave_user_from_room(sid, users[sid]['room_id'])
    
    join_room(room_id)
    if room_id not in active_rooms:
        active_rooms[room_id] = {'users': {}, 'vote_skip': set(), 'host_sid': sid}
    
    active_rooms[room_id]['users'][sid] = username
    users[sid] = {'username': username, 'room_id': room_id, 'is_host': active_rooms[room_id]['host_sid'] == sid}
    
    # Calculate estimated playback time for better sync
    current_pos = room.playback_time
    if room.is_playing and 'last_sync' in active_rooms[room_id]:
        import time
        elapsed = time.time() - active_rooms[room_id]['last_sync']['ts']
        current_pos += elapsed

    emit('joined_room', {
        'room_id': room_id,
        'room_name': room.name,
        'has_password': room.password is not None,
        'is_host': users[sid]['is_host'],
        'theme': room.theme
    })
    
    # Send queue & current song
    queue = [{'id': s.yt_id, 'title': s.title, 'channel': s.channel, 'added_by': s.added_by, 'uuid': s.uuid} 
             for s in room.songs if s.is_queued]
    emit('queue_updated', queue, room=room_id)
    
    if room.current_song_id:
        emit('now_playing', {
            'id': room.current_song_id,
            'title': room.current_song_title,
            'start_at': current_pos,
            'is_playing': room.is_playing
        })
    
    # Send chat history
    history = [{
        'username': m.username,
        'message': m.message,
        'time': m.time,
        'sid': None # sid not preserved in DB
    } for m in room.chat_messages[-50:]]
    emit('chat_history', history)
    
    emit('status', f"{username} joined", room=room_id)
    
    # Emit updated user list with host info
    user_data = []
    for u_sid, u_name in active_rooms[room_id]['users'].items():
        user_data.append({
            'username': u_name,
            'is_host': active_rooms[room_id]['host_sid'] == u_sid,
            'sid': u_sid
        })
    socketio.emit('user_list', user_data, room=room_id)
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
    if room_id not in active_rooms:
        return
    
    room_state = active_rooms[room_id]
    username = room_state['users'].pop(sid, 'Unknown')
    room_state['vote_skip'].discard(sid)
    leave_room(room_id)
    
    if sid in users:
        users[sid]['room_id'] = None
    
    # Reassign host if needed
    if room_state.get('host_sid') == sid:
        if room_state['users']:
            new_host_sid = next(iter(room_state['users']))
            room_state['host_sid'] = new_host_sid
            if new_host_sid in users:
                users[new_host_sid]['is_host'] = True
        else:
            room_state['host_sid'] = None

    # Emit updated user list with host info
    user_data = []
    for u_sid, u_name in room_state['users'].items():
        user_data.append({
            'username': u_name,
            'is_host': room_state['host_sid'] == u_sid,
            'sid': u_sid
        })
    socketio.emit('user_list', user_data, room=room_id)
    emit('status', f"{username} left", room=room_id)
    
    if len(room_state['users']) == 0:
        del active_rooms[room_id]
    
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
def handle_add_to_queue(song_data):
    sid = request.sid
    if sid not in users or not users[sid].get('room_id'):
        return
    
    room_id = users[sid]['room_id']
    room = Room.query.get(room_id)
    if not room or not song_data or not song_data.get('id'):
        return
    
    # Calculate order
    last_song = Song.query.filter_by(room_id=room_id, is_queued=True).order_by(Song.order.desc()).first()
    order = (last_song.order + 1) if last_song else 0
    
    new_song = Song(
        room_id=room_id,
        yt_id=song_data['id'],
        title=song_data['title'],
        channel=song_data.get('channel', ''),
        added_by=users[sid]['username'],
        uuid=str(uuid.uuid4()),
        order=order,
        is_queued=True
    )
    db.session.add(new_song)
    db.session.commit()
    
    queue = [{'id': s.yt_id, 'title': s.title, 'channel': s.channel, 'added_by': s.added_by, 'uuid': s.uuid} 
             for s in room.songs if s.is_queued]
    emit('queue_updated', queue, room=room_id)
    emit('status', f"Added: {new_song.title[:30]}", room=room_id)
    
    if not room.current_song_id:
        play_next_song_in_room(room_id)

@socketio.on('remove_from_queue')
def handle_remove_from_queue(data):
    sid = request.sid
    if sid not in users or not users[sid].get('room_id'):
        return
    
    room_id = users[sid]['room_id']
    song_uuid = data.get('uuid')
    if not song_uuid:
        return
    
    song = Song.query.filter_by(room_id=room_id, uuid=song_uuid, is_queued=True).first()
    if song:
        db.session.delete(song)
        db.session.commit()
        
        room = Room.query.get(room_id)
        queue = [{'id': s.yt_id, 'title': s.title, 'channel': s.channel, 'added_by': s.added_by, 'uuid': s.uuid} 
                 for s in room.songs if s.is_queued]
        emit('queue_updated', queue, room=room_id)
        emit('status', "Removed from queue", room=room_id)

@socketio.on('send_message')
def handle_send_message(data):
    sid = request.sid
    if sid not in users or not users[sid].get('room_id'):
        return
    
    room_id = users[sid]['room_id']
    username = users[sid]['username']
    message = data.get('message', '').strip()[:200]
    
    if not message:
        return
        
    time_str = datetime.now().strftime('%H:%M')
    new_msg = ChatMessage(room_id=room_id, username=username, message=message, time=time_str)
    db.session.add(new_msg)
    db.session.commit()
    
    msg_data = {
        'username': username,
        'message': message,
        'time': time_str,
        'sid': sid
    }
    emit('new_message', msg_data, room=room_id)

@socketio.on('send_reaction')
def handle_reaction(data):
    sid = request.sid
    if sid not in users or not users[sid].get('room_id'):
        return
    
    room_id = users[sid]['room_id']
    emoji = data.get('emoji', '🔥')
    socketio.emit('new_reaction', {'userId': sid, 'emoji': emoji}, room=room_id)

@socketio.on('reorder_queue')
def handle_reorder_queue(data):
    sid = request.sid
    if sid not in users or not users[sid].get('room_id'):
        return
    
    room_id = users[sid]['room_id']
    if active_rooms.get(room_id, {}).get('host_sid') != sid:
        return # Only host can reorder
    
    uuids = data.get('uuids', [])
    if not uuids:
        return
    
    room = Room.query.get(room_id)
    if not room:
        return
        
    # Update orders in DB
    for index, song_uuid in enumerate(uuids):
        song = Song.query.filter_by(room_id=room_id, uuid=song_uuid).first()
        if song:
            song.order = index
    
    db.session.commit()
    
    queue = [{'id': s.yt_id, 'title': s.title, 'channel': s.channel, 'added_by': s.added_by, 'uuid': s.uuid} 
             for s in room.songs if s.is_queued]
    # Resort based on new order
    queue.sort(key=lambda x: uuids.index(x['uuid']) if x['uuid'] in uuids else 999)
    
    emit('queue_updated', queue, room=room_id)
    emit('status', "Queue reordered", room=room_id)

@socketio.on('toggle_shuffle')
def handle_toggle_shuffle():
    sid = request.sid
    if sid not in users or not users[sid].get('room_id'):
        return
    
    room_id = users[sid]['room_id']
    if active_rooms.get(room_id, {}).get('host_sid') != sid:
        return
    
    room = Room.query.get(room_id)
    if room:
        room.shuffle_enabled = not room.shuffle_enabled
        if room.shuffle_enabled:
            # Randomize order of all queued songs
            songs = Song.query.filter_by(room_id=room_id, is_queued=True).all()
            import random
            random.shuffle(songs)
            for i, s in enumerate(songs):
                s.order = i
        else:
            # Restore relative order (could be based on ID or something, but for now we leave as is)
            pass
        
        db.session.commit()
        queue = [{'id': s.yt_id, 'title': s.title, 'channel': s.channel, 'added_by': s.added_by, 'uuid': s.uuid} 
                 for s in room.songs if s.is_queued]
        socketio.emit('queue_updated', queue, room=room_id)
        socketio.emit('room_update', {'shuffle_enabled': room.shuffle_enabled, 'repeat_mode': room.repeat_mode}, room=room_id)
        socketio.emit('status', f"Shuffle {'ON' if room.shuffle_enabled else 'OFF'}", room=room_id)

@socketio.on('toggle_repeat')
def handle_toggle_repeat():
    sid = request.sid
    if sid not in users or not users[sid].get('room_id'):
        return
    
    room_id = users[sid]['room_id']
    if active_rooms.get(room_id, {}).get('host_sid') != sid:
        return
    
    room = Room.query.get(room_id)
    if room:
        modes = ['off', 'one', 'all']
        curr_idx = modes.index(room.repeat_mode)
        room.repeat_mode = modes[(curr_idx + 1) % len(modes)]
        db.session.commit()
        socketio.emit('room_update', {'shuffle_enabled': room.shuffle_enabled, 'repeat_mode': room.repeat_mode}, room=room_id)
        socketio.emit('status', f"Repeat: {room.repeat_mode.upper()}", room=room_id)

@socketio.on('set_theme')
def handle_set_theme(data):
    sid = request.sid
    if sid not in users or not users[sid].get('room_id'):
        return
    
    room_id = users[sid]['room_id']
    if active_rooms.get(room_id, {}).get('host_sid') != sid:
        return
    
    theme = data.get('theme', 'default')
    room = Room.query.get(room_id)
    if room:
        room.theme = theme
        db.session.commit()
        socketio.emit('room_update', {'theme': theme}, room=room_id)
        socketio.emit('status', f"Theme set to {theme}", room=room_id)

@socketio.on('seek_to')
def handle_seek_to(data):
    sid = request.sid
    if sid not in users or not users[sid].get('room_id'):
        return
    
    room_id = users[sid]['room_id']
    new_time = data.get('time', 0)
    
    room = Room.query.get(room_id)
    if room:
        room.playback_time = new_time
        db.session.commit()
        # Broadcast to all OTHER users (exclude sender)
        socketio.emit('sync_seek', {'time': new_time}, room=room_id, skip_sid=sid)

@socketio.on('vote_skip')
def handle_vote_skip():
    sid = request.sid
    if sid not in users or not users[sid].get('room_id'):
        return
    
    room_id = users[sid]['room_id']
    if room_id not in active_rooms:
        return
    
    state = active_rooms[room_id]
    is_host = state.get('host_sid') == sid
    state['vote_skip'].add(sid)
    
    votes_needed = max(1, len(state['users']) // 2 + 1)
    current_votes = len(state['vote_skip'])
    
    if is_host or current_votes >= votes_needed:
        socketio.emit('status', "Skipped", room=room_id)
        play_next_song_in_room(room_id)
    else:
        socketio.emit('status', f"Skip: {current_votes}/{votes_needed}", room=room_id)

@socketio.on('play_pause')
def handle_play_pause():
    sid = request.sid
    if sid not in users or not users[sid].get('room_id'):
        return
    
    room_id = users[sid]['room_id']
    room = Room.query.get(room_id)
    if room:
        room.is_playing = not room.is_playing
        db.session.commit()
        socketio.emit('toggle_play', {'is_playing': room.is_playing}, room=room_id)

@socketio.on('sync_time')
def handle_sync_time(data):
    sid = request.sid
    if sid not in users or not users[sid].get('room_id'):
        return
    
    room_id = users[sid]['room_id']
    room = Room.query.get(room_id)
    if room:
        room.playback_time = data.get('time', 0)
        room.is_playing = data.get('is_playing', True)
        db.session.commit()
        
        # Track last sync in memory for new joiners
        import time
        if room_id in active_rooms:
            active_rooms[room_id]['last_sync'] = {
                'time': room.playback_time,
                'ts': time.time()
            }
        
        # Broadcast sync to others so they don't fall behind
        socketio.emit('sync_update', {
            'time': room.playback_time,
            'is_playing': room.is_playing
        }, room=room_id, skip_sid=sid)

@socketio.on('song_ended')
def handle_song_ended():
    sid = request.sid
    if sid not in users or not users[sid].get('room_id'):
        return
    
    room_id = users[sid]['room_id']
    play_next_song_in_room(room_id)

def play_next_song_in_room(room_id):
    room = Room.query.get(room_id)
    if not room:
        return
    
    if room_id in active_rooms:
        active_rooms[room_id]['vote_skip'] = set()
    
    # Handle Repeat One
    if room.repeat_mode == 'one' and room.current_song_id:
        # Just reset time and play again
        room.playback_time = 0
        room.is_playing = True
        db.session.commit()
        socketio.emit('now_playing', {
            'id': room.current_song_id,
            'title': room.current_song_title,
            'start_at': 0,
            'is_playing': True
        }, room=room_id)
        return

    next_song = Song.query.filter_by(room_id=room_id, is_queued=True).order_by(Song.order.asc()).first()
    
    if not next_song and room.repeat_mode == 'all':
        # Re-queue all songs that were played
        all_songs = Song.query.filter_by(room_id=room_id).all()
        for s in all_songs:
            s.is_queued = True
        db.session.commit()
        next_song = Song.query.filter_by(room_id=room_id, is_queued=True).order_by(Song.order.asc()).first()

    if next_song:
        room.current_song_id = next_song.yt_id
        room.current_song_title = next_song.title
        room.playback_time = 0
        room.is_playing = True
        
        # Mark as not in queue
        next_song.is_queued = False
        db.session.commit()
        
        socketio.emit('now_playing', {
            'id': next_song.yt_id,
            'title': next_song.title,
            'start_at': 0,
            'is_playing': True
        }, room=room_id)
        
        queue = [{'id': s.yt_id, 'title': s.title, 'channel': s.channel, 'added_by': s.added_by, 'uuid': s.uuid} 
                 for s in room.songs if s.is_queued]
        socketio.emit('queue_updated', queue, room=room_id)
        socketio.emit('status', f"Playing: {next_song.title[:30]}", room=room_id)
    else:
        room.current_song_id = None
        room.current_song_title = None
        db.session.commit()
        socketio.emit('now_playing', None, room=room_id)
        socketio.emit('status', "Queue empty", room=room_id)

@app.route('/health')
def health():
    return {'status': 'ok', 'rooms': Room.query.count(), 'active_rooms': len(active_rooms)}

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    print(f"YoYo Music starting on port {port}...")
    socketio.run(app, host="0.0.0.0", port=port)
