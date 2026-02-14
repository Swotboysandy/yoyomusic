"use client"

import React from "react"
import { Crown } from "lucide-react"

import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import { ScrollArea } from "@/components/ui/scroll-area"
import { cn } from "@/lib/utils"

interface User {
    id: string
    name: string
    avatar?: string
    isHost?: boolean
}

interface MembersListProps {
    members: User[]
    className?: string
}

export function MembersList({ members, className }: MembersListProps) {
    return (
        <div className={cn("flex flex-col h-full", className)}>
            <div className="flex items-center justify-between px-4 py-2 border-b">
                <h3 className="text-sm font-semibold tracking-tight">Members</h3>
                <span className="text-xs text-muted-foreground">{members.length} online</span>
            </div>
            <ScrollArea className="flex-1">
                <div className="flex flex-col gap-1 p-2">
                    {members.map((member) => (
                        <div key={member.id} className="flex items-center gap-3 rounded-md p-2 hover:bg-accent/50 transition-colors">
                            <Avatar className="h-8 w-8">
                                <AvatarImage src={member.avatar} />
                                <AvatarFallback>{member.name.slice(0, 2).toUpperCase()}</AvatarFallback>
                            </Avatar>
                            <div className="flex flex-col flex-1 overflow-hidden">
                                <div className="flex items-center gap-1.5">
                                    <span className="truncate text-sm font-medium leading-none">{member.name}</span>
                                    {member.isHost && (
                                        <Crown className="h-3 w-3 text-yellow-500 fill-yellow-500" />
                                    )}
                                </div>
                            </div>
                        </div>
                    ))}
                </div>
            </ScrollArea>
        </div>
    )
}
