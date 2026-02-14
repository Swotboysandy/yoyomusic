"use client"

import React from "react"
import { Play, Pause, SkipBack, SkipForward, Shuffle, Repeat } from "lucide-react"

import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import { usePlayerStore } from "@/store/usePlayerStore"

export function PlayerControls({ className }: { className?: string }) {
    const { isPlaying, setIsPlaying, playNext, playPrevious } = usePlayerStore()

    const togglePlay = () => {
        setIsPlaying(!isPlaying)
        // Todo: Emit socket event
    }

    return (
        <div className={cn("flex items-center gap-2", className)}>
            <Button variant="ghost" size="icon" className="text-muted-foreground hover:text-foreground">
                <Shuffle className="h-4 w-4" />
            </Button>
            <Button variant="ghost" size="icon" onClick={playPrevious} className="text-muted-foreground hover:text-foreground">
                <SkipBack className="h-5 w-5" />
            </Button>
            <Button size="icon" className="h-10 w-10 rounded-full" onClick={togglePlay}>
                {isPlaying ? <Pause className="h-5 w-5" /> : <Play className="h-5 w-5 ml-0.5" />}
            </Button>
            <Button variant="ghost" size="icon" onClick={playNext} className="text-muted-foreground hover:text-foreground">
                <SkipForward className="h-5 w-5" />
            </Button>
            <Button variant="ghost" size="icon" className="text-muted-foreground hover:text-foreground">
                <Repeat className="h-4 w-4" />
            </Button>
        </div>
    )
}
