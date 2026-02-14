"use client"

import React, { useState, useEffect } from "react"
import { Search, Loader2 } from "lucide-react"

import { Input } from "@/components/ui/input"
import { ScrollArea } from "@/components/ui/scroll-area"
import { SongCard } from "@/components/features/room/SongCard"
import { usePlayerStore, Song } from "@/store/usePlayerStore"
import { useToast } from "@/hooks/use-toast"
import { cn } from "@/lib/utils"

// Mock search function type
type SearchFunction = (query: string) => Promise<Song[]>

interface SearchPanelProps {
    className?: string
    onSearch?: SearchFunction // Optional prop if we want to pass a search handler
}

export function SearchPanel({ className, onSearch }: SearchPanelProps) {
    const [query, setQuery] = useState("")
    const [results, setResults] = useState<Song[]>([])
    const [isLoading, setIsLoading] = useState(false)
    const { addToQueue } = usePlayerStore()
    const { toast } = useToast()

    // Debounce logic could be added here
    useEffect(() => {
        const timer = setTimeout(() => {
            if (query.trim().length > 2) {
                performSearch(query)
            }
        }, 500)
        return () => clearTimeout(timer)
    }, [query])

    const performSearch = async (q: string) => {
        setIsLoading(true)
        try {
            // Mock API or actual API call
            // await new Promise(resolve => setTimeout(resolve, 1000))
            // setResults([...mockResults])
            if (onSearch) {
                const data = await onSearch(q)
                setResults(data)
            } else {
                // Fallback mock
                console.log("Searching for:", q)
                // For demo purposes, we can't fetch real data without backend
            }
        } catch (error) {
            console.error(error)
        } finally {
            setIsLoading(false)
        }
    }

    const handleAdd = (song: Song) => {
        addToQueue(song)
        toast({
            title: "Added to queue",
            description: `${song.title} has been added to the queue.`
        })
    }

    return (
        <div className={cn("flex flex-col h-full bg-background/50 backdrop-blur", className)}>
            <div className="p-4 border-b">
                <div className="relative">
                    <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                    <Input
                        placeholder="Search for songs..."
                        className="pl-9"
                        value={query}
                        onChange={(e) => setQuery(e.target.value)}
                    />
                </div>
            </div>

            <ScrollArea className="flex-1">
                <div className="grid grid-cols-1 p-4 gap-2">
                    {isLoading && (
                        <div className="flex items-center justify-center py-8">
                            <Loader2 className="h-6 w-6 animate-spin text-primary" />
                        </div>
                    )}

                    {!isLoading && results.length === 0 && query.length > 2 && (
                        <div className="text-center text-sm text-muted-foreground py-8">
                            No results found.
                        </div>
                    )}

                    {!isLoading && results.map((song) => (
                        <SongCard
                            key={song.id}
                            song={song}
                            onClick={() => handleAdd(song)}
                        />
                    ))}
                </div>
            </ScrollArea>
        </div>
    )
}
