"use client";

import { useEffect } from "react";
import Link from "next/link";
import { Music2, Plus, Users } from "lucide-react";

import { Button } from "@/components/ui/button";
import { ensureDevToken } from "@/lib/devToken";

export default function Home() {
  useEffect(() => {
    ensureDevToken();
  }, []);

  return (
    <main className="flex min-h-screen flex-col items-center justify-center p-4 bg-background relative overflow-hidden">
      {/* Background Gradients */}
      <div className="absolute top-0 left-0 w-full h-full overflow-hidden -z-10">
        <div className="absolute top-[-10%] right-[-5%] w-[500px] h-[500px] rounded-full bg-primary/10 blur-[100px]" />
        <div className="absolute bottom-[-10%] left-[-5%] w-[500px] h-[500px] rounded-full bg-secondary/10 blur-[100px]" />
      </div>

      <div className="flex flex-col items-center text-center space-y-8 max-w-2xl animate-in fade-in slide-in-from-bottom-8 duration-700">
        <div className="flex items-center justify-center h-20 w-20 rounded-2xl bg-primary/10 text-primary mb-4">
          <Music2 className="h-10 w-10" />
        </div>

        <h1 className="text-5xl md:text-7xl font-bold tracking-tighter bg-clip-text text-transparent bg-gradient-to-br from-foreground to-muted-foreground">
          YoYoMusic
        </h1>

        <p className="text-xl text-muted-foreground max-w-md mx-auto">
          Listen to music with friends in real-time.
          Synchronized playback, collaborative queue, and chat.
        </p>

        <div className="flex flex-col sm:flex-row gap-4 w-full justify-center pt-8">
          <Link href="/create">
            <Button size="lg" className="h-12 px-8 text-base w-full sm:w-auto shadow-lg hover:shadow-primary/20 transition-all">
              <Plus className="mr-2 h-5 w-5" />
              Create Room
            </Button>
          </Link>
          <Link href="/join">
            <Button variant="outline" size="lg" className="h-12 px-8 text-base w-full sm:w-auto hover:bg-secondary/50">
              <Users className="mr-2 h-5 w-5" />
              Join Room
            </Button>
          </Link>
        </div>
      </div>

      <footer className="absolute bottom-8 text-sm text-muted-foreground">
        © 2024 YoYoMusic. Built for music lovers.
      </footer>
    </main>
  );
}
