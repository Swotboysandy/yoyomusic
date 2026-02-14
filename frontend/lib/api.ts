import axios from 'axios';

const api = axios.create({
    baseURL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
    headers: {
        'Content-Type': 'application/json',
    },
});

api.interceptors.request.use((config) => {
    const token = typeof window !== 'undefined' ? localStorage.getItem('token') : null;
    if (token) {
        config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
});

export interface Room {
    id: string;
    name: string;
    host_id: string;
    is_active: boolean;
    created_at: string;
    settings: any;
}

export interface RoomState {
    meta: Room;
    playback: any;
    participant_count: number;
}

export const createRoom = async (name: string, settings?: any): Promise<Room> => {
    const response = await api.post('/api/v1/rooms/', { name, settings });
    return response.data;
};

export const joinRoom = async (slug: string, username: string): Promise<RoomState> => {
    const response = await api.post(`/api/v1/rooms/${slug}/join`, { username });
    return response.data;
};

export const getRoom = async (slug: string): Promise<RoomState> => {
    const response = await api.get(`/api/v1/rooms/${slug}`);
    return response.data;
};

// Player Controls
export const playMusic = async (slug: string, songId: string, positionMs: number = 0) => {
    return await api.post(`/api/v1/rooms/${slug}/player/play`, { song_id: songId, position_ms: positionMs });
};

export const pauseMusic = async (slug: string, positionMs: number) => {
    return await api.post(`/api/v1/rooms/${slug}/player/pause`, { position_ms: positionMs });
};

export const seekMusic = async (slug: string, positionMs: number) => {
    return await api.post(`/api/v1/rooms/${slug}/player/seek`, { position_ms: positionMs });
};

// Queue
export interface QueueSong {
    id: number;
    room_id: string;
    user_id: string;
    yt_id: string;
    title: string;
    duration: number | null;
    status: string;
    position: number;
    created_at: string;
}

export interface QueueState {
    now_playing: QueueSong | null;
    queue: QueueSong[];
}

export const addToQueue = async (slug: string, ytId: string, title: string, duration?: number) => {
    return await api.post(`/api/v1/rooms/${slug}/queue`, { yt_id: ytId, title, duration });
};

export const getQueue = async (slug: string): Promise<QueueState> => {
    const response = await api.get(`/api/v1/rooms/${slug}/queue`);
    return response.data;
};

export const hostSkip = async (slug: string) => {
    return await api.post(`/api/v1/rooms/${slug}/queue/skip`);
};

export const voteSkip = async (slug: string) => {
    return await api.post(`/api/v1/rooms/${slug}/queue/vote-skip`);
};

export const songEnded = async (slug: string) => {
    return await api.post(`/api/v1/rooms/${slug}/queue/song-ended`);
};

export default api;
