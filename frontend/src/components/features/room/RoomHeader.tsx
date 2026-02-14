"use client"

import React from "react"
import { Copy, LogOut, Settings, Users } from "lucide-react"

import { Button } from "@/components/ui/button"
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogHeader,
    DialogTitle,
    DialogTrigger,
} from "@/components/ui/dialog"
import { useToast } from "@/hooks/use-toast"
import { cn } from "@/lib/utils"

interface RoomHeaderProps {
    roomName: string
    roomId: string
    memberCount: number
    className?: string
}

export function RoomHeader({ roomName, roomId, memberCount, className }: RoomHeaderProps) {
    const { toast } = useToast()

    const copyLink = () => {
        navigator.clipboard.writeText(`${window.location.origin}/room/${roomId}`)
        toast({
            title: "Link copied",
            description: "Room link copied to clipboard",
        })
    }

    return (
        <header className={cn("flex h-16 w-full items-center justify-between border-b px-4 lg:px-6 bg-background/95 backdrop-blur", className)}>
            <div className="flex items-center gap-4">
                <div className="flex flex-col">
                    <h1 className="text-lg font-bold leading-none tracking-tight">{roomName}</h1>
                    <div className="flex items-center gap-1 text-xs text-muted-foreground">
                        <span>ID: {roomId}</span>
                        <button
                            onClick={copyLink}
                            className="ml-1 rounded-sm p-0.5 hover:bg-muted focus:outline-none focus:ring-1 focus:ring-ring"
                        >
                            <Copy className="h-3 w-3" />
                            <span className="sr-only">Copy ID</span>
                        </button>
                    </div>
                </div>
            </div>

            <div className="flex items-center gap-2">
                <div className="hidden md:flex items-center gap-1.5 rounded-full bg-secondary px-3 py-1 text-xs font-medium text-secondary-foreground">
                    <Users className="h-3 w-3" />
                    <span>{memberCount}</span>
                </div>

                <Dialog>
                    <DialogTrigger asChild>
                        <Button variant="ghost" size="icon">
                            <Settings className="h-5 w-5" />
                            <span className="sr-only">Settings</span>
                        </Button>
                    </DialogTrigger>
                    <DialogContent>
                        <DialogHeader>
                            <DialogTitle>Room Settings</DialogTitle>
                            <DialogDescription>
                                Configure room preferences and permissions.
                            </DialogDescription>
                        </DialogHeader>
                        <div className="grid gap-4 py-4">
                            {/* Settings Content Placeholder */}
                            <p className="text-sm text-muted-foreground">Settings coming soon...</p>
                        </div>
                    </DialogContent>
                </Dialog>

                <Button variant="ghost" size="icon" className="text-destructive hover:bg-destructive/10 hover:text-destructive">
                    <LogOut className="h-5 w-5" />
                    <span className="sr-only">Leave Room</span>
                </Button>
            </div>
        </header>
    )
}
