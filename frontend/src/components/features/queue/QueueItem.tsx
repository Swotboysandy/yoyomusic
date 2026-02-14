"use client"

import React from "react"
import Image from "next/image"
import { Draggable } from "@hello-pangea/dnd"
import { GripVertical, X, ThumbsUp } from "lucide-react"

import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import { Song } from "@/store/usePlayerStore"

interface QueueItemProps {
    song: Song
    index: number
    isHost?: boolean
    isCurrent?: boolean
    onVote?: (id: string) => void
    onRemove?: (id: string) => void
}

export function QueueItem({ song, index, isHost, isCurrent, onVote, onRemove }: QueueItemProps) {
    return (
        <Draggable draggableId={song.id} index={index} isDragDisabled={!isHost}>
            {(provided, snapshot) => (
                <div
                    ref={provided.innerRef}
                    {...provided.draggableProps}
                    className={cn(
                        "group flex items-center gap-3 rounded-md border p-2 mb-2 bg-card transition-colors hover:bg-accent/50",
                        snapshot.isDragging && "shadow-lg ring-2 ring-primary",
                        isCurrent && "border-primary/50 bg-primary/10"
                    )}
                >
                    {isHost && (
                        <div {...provided.dragHandleProps} className="cursor-grab text-muted-foreground hover:text-foreground">
                            <GripVertical className="h-4 w-4" />
                        </div>
                    )}

                    <div className="relative h-10 w-10 shrink-0 overflow-hidden rounded">
                        <Image src={song.thumbnail} alt={song.title} fill className="object-cover" />
                    </div>

                    <div className="flex-1 overflow-hidden">
                        <h4 className={cn("truncate text-sm font-medium", isCurrent && "text-primary")}>{song.title}</h4>
                        <p className="truncate text-xs text-muted-foreground">{song.artist}</p>
                    </div>

                    <div className="flex items-center gap-1">
                        <span className="text-xs text-muted-foreground tabular-nums">
                            {Math.floor(song.duration / 60)}:{Math.floor(song.duration % 60).toString().padStart(2, '0')}
                        </span>

                        {!isCurrent && (
                            <Button
                                variant="ghost"
                                size="icon"
                                className="h-8 w-8 text-muted-foreground hover:text-primary"
                                onClick={() => onVote?.(song.id)}
                            >
                                <ThumbsUp className="h-3 w-3" />
                            </Button>
                        )}

                        {isHost && !isCurrent && (
                            <Button
                                variant="ghost"
                                size="icon"
                                className="h-8 w-8 text-muted-foreground hover:text-destructive opacity-0 group-hover:opacity-100"
                                onClick={() => onRemove?.(song.id)}
                            >
                                <X className="h-4 w-4" />
                            </Button>
                        )}
                    </div>
                </div>
            )}
        </Draggable>
    )
}
