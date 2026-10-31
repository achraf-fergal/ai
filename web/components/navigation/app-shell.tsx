"use client";

import { useState } from "react";

import { AppSidebar } from "@/components/navigation/Sidebar";
import { AppHeader } from "@/components/navigation/app-header";
import type { DbUser } from "@/lib/db/queries";

interface AppShellProps {
  user: DbUser;
  children: React.ReactNode;
}

export function AppShell({ user, children }: AppShellProps) {
  const [sidebarOpen, setSidebarOpen] = useState(true);

  return (
    <div className="flex min-h-screen w-full">
      <AppSidebar
        user={user}
        open={sidebarOpen}
        onToggle={() => setSidebarOpen((open) => !open)}
      />
      <div className="flex min-w-0 flex-1 flex-col">
        <AppHeader user={user} />
        <main className="flex-1">{children}</main>
      </div>
    </div>
  );
}
