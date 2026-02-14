"use client"

import React, { useEffect, useState } from "react"
import { Slider } from "@/components/ui/slider"
import { usePlayerStore } from "@/store/usePlayerStore"
import { cn } from "@/lib/utils"

function formatTime(seconds: number) {
    const mins = Math.floor(seconds / 60)
    const secs = Math.floor(seconds % 60)
    return `${mins}:${secs.toString().padStart(2, "0")}`
}

export function PlayerProgress({ className }: { className?: string }) {
    const { currentTime, duration, setCurrentTime } = usePlayerStore()
    const [localTime, setLocalTime] = useState(currentTime)
    const [isDragging, setIsDragging] = useState(false)

    useEffect(() => {
        if (!isDragging) {
            setLocalTime(currentTime)
        }
    }, [currentTime, isDragging])

    const handleSeek = (value: number[]) => {
        setLocalTime(value[0])
    }

    const handleCommit = (value: number[]) => {
        setIsDragging(false)
        setCurrentTime(value[0])
        // Todo: Emit seek event
    }

    return (
        <div className={cn("flex w-full items-center gap-2 text-xs text-muted-foreground", className)}>
            <span className="w-10 text-right">{formatTime(localTime)}</span>
            <Slider
                value={[localTime]}
                max={duration > 0 ? duration : 100}
                step={1}
                onValueChange={handleSeek}
                onValueCommit={handleCommit}
                onPointerDown={() => setIsDragging(true)}
                className="cursor-pointer"
            />
            <span className="w-10">{formatTime(duration)}</span>
        </div>
    )
}
