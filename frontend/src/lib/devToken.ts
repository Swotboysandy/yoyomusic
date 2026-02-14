/**
 * DEV-ONLY: Auto-fetch a dev token from the backend on app init.
 * Replace with real auth flow in production.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export async function ensureDevToken(): Promise<string> {
    if (typeof window === 'undefined') return '';

    let token = localStorage.getItem('token');
    if (token) return token;

    try {
        const res = await fetch(`${API_BASE}/api/v1/auth/dev-token`);
        const data = await res.json();
        token = data.access_token;
        if (token) {
            localStorage.setItem('token', token);
        }
        return token || '';
    } catch (e) {
        console.error('Failed to fetch dev token:', e);
        return '';
    }
}