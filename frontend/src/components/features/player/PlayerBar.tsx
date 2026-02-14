"use client"

import React from "react"
import Image from "next/image"
import { Heart, ListMusic, Maximize2 } from "lucide-react"

import { Button } from "@/components/ui/button"
import { PlayerControls } from "./PlayerControls"
import { PlayerProgress } from "./PlayerProgress"
import { PlayerVolume } from "./PlayerVolume"
import { usePlayerStore } from "@/store/usePlayerStore"
import { cn } from "@/lib/utils"

export function PlayerBar({ className }: { className?: string }) {
    const { currentSong } = usePlayerStore()

    if (!currentSong) {
        // Option: Return null to hide, or show a placeholder
        // For now, let's show a placeholder state or just the bar disabled
        return (
            <div className={cn("fixed bottom-0 left-0 right-0 z-50 flex h-20 items-center justify-between border-t bg-background/95 px-4 backdrop-blur supports-[backdrop-filter]:bg-background/60", className)}>
                <div className="flex items-center gap-4">
                    <div className="h-14 w-14 rounded bg-muted/50 animate-pulse" />
                    <div className="space-y-2">
                        <div className="h-4 w-32 rounded bg-muted/50 animate-pulse" />
                        <div className="h-3 w-20 rounded bg-muted/50 animate-pulse" />
                    </div>
                </div>
                <div className="flex flex-col items-center gap-2">
                    <PlayerControls />
                </div>
                <div className="flex items-center gap-2">
                    <PlayerVolume />
                </div>
            </div>
        )
    }

    return (
        <div className={cn("fixed bottom-0 left-0 right-0 z-50 grid grid-cols-1 md:grid-cols-3 h-24 items-center border-t bg-background/95 px-4 backdrop-blur supports-[backdrop-filter]:bg-background/60", className)}>

            {/* Left: Song Info */}
            <div className="flex items-center gap-4 justify-start">
                <div className="relative h-14 w-14 overflow-hidden rounded-md shadow-sm">
                    <Image
                        src={currentSong.thumbnail}
                        alt={currentSong.title}
                        fill
                        className="object-cover"
                    />
                </div>
                <div className="flex flex-col justify-center overflow-hidden">
                    <h4 className="truncate text-sm font-semibold">{currentSong.title}</h4>
                    <p className="truncate text-xs text-muted-foreground">{currentSong.artist}</p>
                </div>
                <Button variant="ghost" size="icon" className="hidden sm:inline-flex text-muted-foreground hover:text-primary">
                    <Heart className="h-4 w-4" />
                </Button>
            </div>

            {/* Center: Controls & Progress */}
            <div className="flex flex-col items-center justify-center gap-1 w-full max-w-md mx-auto">
                <PlayerControls />
                <PlayerProgress className="w-full hidden md:flex" />
            </div>

            {/* Right: Volume & Extra Actions */}
            <div className="flex items-center justify-end gap-2 md:gap-4">
                <PlayerVolume className="hidden md:flex" />
                <Button variant="ghost" size="icon" className="text-muted-foreground hover:text-foreground">
                    <ListMusic className="h-5 w-5" />
                </Button>
                <Button variant="ghost" size="icon" className="hidden sm:inline-flex text-muted-foreground hover:text-foreground">
                    <Maximize2 className="h-4 w-4" />
                </Button>
            </div>

            {/* Mobile Progress Bar (Optional, can be overlaid at top of bar) */}
            <div className="md:hidden absolute top-0 left-0 w-full">
                <PlayerProgress className="h-1" />
            </div>
        </div>
    )
}
