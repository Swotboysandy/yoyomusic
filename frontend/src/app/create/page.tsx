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

export default function CreateRoomPage() {
    const router = useRouter();
    const [name, setName] = useState("");
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState("");

    const handleCreate = async () => {
        setLoading(true);
        setError("");
        try {
            const response = await api.post("/api/v1/rooms/", { name });
            const room = response.data;
            router.push(`/room/${room.id}`);
        } catch (err) {
            setError("Failed to create room. Please try again.");
            console.error(err);
        } finally {
            setLoading(false);
        }
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
                        <CardTitle className="text-2xl">Create a Room</CardTitle>
                        <CardDescription>Start a new listening session with friends.</CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-4">
                        <div className="space-y-2">
                            <Label htmlFor="room-name">Room Name</Label>
                            <Input
                                id="room-name"
                                placeholder="e.g. Chill Vibes 🎵"
                                value={name}
                                onChange={(e) => setName(e.target.value)}
                                className="h-11"
                            />
                        </div>
                        {error && <p className="text-sm font-medium text-destructive">{error}</p>}
                    </CardContent>
                    <CardFooter>
                        <Button onClick={handleCreate} disabled={loading || !name.trim()} className="w-full h-11 text-base">
                            {loading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                            {loading ? "Creating..." : "Create Room"}
                        </Button>
                    </CardFooter>
                </Card>
            </div>
        </div>
    );
}
