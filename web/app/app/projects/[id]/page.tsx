"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowLeft, Trash2 } from "lucide-react";

import { AssetCard, type AssetSummary } from "@/components/projects/asset-card";
import { AssetLayoutControls, assetLayoutClass } from "@/components/projects/asset-layout-controls";
import { useAssetLayout } from "@/components/projects/use-asset-layout";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";

export default function ProjectDetailPage({ params }: { params: { id: string } }) {
  const router = useRouter();
  const [projectName, setProjectName] = useState<string | null>(null);
  const [assets, setAssets] = useState<AssetSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);
  const { layout, columns, setLayout, setColumns } = useAssetLayout(`project:${params.id}`);

  const fetchProject = useCallback(async () => {
    try {
      const response = await fetch(`/api/projects/${params.id}`);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = (await response.json()) as { project: { id: string; name: string }; assets: AssetSummary[] };
      setProjectName(data.project.name);
      setAssets(data.assets);
      setError(null);
    } catch {
      setError("Could not load this audio project.");
    }
  }, [params.id]);

  useEffect(() => { void fetchProject(); }, [fetchProject]);

  const deleteProject = async () => {
    if (!window.confirm(`Delete project "${projectName ?? "this project"}" and its audio files? This cannot be undone.`)) return;
    setDeleting(true);
    try {
      const response = await fetch(`/api/projects/${params.id}`, { method: "DELETE" });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      router.push("/app/projects");
    } catch {
      setError("Could not delete this project.");
      setDeleting(false);
    }
  };

  return (
    <main className="flex min-h-screen w-full flex-col gap-5 p-4 sm:p-6">
      <header className="flex flex-col gap-3">
        <Button asChild variant="ghost" size="sm" className="w-fit gap-2 px-0 text-muted-foreground">
          <Link href="/app/projects"><ArrowLeft className="h-4 w-4" /> Audio Library</Link>
        </Button>
        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="text-xl font-semibold tracking-tight">{projectName ?? "Loading…"}</h1>
            <p className="text-sm text-muted-foreground">{assets === null ? "Loading audio…" : `${assets.length} audio files`}</p>
          </div>
          <Button type="button" variant="outline" size="sm" className="gap-2 text-destructive hover:text-destructive" disabled={deleting} onClick={() => void deleteProject()}>
            <Trash2 className="h-4 w-4" /> Delete project
          </Button>
        </div>
      </header>

      <AssetLayoutControls layout={layout} columns={columns} onLayoutChange={setLayout} onColumnsChange={setColumns} />
      {error && <p role="alert" className="text-sm text-destructive">{error}</p>}

      {assets === null ? (
        <div className={assetLayoutClass(layout)} style={layout === "grid" ? { gridTemplateColumns: `repeat(${columns}, minmax(0, 1fr))` } : undefined}>
          {Array.from({ length: 4 }).map((_, index) => <Skeleton key={index} className="aspect-[4/3] w-full" />)}
        </div>
      ) : assets.length === 0 ? (
        <div className="flex flex-1 flex-col items-center justify-center gap-2 py-16 text-center">
          <p className="text-sm font-medium">No audio in this project yet</p>
          <p className="text-sm text-muted-foreground">Generate speech to save it here.</p>
          <Button asChild variant="outline" size="sm" className="mt-2"><Link href="/app/audio-studio">Open Audio Studio</Link></Button>
        </div>
      ) : (
        <div className={assetLayoutClass(layout)} style={layout === "grid" ? { gridTemplateColumns: `repeat(${columns}, minmax(0, 1fr))` } : undefined}>
          {assets.map((asset) => <AssetCard key={asset.id} asset={asset} layout={layout} onChanged={() => void fetchProject()} />)}
        </div>
      )}
    </main>
  );
}
