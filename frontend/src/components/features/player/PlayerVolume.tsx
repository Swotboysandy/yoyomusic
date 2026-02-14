"use client"

import React, { useState } from "react"
import { Volume2, VolumeX } from "lucide-react"

import { Slider } from "@/components/ui/slider"
import { Button } from "@/components/ui/button"
import { usePlayerStore } from "@/store/usePlayerStore"
import { cn } from "@/lib/utils"

export function PlayerVolume({ className }: { className?: string }) {
    const { volume, setVolume } = usePlayerStore()
    const [prevVolume, setPrevVolume] = useState(volume)

    const handleVolumeChange = (value: number[]) => {
        setVolume(value[0])
    }

    const toggleMute = () => {
        if (volume === 0) {
            setVolume(prevVolume || 50)
        } else {
            setPrevVolume(volume)
            setVolume(0)
        }
    }

    return (
        <div className={cn("flex items-center gap-2", className)}>
            <Button variant="ghost" size="icon" onClick={toggleMute} className="h-8 w-8 text-muted-foreground hover:text-foreground">
                {volume === 0 ? <VolumeX className="h-4 w-4" /> : <Volume2 className="h-4 w-4" />}
            </Button>
            <Slider
                defaultValue={[volume]}
                value={[volume]}
                max={100}
                step={1}
                onValueChange={handleVolumeChange}
                className="w-24 cursor-pointer"
            />
        </div>
    )
}
