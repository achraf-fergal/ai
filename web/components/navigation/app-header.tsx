"use client";

import Link from "next/link";
import { Waves } from "lucide-react";

import { ThemeToggle } from "@/components/theme-toggle";
import { UserMenu } from "@/components/navigation/user-menu";
import type { DbUser } from "@/lib/db/queries";

export function AppHeader({ user }: { user: DbUser }) {
  return (
    <header className="sticky top-0 z-30 flex h-14 w-full items-center justify-between border-b bg-background/95 px-4 backdrop-blur supports-[backdrop-filter]:bg-background/80">
      <Link href="/app/audio-studio" className="flex items-center gap-2 text-foreground">
        <Waves className="h-5 w-5 text-primary" />
        <span className="font-semibold">Audio Studio</span>
      </Link>
      <div className="flex items-center gap-1 sm:gap-2">
        <ThemeToggle variant="ghost" size="icon" />
        <UserMenu user={user} />
      </div>
    </header>
  );
}
