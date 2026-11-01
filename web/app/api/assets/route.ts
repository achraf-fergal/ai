// Audio files owned by the authenticated user, including generated recordings and uploads.
import { NextRequest, NextResponse } from "next/server";

import { requireAuth } from "@/lib/auth";
import { ensureDefaultProject, insertSourceAsset, listAssets } from "@/lib/db/queries";
import { publicUrl, uploadSource } from "@/lib/worker-client";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const AUDIO_TYPES = new Set(["audio/mpeg", "audio/mp3", "audio/wav", "audio/x-wav", "audio/wave", "audio/webm", "audio/ogg", "audio/x-m4a", "audio/mp4"]);
const MAX_AUDIO_SIZE = 20 * 1024 * 1024;

export async function GET(req: NextRequest) {
  const params = new URL(req.url).searchParams;
  const { dbUser: user } = await requireAuth();
  const assets = await listAssets(user.id, {
    projectId: params.get("project_id") ?? undefined,
    favorite: params.get("favorite") === "1" ? true : undefined,
    trashed: params.get("trashed") === "1",
    uploadsOnly: params.get("uploads") === "1",
  });
  return NextResponse.json({
    assets: assets.map((asset) => ({
      id: asset.id,
      projectId: asset.project_id,
      type: "audio" as const,
      url: publicUrl(asset.storage_path),
      isFavorite: asset.is_favorite,
      generationId: asset.generation_id,
      createdAt: asset.created_at,
    })),
  });
}

export async function POST(req: NextRequest) {
  const { dbUser: user } = await requireAuth();
  let form: FormData;
  try {
    form = await req.formData();
  } catch {
    return NextResponse.json({ error: "Invalid request." }, { status: 400 });
  }

  const file = form.get("file");
  if (!(file instanceof File)) return NextResponse.json({ error: "Missing audio file." }, { status: 400 });
  if (!AUDIO_TYPES.has(file.type)) return NextResponse.json({ error: "Unsupported audio file type." }, { status: 400 });
  if (file.size > MAX_AUDIO_SIZE) return NextResponse.json({ error: "Audio file too large (20 MB max)." }, { status: 400 });

  try {
    const storagePath = await uploadSource(Buffer.from(await file.arrayBuffer()), file.type);
    const project = await ensureDefaultProject(user.id);
    const assetId = await insertSourceAsset({ userId: user.id, projectId: project.id, type: "audio", storagePath });
    return NextResponse.json({
      asset: { id: assetId, projectId: project.id, type: "audio", url: publicUrl(storagePath), isFavorite: false, generationId: null, createdAt: new Date().toISOString() },
    });
  } catch {
    return NextResponse.json({ error: "Audio upload failed, please try again." }, { status: 500 });
  }
}
