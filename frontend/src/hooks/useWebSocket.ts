import { useEffect, useRef, useState } from 'react';

type WebSocketEvent = 'participant_joined' | 'participant_left' | 'playback_update';

interface WebSocketMessage {
    type: WebSocketEvent;
    data: any;
    room_slug: string;
}

export const useWebSocket = (slug: string) => {
    const [lastMessage, setLastMessage] = useState<WebSocketMessage | null>(null);
    const [isConnected, setIsConnected] = useState(false);
    const wsRef = useRef<WebSocket | null>(null);
    const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);

    useEffect(() => {
        if (!slug) return;

        const connect = () => {
            // Determine dynamic WS URL
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const host = process.env.NEXT_PUBLIC_API_URL
                ? process.env.NEXT_PUBLIC_API_URL.replace(/^http(s)?:\/\//, '')
                : 'localhost:8000';

            const url = `${protocol}//${host}/api/v1/ws/${slug}`;

            console.log("Connecting to WS:", url);
            const ws = new WebSocket(url);
            wsRef.current = ws;

            ws.onopen = () => {
                console.log('WebSocket Connected');
                setIsConnected(true);
                if (reconnectTimeoutRef.current) {
                    clearTimeout(reconnectTimeoutRef.current);
                    reconnectTimeoutRef.current = null;
                }
            };

            ws.onmessage = (event) => {
                try {
                    const message: WebSocketMessage = JSON.parse(event.data);
                    setLastMessage(message);
                } catch (e) {
                    console.error('WebSocket message parse error', e);
                }
            };

            ws.onclose = () => {
                console.log('WebSocket Disconnected');
                setIsConnected(false);
                // Reconnect logic
                reconnectTimeoutRef.current = setTimeout(() => {
                    console.log('Attempting Reconnect...');
                    connect();
                }, 3000); // Retry every 3s
            };

            ws.onerror = (error) => {
                console.error('WebSocket Error', error);
                ws.close();
            };
        };

        connect();

        return () => {
            if (wsRef.current) {
                wsRef.current.close();
            }
            if (reconnectTimeoutRef.current) {
                clearTimeout(reconnectTimeoutRef.current);
            }
        };
    }, [slug]);

    const sendMessage = (msg: any) => {
        if (wsRef.current && isConnected) {
            wsRef.current.send(JSON.stringify(msg));
        }
    };

    return { lastMessage, isConnected, sendMessage };
};
