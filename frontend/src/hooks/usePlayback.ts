import { useState, useEffect, useRef } from 'react';

export interface PlaybackState {
    status: 'playing' | 'paused' | 'idle';
    current_song_id: string;
    position_ms: number;
    updated_at: number; // Server timestamp (UTC ms)
    speed: number;
}

export const usePlayback = (initialState: PlaybackState) => {
    const [status, setStatus] = useState<PlaybackState['status']>(initialState?.status || 'idle');
    const [progressMs, setProgressMs] = useState(initialState?.position_ms || 0);
    const [playbackState, setPlaybackState] = useState<PlaybackState>(initialState);

    const requestRef = useRef<number | undefined>(undefined);

    // Update internal state when props change (from WebSocket)
    useEffect(() => {
        if (initialState) {
            setPlaybackState(initialState);
            setStatus(initialState.status);
            if (initialState.status === 'paused' || initialState.status === 'idle') {
                setProgressMs(initialState.position_ms);
            }
        }
    }, [initialState]);

    const animate = () => {
        if (status === 'playing') {
            // Calculate current position based on server time
            // Assumption: Client clock is reasonably synced with Server clock
            // Formula: position = known_pos + (now - updated_at)
            const now = Date.now();
            // Using a simple efficient calculation
            // If clocks are skewed, there will be a constant offset.
            // Ideally, we'd calculate clock offset, but for Phase 4, we assume sync or ignore small drift.

            // To be safer without NTP sync, we can use local 'received_at' but server is authoritative.
            // Let's stick to the server authority model:
            const elapsed = now - playbackState.updated_at;
            const current = playbackState.position_ms + (elapsed * (playbackState.speed || 1));

            setProgressMs(current > 0 ? current : 0);

            requestRef.current = requestAnimationFrame(animate);
        }
    };

    useEffect(() => {
        if (status === 'playing') {
            requestRef.current = requestAnimationFrame(animate);
        } else {
            if (requestRef.current) cancelAnimationFrame(requestRef.current);
        }
        return () => {
            if (requestRef.current) cancelAnimationFrame(requestRef.current);
        };
    }, [status, playbackState]);

    return {
        status,
        progressMs
    };
};
