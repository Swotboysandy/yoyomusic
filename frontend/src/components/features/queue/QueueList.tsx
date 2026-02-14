"use client"

import React, { useEffect, useState } from "react"
import { DragDropContext, Droppable, DropResult } from "@hello-pangea/dnd"

import { usePlayerStore, Song } from "@/store/usePlayerStore"
import { QueueItem } from "./QueueItem"
import { ScrollArea } from "@/components/ui/scroll-area"

// StrictModeDroppable needed for React 18 strict mode compatibility with hello-pangea/dnd
export const StrictModeDroppable = ({ children, ...props }: any) => {
    const [enabled, setEnabled] = useState(false);
    useEffect(() => {
        const animation = requestAnimationFrame(() => setEnabled(true));
        return () => {
            cancelAnimationFrame(animation);
            setEnabled(false);
        };
    }, []);
    if (!enabled) {
        return null;
    }
    return <Droppable {...props}>{children}</Droppable>;
};


export function QueueList({ className }: { className?: string }) {
    const { queue, setQueue, currentSong } = usePlayerStore()
    const isHost = true; // Placeholder

    const handleVote = async (songId: string) => {
        // console.log("Voting for", songId)
        // await api.vote(songId)
    }

    const handleRemove = async (songId: string) => {
        // console.log("Removing", songId)
        // await api.removeFromQueue(songId)
    }

    const onDragEnd = (result: DropResult) => {
        if (!result.destination) return

        const items = Array.from(queue)
        const [reorderedItem] = items.splice(result.source.index, 1)
        items.splice(result.destination.index, 0, reorderedItem)

        setQueue(items)
        // Todo: Emit socket event for reorder
    }

    return (
        <div className={className}>
            <h3 className="mb-4 text-lg font-semibold tracking-tight px-1">Up Next</h3>
            <DragDropContext onDragEnd={onDragEnd}>
                <StrictModeDroppable droppableId="queue">
                    {(provided: any) => (
                        <ScrollArea className="h-[calc(100vh-12rem)] pr-4">
                            <div {...provided.droppableProps} ref={provided.innerRef}>
                                {currentSong && (
                                    <div className="mb-4">
                                        <div className="text-xs font-medium text-muted-foreground uppercase mb-2 px-1">Now Playing</div>
                                        <QueueItem song={currentSong} index={-1} isHost={false} isCurrent={true} />
                                    </div>
                                )}

                                <div className="text-xs font-medium text-muted-foreground uppercase mb-2 px-1">Queue</div>
                                {queue.map((song, index) => (
                                    <QueueItem
                                        key={song.id}
                                        song={song}
                                        index={index}
                                        isHost={isHost}
                                        onVote={handleVote}
                                        onRemove={handleRemove}
                                    />
                                ))}
                                {queue.length === 0 && (
                                    <div className="py-8 text-center text-sm text-muted-foreground border border-dashed rounded-md">
                                        No songs in queue. Add some!
                                    </div>
                                )}
                                {provided.placeholder}
                            </div>
                        </ScrollArea>
                    )}
                </StrictModeDroppable>
            </DragDropContext>
        </div>
    )
}
