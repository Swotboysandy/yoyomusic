"use client"

import React from "react"
import Image from "next/image"
import { Play, Plus } from "lucide-react"

import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import { Song } from "@/store/usePlayerStore"

interface SongCardProps {
    song: Song
    onClick?: () => void
    className?: string
}

export function SongCard({ song, onClick, className }: SongCardProps) {
    return (
        <div
            className={cn(
                "group relative flex flex-col gap-2 rounded-md border bg-card p-3 transition-all hover:bg-accent/50 hover:shadow-md cursor-pointer",
                className
            )}
            onClick={onClick}
        >
            <div className="relative aspect-square w-full overflow-hidden rounded-md">
                <Image
                    src={song.thumbnail}
                    alt={song.title}
                    fill
                    className="object-cover transition-transform group-hover:scale-105"
                />
                <div className="absolute inset-0 flex items-center justify-center bg-black/40 opacity-0 transition-opacity group-hover:opacity-100">
                    <Button size="icon" className="h-10 w-10 rounded-full bg-primary text-primary-foreground shadow-lg">
                        <Play className="h-5 w-5 ml-0.5" />
                    </Button>
                </div>
            </div>

            <div className="space-y-1">
                <h4 className="truncate font-medium leading-none">{song.title}</h4>
                <p className="truncate text-xs text-muted-foreground">{song.artist}</p>
            </div>
        </div>
    )
}
