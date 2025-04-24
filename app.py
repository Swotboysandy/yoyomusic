from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit, join_room, leave_room
from threading import Lock
import yt_dlp
import uuid
import os

app = Flask(__name__, static_folder='static', template_folder='templates')
app.config['SECRET_KEY'] = 'music-room'
socketio = SocketIO(app, cors_allowed_origins="*")

# Global variables
queue = []
current_song = None
users = {}
vote_skip = set()
thread_lock = Lock()

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('join')
def handle_join(data):
    username = data['username']
    sid = request.sid
    users[sid] = username
    emit('user_list', list(users.values()), broadcast=True)
    emit('status', f"{username} joined the session.", broadcast=True)

@socketio.on('disconnect')
def handle_disconnect():
    sid = request.sid
    if sid in users:
        left_user = users.pop(sid)
        emit('user_list', list(users.values()), broadcast=True)
        emit('status', f"{left_user} left the session.", broadcast=True)

@socketio.on('search')
def handle_search(query):
    results = []
    ydl_opts = {'quiet': True, 'extract_flat': True, 'force_generic_extractor': True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        search_results = ydl.extract_info(f"ytsearch5:{query}", download=False)['entries']
        for result in search_results:
            results.append({"id": result['id'], "title": result['title']})
    emit('search_results', results)

@socketio.on('add_to_queue')
def add_to_queue(song):
    global queue
    song['uuid'] = str(uuid.uuid4())
    queue.append(song)
    emit('queue_updated', queue, broadcast=True)
    if not current_song:
        play_next_song()

@socketio.on('vote_skip')
def vote_to_skip():
    sid = request.sid
    vote_skip.add(sid)
    if len(vote_skip) > len(users) / 2:
        play_next_song()

@socketio.on('play_pause')
def play_pause():
    emit('toggle_play', broadcast=True)


def play_next_song():
    global current_song, queue, vote_skip
    vote_skip = set()
    if queue:
        current_song = queue.pop(0)
        socketio.emit('now_playing', current_song)
        socketio.emit('queue_updated', queue)
    else:
        current_song = None
        socketio.emit('now_playing', None)


if __name__ == '__main__':
    import os
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host="0.0.0.0", port=port)

