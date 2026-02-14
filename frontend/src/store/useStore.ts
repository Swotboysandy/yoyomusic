import { create } from 'zustand';

interface User {
    id: string;
    username: string;
}

interface AppState {
    user: User | null;
    setUser: (user: User | null) => void;
    token: string | null;
    setToken: (token: string | null) => void;
    isLoading: boolean;
    setIsLoading: (loading: boolean) => void;
}

export const useStore = create<AppState>((set) => ({
    user: null,
    setUser: (user) => set({ user }),
    token: null,
    setToken: (token) => {
        if (typeof window !== 'undefined') {
            if (token) localStorage.setItem('token', token);
            else localStorage.removeItem('token');
        }
        set({ token });
    },
    isLoading: false,
    setIsLoading: (isLoading) => set({ isLoading }),
}));
