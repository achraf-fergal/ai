"use client";

import { useState } from "react";
import { ArchiveRestore, Download, Music2, Star, Trash2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { saveResult } from "@/lib/download";
import { cn } from "@/lib/utils";

export interface AssetSummary {
  id: string;
  type: "audio";
  url: string;
  isFavorite: boolean;
}

interface AssetCardProps {
  asset: AssetSummary;
  trashed?: boolean;
  onChanged: () => void;
  onDelete?: (assetId: string) => void;
  layout?: "grid" | "list";
}

export function AssetCard({ asset, trashed = false, onChanged, onDelete, layout = "grid" }: AssetCardProps) {
  const [busy, setBusy] = useState(false);

  const patch = async (body: { isFavorite?: boolean; isTrashed?: boolean }) => {
    if (busy) return;
    setBusy(true);
    try {
      const response = await fetch(`/api/assets/${asset.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!response.ok) throw new Error("Could not update this audio file.");
      onChanged();
    } finally {
      setBusy(false);
    }
  };

  const handleDelete = async () => {
    if (!onDelete || !window.confirm("Delete this audio file permanently? This cannot be undone.")) return;
    setBusy(true);
    try {
      const response = await fetch(`/api/assets/${asset.id}`, { method: "DELETE" });
      if (!response.ok) throw new Error("Could not delete this audio file.");
      onDelete(asset.id);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card className={cn("overflow-hidden", layout === "list" && "flex min-h-32 flex-row")}>
      <div className={cn("relative flex items-center justify-center gap-3 bg-muted p-4", layout === "list" ? "w-40 shrink-0 sm:w-56" : "aspect-[4/3] flex-col")}>
        <Music2 className="h-10 w-10 shrink-0 text-muted-foreground" />
        <audio src={asset.url} controls preload="metadata" className="w-full max-w-sm" />
        <Badge variant="secondary" className="absolute left-2 top-2">Audio</Badge>
      </div>
      <CardContent className={cn("flex flex-wrap items-center justify-end gap-1 p-2", layout === "list" && "flex-1 self-center")}>
        {trashed ? (
          <>
            <Button type="button" variant="ghost" size="sm" disabled={busy} onClick={() => void patch({ isTrashed: false })} className="gap-2">
              <ArchiveRestore className="h-4 w-4" /> Restore
            </Button>
            {onDelete && (
              <Button type="button" variant="ghost" size="sm" disabled={busy} onClick={() => void handleDelete()} className="gap-2 text-destructive hover:text-destructive">
                <Trash2 className="h-4 w-4" /> Delete
              </Button>
            )}
          </>
        ) : (
          <>
            <Button type="button" variant="ghost" size="icon" className="h-8 w-8" disabled={busy} onClick={() => void saveResult(asset.url)} aria-label="Download audio">
              <Download className="h-4 w-4" />
            </Button>
            <Button type="button" variant="ghost" size="icon" className="h-8 w-8" disabled={busy} onClick={() => void patch({ isFavorite: !asset.isFavorite })} aria-label={asset.isFavorite ? "Remove from favorites" : "Add to favorites"}>
              <Star className={cn("h-4 w-4", asset.isFavorite && "fill-current text-yellow-500")} />
            </Button>
            <Button type="button" variant="ghost" size="icon" className="h-8 w-8" disabled={busy} onClick={() => void patch({ isTrashed: true })} aria-label="Move audio to trash">
              <Trash2 className="h-4 w-4" />
            </Button>
          </>
        )}
      </CardContent>
    </Card>
  );
}
