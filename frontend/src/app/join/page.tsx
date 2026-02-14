"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft, Loader2 } from "lucide-react";
import Link from "next/link";

import api from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardHeader, CardTitle, CardContent, CardDescription, CardFooter } from "@/components/ui/card";

export default function JoinRoomPage() {
    const router = useRouter();
    const [slug, setSlug] = useState("");
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState("");

    const handleJoin = async () => {
        if (!slug) return;
        setLoading(true);
        setError("");

        // Optional: Verify room exists before navigating
        // try {
        //     await api.get(`/api/v1/rooms/${slug}`);
        //     router.push(`/room/${slug}`);
        // } catch (e) {
        //     setError("Room not found.");
        // }
        // For now, direct navigation as in original code, but could be improved

        router.push(`/room/${slug}`);
        setLoading(false);
    };

    return (
        <div className="flex min-h-screen flex-col items-center justify-center p-4 bg-muted/30">
            <div className="w-full max-w-md space-y-4">
                <Link href="/">
                    <Button variant="ghost" className="pl-0 hover:bg-transparent hover:text-primary">
                        <ArrowLeft className="mr-2 h-4 w-4" />
                        Back to Home
                    </Button>
                </Link>

                <Card className="border-2 shadow-lg">
                    <CardHeader>
                        <CardTitle className="text-2xl">Join a Room</CardTitle>
                        <CardDescription>Enter the room code to join the party.</CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-4">
                        <div className="space-y-2">
                            <Label htmlFor="room-slug">Room Code</Label>
                            <Input
                                id="room-slug"
                                placeholder="e.g. ABCD-1234"
                                value={slug}
                                onChange={(e) => setSlug(e.target.value.toUpperCase())}
                                className="h-11 font-mono tracking-widest uppercase"
                            />
                        </div>
                        {error && <p className="text-sm font-medium text-destructive">{error}</p>}
                    </CardContent>
                    <CardFooter>
                        <Button onClick={handleJoin} disabled={loading || !slug.trim()} className="w-full h-11 text-base">
                            {loading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                            {loading ? "Joining..." : "Join Room"}
                        </Button>
                    </CardFooter>
                </Card>
            </div>
        </div>
    );
}
