"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { useParams } from "next/navigation";
import { Loader2 } from "lucide-react";

import {
    getRoom, joinRoom,
    getQueue, getStreamUrl, songEnded,
    RoomState, QueueState,
    addToQueue,
    searchYouTube
} from "@/lib/api";
import { ensureDevToken } from "@/lib/devToken";
import { useWebSocket } from "@/hooks/useWebSocket";
import { usePlayerStore, Song } from "@/store/usePlayerStore";
import { useToast } from "@/hooks/use-toast";

// Components
import { RoomHeader } from "@/components/features/room/RoomHeader";
import { MembersList } from "@/components/features/room/MembersList";
import { NowPlayingCard } from "@/components/features/room/NowPlayingCard";
import { QueueList } from "@/components/features/queue/QueueList";
import { SearchPanel } from "@/components/features/common/SearchPanel";
import { PlayerBar } from "@/components/features/player/PlayerBar";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";

export default function RoomPage() {
    const params = useParams();
    const slug = params.slug as string;
    const { toast } = useToast();

    // Local State
    const [roomState, setRoomState] = useState<RoomState | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");
    const audioRef = useRef<HTMLAudioElement>(null);

    // Store Access
    const {
        setIsPlaying, setCurrentSong, setQueue, setDuration, setCurrentTime,
        queue
    } = usePlayerStore();

    // WebSocket
    const { lastMessage } = useWebSocket(slug);

    // Initial Fetch & Setup
    useEffect(() => {
        const init = async () => {
            try {
                await ensureDevToken();
                try { await joinRoom(slug, "Guest"); } catch { }

                const roomData = await getRoom(slug);
                setRoomState(roomData);

                const queueData = await getQueue(slug);
                syncQueueState(queueData);

            } catch (err) {
                setError("Failed to load room.");
                console.error(err);
            } finally {
                setLoading(false);
            }
        };
        if (slug) init();
    }, [slug]);

    // WebSocket Handling
    useEffect(() => {
        if (!lastMessage) return;

        switch (lastMessage.type) {
            case 'participant_joined':
            case 'participant_left':
                if (roomState) {
                    setRoomState({ ...roomState, participant_count: lastMessage.data.count });
                }
                break;
            case 'playback_update':
                handlePlaybackUpdate(lastMessage.data);
                break;
            case 'queue_update':
                syncQueueState(lastMessage.data);
                break;
        }
    }, [lastMessage]);

    // Helper: Sync Queue/Store
    const syncQueueState = (q: QueueState) => {
        // Map API queue to Store Song type
        const mappedQueue: Song[] = q.queue.map((item: any) => ({
            id: item.id || item.yt_id,
            title: item.title,
            artist: item.channel || "Unknown Artist",
            thumbnail: item.thumbnail || "/placeholder.jpg",
            duration: item.duration ? item.duration / 1000 : 0,
            requested_by: item.requested_by
        }));

        setQueue(mappedQueue);

        if (q.now_playing) {
            const current: Song = {
                id: q.now_playing.yt_id,
                title: q.now_playing.title,
                artist: q.now_playing.channel || "Unknown Artist",
                thumbnail: q.now_playing.thumbnail || "/placeholder.jpg",
                duration: q.now_playing.duration ? q.now_playing.duration / 1000 : 0,
            };
            setCurrentSong(current);
            setDuration(current.duration);

            if (q.now_playing.stream_url) {
                playAudio(q.now_playing.stream_url);
            }
        } else {
            setCurrentSong(null);
            setIsPlaying(false);
        }
    };

    const handlePlaybackUpdate = (data: any) => {
        if (data.status === 'playing' && data.stream_url) {
            if (audioRef.current && audioRef.current.src !== data.stream_url) {
                playAudio(data.stream_url);
            } else if (audioRef.current?.paused) {
                audioRef.current.play().catch(console.error);
            }
            setIsPlaying(true);
        } else if (data.status === 'paused' || data.status === 'idle') {
            audioRef.current?.pause();
            setIsPlaying(false);
        }
    }

    const playAudio = useCallback((url: string) => {
        if (!audioRef.current) return;
        if (audioRef.current.src === url && !audioRef.current.paused) return; // Already playing

        audioRef.current.src = url;
        audioRef.current.load();
        audioRef.current.play()
            .then(() => setIsPlaying(true))
            .catch(err => {
                console.warn("Autoplay prevented:", err);
                setIsPlaying(false);
            });
    }, []);

    const onAudioEnded = async () => {
        setIsPlaying(false);
        try { await songEnded(slug); } catch { }
    };

    const onAudioError = async () => {
        console.error("Audio error, attempting refresh...");
        const storeState = usePlayerStore.getState();
        if (storeState.currentSong) {
            try {
                const url = await getStreamUrl(storeState.currentSong.id);
                playAudio(url);
            } catch {
                toast({ variant: "destructive", title: "Playback Error", description: "Failed to load stream." });
            }
        }
    };

    // Search Handler for SearchPanel
    const handleSearch = async (query: string): Promise<Song[]> => {
        try {
            const results = await searchYouTube(query);
            return results.map(r => ({
                id: r.video_id,
                title: r.title,
                artist: r.channel || "Unknown",
                thumbnail: r.thumbnail,
                duration: r.duration_s
            }));
        } catch (error) {
            console.error(error);
            toast({ variant: "destructive", title: "Search failed" });
            return [];
        }
    };

    if (loading) return <div className="flex h-screen items-center justify-center"><Loader2 className="animate-spin h-8 w-8 text-primary" /></div>;
    if (error || !roomState) return <div className="flex h-screen items-center justify-center flex-col gap-4 text-destructive"><h1>Error</h1><p>{error}</p></div>;

    return (
        <div className="flex flex-col h-screen bg-background overflow-hidden">
            {/* Audio Element */}
            <audio
                ref={audioRef}
                onTimeUpdate={() => setCurrentTime(audioRef.current?.currentTime || 0)}
                onEnded={onAudioEnded}
                onError={onAudioError}
                onPlay={() => setIsPlaying(true)}
                onPause={() => setIsPlaying(false)}
                className="hidden"
            />

            {/* Header */}
            <RoomHeader
                roomName={roomState.meta.name}
                roomId={roomState.meta.id}
                memberCount={roomState.participant_count}
            />

            {/* Main Content Area */}
            <div className="flex-1 flex overflow-hidden">

                {/* Left Column (Desktop): Queue & Search */}
                <div className="hidden lg:flex w-1/4 min-w-[300px] border-r flex-col bg-muted/10">
                    <Tabs defaultValue="queue" className="flex-1 flex flex-col">
                        <div className="px-4 py-2 border-b">
                            <TabsList className="w-full grid grid-cols-2">
                                <TabsTrigger value="queue">Queue</TabsTrigger>
                                <TabsTrigger value="search">Search</TabsTrigger>
                            </TabsList>
                        </div>
                        <TabsContent value="queue" className="flex-1 overflow-hidden m-0 p-0">
                            <QueueList className="h-full px-4 py-2" />
                        </TabsContent>
                        <TabsContent value="search" className="flex-1 overflow-hidden m-0 p-0">
                            <SearchPanel className="h-full" onSearch={handleSearch} />
                        </TabsContent>
                    </Tabs>
                </div>

                {/* Center Column: Now Playing (Visualizer) */}
                <div className="flex-1 flex flex-col items-center justify-center p-6 relative overflow-hidden">
                    {/* Background blur effect */}
                    <div className="absolute inset-0 bg-gradient-to-br from-primary/5 to-secondary/5 -z-10" />
                    <NowPlayingCard />
                </div>

                {/* Right Column (Desktop): Members / Chat */}
                <div className="hidden lg:flex w-1/4 min-w-[250px] border-l flex-col bg-muted/10">
                    <MembersList members={[]} className="h-full" />
                </div>
            </div>

            {/* Sticky Player Bar */}
            <PlayerBar />

            {/* Mobile Navigation / Sheets (if needed) */}
            <div className="lg:hidden absolute bottom-24 right-4 flex flex-col gap-2">
                {/* Mobile Queue/Search Trigger */}
                <Sheet>
                    <SheetTrigger asChild>
                        <Button size="icon" className="rounded-full shadow-lg h-12 w-12">
                            <Loader2 className="h-6 w-6" /> {/* Placeholder icon */}
                        </Button>
                    </SheetTrigger>
                    <SheetContent side="bottom" className="h-[80vh]">
                        <Tabs defaultValue="queue" className="h-full flex flex-col">
                            <TabsList className="w-full grid grid-cols-2">
                                <TabsTrigger value="queue">Queue</TabsTrigger>
                                <TabsTrigger value="search">Search</TabsTrigger>
                            </TabsList>
                            <TabsContent value="queue" className="flex-1 overflow-hidden"><QueueList /></TabsContent>
                            <TabsContent value="search" className="flex-1 overflow-hidden"><SearchPanel onSearch={handleSearch} /></TabsContent>
                        </Tabs>
                    </SheetContent>
                </Sheet>
            </div>
        </div>
    );
}
