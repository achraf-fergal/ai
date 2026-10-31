"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { FolderOpen, Menu, Mic, Settings, Star, Trash2, Upload, Waves } from "lucide-react";

import { Button } from "@/components/ui/button";
import { LogoutButton } from "@/components/navigation/logout-button";
import { cn } from "@/lib/utils";
import type { DbUser } from "@/lib/db/queries";

const NAV_ITEMS = [
  { href: "/app/audio-studio", label: "Audio Studio", icon: Waves },
  { href: "/app/voice-generator", label: "Voice Generator", icon: Mic },
  { href: "/app/projects", label: "Audio Library", icon: FolderOpen },
  { href: "/app/favorites", label: "Favorites", icon: Star },
  { href: "/app/uploads", label: "Uploaded Audio", icon: Upload },
  { href: "/app/trash", label: "Trash", icon: Trash2 },
  { href: "/app/settings", label: "Settings", icon: Settings },
] as const;

interface AppSidebarProps {
  user: DbUser;
  open: boolean;
  onToggle: () => void;
}

export function AppSidebar({ user, open, onToggle }: AppSidebarProps) {
  const pathname = usePathname();
  const collapsed = !open;

  return (
    <aside
      className={cn(
        "sticky top-0 flex shrink-0 flex-col border-r bg-background transition-[width] duration-200 ease-in-out",
        collapsed ? "w-0 md:w-16" : "w-16 md:w-64"
      )}
      style={{ height: "100vh", maxHeight: "100vh" }}
    >
      <div className="flex items-center justify-between gap-2 overflow-hidden p-3">
        {!collapsed && (
          <Link href="/app/audio-studio" className="hidden truncate font-semibold md:block">
            Audio Studio
          </Link>
        )}
        <Button type="button" variant="ghost" size="icon" onClick={onToggle} aria-label="Toggle sidebar" className="h-9 w-9 shrink-0">
          <Menu className="h-5 w-5" />
        </Button>
      </div>

      <nav className="flex flex-1 flex-col gap-1 overflow-y-auto p-3">
        {NAV_ITEMS.map(({ href, label, icon: Icon }) => {
          const active = pathname === href || (href !== "/app/audio-studio" && pathname.startsWith(`${href}/`));
          return (
            <Button
              key={href}
              variant="ghost"
              size="sm"
              asChild
              className={cn(
                "h-9 w-full justify-center gap-3 px-3 md:justify-start",
                collapsed && "md:justify-center md:px-0",
                active ? "bg-accent text-foreground hover:bg-accent" : "text-muted-foreground hover:bg-accent/60 hover:text-foreground"
              )}
              title={label}
            >
              <Link href={href} aria-current={active ? "page" : undefined}>
                <Icon className="h-4 w-4 shrink-0" />
                <span className={cn("hidden md:inline", collapsed && "md:hidden")}>{label}</span>
              </Link>
            </Button>
          );
        })}
      </nav>

      <div className={cn("flex flex-col gap-2 overflow-hidden border-t p-3", collapsed && "md:items-center")}>
        {!collapsed && <p className="hidden truncate px-2 text-xs text-muted-foreground md:block">{user.email}</p>}
        <LogoutButton collapsed={collapsed} className="h-9 w-full justify-center px-3 md:justify-start" />
      </div>
    </aside>
  );
}
