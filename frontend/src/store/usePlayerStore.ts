import { create } from 'zustand';

export interface Song {
    id: string;
    title: string;
    artist: string;
    thumbnail: string;
    duration: number; // in seconds
    url?: string;
    requested_by?: string;
}

export interface PlayerState {
    isPlaying: boolean;
    currentSong: Song | null;
    volume: number;
    currentTime: number;
    duration: number;
    queue: Song[];

    // Actions
    setIsPlaying: (isPlaying: boolean) => void;
    setCurrentSong: (song: Song | null) => void;
    setVolume: (volume: number) => void;
    setCurrentTime: (time: number) => void;
    setDuration: (duration: number) => void;
    setQueue: (queue: Song[]) => void;
    addToQueue: (song: Song) => void;
    removeFromQueue: (songId: string) => void;
    playNext: () => void;
    playPrevious: () => void;
}

export const usePlayerStore = create<PlayerState>((set) => ({
    isPlaying: false,
    currentSong: null,
    volume: 50,
    currentTime: 0,
    duration: 0,
    queue: [],

    setIsPlaying: (isPlaying) => set({ isPlaying }),
    setCurrentSong: (currentSong) => set({ currentSong }),
    setVolume: (volume) => set({ volume }),
    setCurrentTime: (currentTime) => set({ currentTime }),
    setDuration: (duration) => set({ duration }),
    setQueue: (queue) => set({ queue }),

    addToQueue: (song) => set((state) => ({ queue: [...state.queue, song] })),
    removeFromQueue: (songId) => set((state) => ({
        queue: state.queue.filter(s => s.id !== songId)
    })),

    playNext: () => set((state) => {
        if (state.queue.length === 0) return {};
        const nextSong = state.queue[0];
        return {
            currentSong: nextSong,
            queue: state.queue.slice(1),
            currentTime: 0,
            isPlaying: true
        };
    }),

    playPrevious: () => {
        // Implement history if needed
        return {};
    }
}));
