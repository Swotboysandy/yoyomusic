"use client"

import React from "react"
import Image from "next/image"
import { Disc, Music2 } from "lucide-react"

import { usePlayerStore } from "@/store/usePlayerStore"
import { cn } from "@/lib/utils"

export function NowPlayingCard({ className }: { className?: string }) {
    const { currentSong } = usePlayerStore()

    if (!currentSong) {
        return (
            <div className={cn("flex flex-col items-center justify-center aspect-square rounded-xl border bg-muted/20 text-muted-foreground", className)}>
                <Music2 className="h-20 w-20 opacity-50 mb-4" />
                <p>No song playing</p>
            </div>
        )
    }

    return (
        <div className={cn("relative flex flex-col gap-6 w-full max-w-2xl mx-auto", className)}>
            <div className="relative aspect-square w-full overflow-hidden rounded-2xl shadow-2xl ring-1 ring-white/10">
                <Image
                    src={currentSong.thumbnail}
                    alt={currentSong.title}
                    fill
                    className="object-cover"
                />

                {/* Overlay with vinyl effect or visualizer placeholder */}
                <div className="absolute inset-0 bg-gradient-to-t from-black/60 to-transparent" />
            </div>

            <div className="flex flex-col items-center text-center space-y-2">
                <h2 className="text-3xl font-bold tracking-tight text-foreground sm:text-4xl">{currentSong.title}</h2>
                <p className="text-xl text-muted-foreground font-medium">{currentSong.artist}</p>
            </div>
        </div>
    )
}
