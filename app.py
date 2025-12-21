from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit
from threading import Lock
import yt_dlp
import uuid
import os
from datetime import datetime

app = Flask(__name__, static_folder='static', template_folder='templates')
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'yoyo-music-secret-2024')
socketio = SocketIO(app, cors_allowed_origins="*")

# Global state
queue = []
current_song = None
users = {}
vote_skip = set()
history = []
thread_lock = Lock()

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('join')
def handle_join(data):
    username = data.get('username', 'Anonymous')
    sid = request.sid
    users[sid] = username
    
    emit('user_list', list(users.values()), broadcast=True)
    emit('queue_updated', queue, broadcast=True)
    if current_song:
        emit('now_playing', current_song)
    
    emit('status', f"{username} joined", broadcast=True)

@socketio.on('disconnect')
def handle_disconnect():
    sid = request.sid
    if sid in users:
        left_user = users.pop(sid)
        vote_skip.discard(sid)
        emit('user_list', list(users.values()), broadcast=True)
        emit('status', f"{left_user} left", broadcast=True)

@socketio.on('search')
def handle_search(query):
    """Fast search - just returns results, let frontend handle playback errors"""
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
                
                # Skip obvious non-music content
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
    global queue
    
    if not song or not song.get('id'):
        return
    
    song['uuid'] = str(uuid.uuid4())
    song['added_by'] = users.get(request.sid, 'Unknown')
    
    queue.append(song)
    emit('queue_updated', queue, broadcast=True)
    emit('status', f"Added: {song.get('title', 'Song')[:30]}", broadcast=True)
    
    if not current_song:
        play_next_song()

@socketio.on('vote_skip')
def vote_to_skip():
    sid = request.sid
    vote_skip.add(sid)
    
    votes_needed = max(1, len(users) // 2 + 1)
    current_votes = len(vote_skip)
    
    if current_votes >= votes_needed:
        emit('status', "Skipped", broadcast=True)
        play_next_song()
    else:
        emit('status', f"Skip: {current_votes}/{votes_needed}", broadcast=True)

@socketio.on('play_pause')
def play_pause():
    emit('toggle_play', broadcast=True)

@socketio.on('song_ended')
def song_ended():
    play_next_song()

def play_next_song():
    global current_song, queue, vote_skip
    
    vote_skip = set()
    
    if current_song:
        history.append(current_song)
        if len(history) > 50:
            history.pop(0)
    
    if queue:
        current_song = queue.pop(0)
        socketio.emit('now_playing', current_song)
        socketio.emit('queue_updated', queue)
        socketio.emit('status', f"Playing: {current_song.get('title', '')[:30]}")
    else:
        current_song = None
        socketio.emit('now_playing', None)
        socketio.emit('status', "Queue empty")

@app.route('/health')
def health():
    return {'status': 'ok', 'users': len(users), 'queue': len(queue)}

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    print(f"YoYo Music starting on port {port}...")
    socketio.run(app, host="0.0.0.0", port=port)
