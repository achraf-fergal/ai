"use client";

import Link from "next/link";
import { FolderOpen, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";

export interface ProjectSummary {
  id: string;
  name: string;
  assetCount: number;
}

interface ProjectCardProps {
  project: ProjectSummary;
  onDelete?: (projectId: string) => void;
  layout?: "grid" | "list";
}

export function ProjectCard({ project, onDelete, layout = "grid" }: ProjectCardProps) {
  return (
    <Card className={cn("group relative overflow-hidden transition-all hover:ring-1 hover:ring-foreground/20", layout === "list" && "flex min-h-32 flex-row")}>
      <Link href={`/app/projects/${project.id}`} className={cn("flex w-full items-center gap-4 p-5", layout === "list" && "flex-1")}>
        <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary">
          <FolderOpen className="h-6 w-6" />
        </div>
        <div className="min-w-0 flex-1">
          <p className="truncate font-semibold">{project.name}</p>
          <p className="text-sm text-muted-foreground">{project.assetCount} audio files</p>
        </div>
      </Link>
      {onDelete && (
        <Button
          type="button"
          variant="ghost"
          size="icon"
          className="absolute right-2 top-2 h-8 w-8 text-muted-foreground opacity-100 hover:text-destructive md:opacity-0 md:group-hover:opacity-100"
          onClick={(event) => {
            event.preventDefault();
            event.stopPropagation();
            if (window.confirm(`Delete audio project "${project.name}" and its files? This cannot be undone.`)) onDelete(project.id);
          }}
          aria-label="Delete project"
        >
          <Trash2 className="h-4 w-4" />
        </Button>
      )}
    </Card>
  );
}
