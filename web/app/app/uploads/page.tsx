"use client";

import { useCallback, useEffect, useState } from "react";
import { Upload } from "lucide-react";

import { AssetCard, type AssetSummary } from "@/components/projects/asset-card";
import { AssetLayoutControls, assetLayoutClass } from "@/components/projects/asset-layout-controls";
import { useAssetLayout } from "@/components/projects/use-asset-layout";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";

const MAX_AUDIO_BYTES = 20 * 1024 * 1024;

export default function UploadsPage() {
  const [assets, setAssets] = useState<AssetSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const { layout, columns, setLayout, setColumns } = useAssetLayout("uploads");

  const fetchUploads = useCallback(async () => {
    try {
      const response = await fetch("/api/assets?uploads=1");
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = (await response.json()) as { assets: AssetSummary[] };
      setAssets(data.assets);
      setError(null);
    } catch {
      setError("Could not load uploaded audio.");
    }
  }, []);

  useEffect(() => { void fetchUploads(); }, [fetchUploads]);

  const uploadAudio = async (file?: File) => {
    if (!file) return;
    if (!file.type.startsWith("audio/")) {
      setError("Choose an audio file.");
      return;
    }
    if (file.size > MAX_AUDIO_BYTES) {
      setError("Audio files must be 20 MB or smaller.");
      return;
    }
    setUploading(true);
    setError(null);
    try {
      const form = new FormData();
      form.append("file", file);
      const response = await fetch("/api/assets", { method: "POST", body: form });
      const data = await response.json();
      if (!response.ok) throw new Error(typeof data.error === "string" ? data.error : "Upload failed.");
      await fetchUploads();
    } catch (uploadError) {
      setError(uploadError instanceof Error ? uploadError.message : "Upload failed.");
    } finally {
      setUploading(false);
    }
  };

  return (
    <main className="flex min-h-screen w-full flex-col gap-5 p-4 sm:p-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Uploaded audio</h1>
          <p className="text-sm text-muted-foreground">Keep audio files together with generated recordings.</p>
        </div>
        <label className="cursor-pointer">
          <input type="file" accept="audio/*" className="sr-only" disabled={uploading} onChange={(event) => { void uploadAudio(event.target.files?.[0]); event.currentTarget.value = ""; }} />
          <span className="inline-flex h-9 items-center rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground hover:bg-primary/90">
            <Upload className="mr-2 h-4 w-4" /> {uploading ? "Uploading…" : "Upload audio"}
          </span>
        </label>
      </header>

      <AssetLayoutControls layout={layout} columns={columns} onLayoutChange={setLayout} onColumnsChange={setColumns} />
      {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
      {assets === null ? (
        <div className={assetLayoutClass(layout)} style={layout === "grid" ? { gridTemplateColumns: `repeat(${columns}, minmax(0, 1fr))` } : undefined}>
          {Array.from({ length: 4 }).map((_, index) => <Skeleton key={index} className="aspect-[4/3] w-full" />)}
        </div>
      ) : assets.length === 0 ? (
        <div className="flex flex-1 flex-col items-center justify-center gap-2 py-16 text-center">
          <p className="text-sm font-medium">No uploaded audio yet</p>
          <p className="text-sm text-muted-foreground">Upload an audio file to add it to your library.</p>
        </div>
      ) : (
        <div className={assetLayoutClass(layout)} style={layout === "grid" ? { gridTemplateColumns: `repeat(${columns}, minmax(0, 1fr))` } : undefined}>
          {assets.map((asset) => <AssetCard key={asset.id} asset={asset} layout={layout} onChanged={() => void fetchUploads()} />)}
        </div>
      )}
    </main>
  );
}
