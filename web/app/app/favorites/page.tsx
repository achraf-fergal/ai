"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";

import { AssetCard, type AssetSummary } from "@/components/projects/asset-card";
import { AssetLayoutControls, assetLayoutClass } from "@/components/projects/asset-layout-controls";
import { useAssetLayout } from "@/components/projects/use-asset-layout";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";

export default function FavoritesPage() {
  const [assets, setAssets] = useState<AssetSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const { layout, columns, setLayout, setColumns } = useAssetLayout("favorites");

  const fetchFavorites = useCallback(async () => {
    try {
      const response = await fetch("/api/assets?favorite=1");
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = (await response.json()) as { assets: AssetSummary[] };
      setAssets(data.assets);
      setError(null);
    } catch {
      setError("Could not load your audio favorites.");
    }
  }, []);

  useEffect(() => { void fetchFavorites(); }, [fetchFavorites]);

  return (
    <main className="flex min-h-screen w-full flex-col gap-5 p-4 sm:p-6">
      <header>
        <h1 className="text-xl font-semibold tracking-tight">Favorite audio</h1>
        <p className="text-sm text-muted-foreground">Your saved speech and dialogue recordings.</p>
      </header>
      <AssetLayoutControls layout={layout} columns={columns} onLayoutChange={setLayout} onColumnsChange={setColumns} />
      {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
      {assets === null ? (
        <div className={assetLayoutClass(layout)} style={layout === "grid" ? { gridTemplateColumns: `repeat(${columns}, minmax(0, 1fr))` } : undefined}>
          {Array.from({ length: 4 }).map((_, index) => <Skeleton key={index} className="aspect-[4/3] w-full" />)}
        </div>
      ) : assets.length === 0 ? (
        <div className="flex flex-1 flex-col items-center justify-center gap-2 py-16 text-center">
          <p className="text-sm font-medium">No favorite audio yet</p>
          <p className="text-sm text-muted-foreground">Star a recording in your audio library to find it here.</p>
          <Button asChild variant="outline" size="sm" className="mt-2"><Link href="/app/projects">Open Audio Library</Link></Button>
        </div>
      ) : (
        <div className={assetLayoutClass(layout)} style={layout === "grid" ? { gridTemplateColumns: `repeat(${columns}, minmax(0, 1fr))` } : undefined}>
          {assets.map((asset) => <AssetCard key={asset.id} asset={asset} layout={layout} onChanged={() => void fetchFavorites()} />)}
        </div>
      )}
    </main>
  );
}
