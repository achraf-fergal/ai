// Authenticated audio project contents and project management.
import { NextRequest, NextResponse } from "next/server";

import { requireAuth } from "@/lib/auth";
import { deleteProject, getProject, listAssets, renameProject } from "@/lib/db/queries";
import { publicUrl } from "@/lib/worker-client";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(_req: NextRequest, { params }: { params: { id: string } }) {
  const { dbUser: user } = await requireAuth();
  const project = await getProject(user.id, params.id);
  if (!project) return NextResponse.json({ error: "Project not found." }, { status: 404 });
  const assets = await listAssets(user.id, { projectId: project.id });
  return NextResponse.json({
    project: { id: project.id, name: project.name },
    assets: assets.map((asset) => ({
      id: asset.id,
      type: "audio" as const,
      url: publicUrl(asset.storage_path),
      isFavorite: asset.is_favorite,
      generationId: asset.generation_id,
      createdAt: asset.created_at,
    })),
  });
}

export async function PATCH(req: NextRequest, { params }: { params: { id: string } }) {
  const body = (await req.json().catch(() => null)) as { name?: unknown } | null;
  const { dbUser: user } = await requireAuth();
  const project = await getProject(user.id, params.id);
  if (!project) return NextResponse.json({ error: "Project not found." }, { status: 404 });
  if (typeof body?.name === "string" && body.name.trim()) {
    await renameProject(user.id, project.id, body.name.trim().slice(0, 120));
  }
  return NextResponse.json({ ok: true });
}

export async function DELETE(_req: NextRequest, { params }: { params: { id: string } }) {
  const { dbUser: user } = await requireAuth();
  const project = await getProject(user.id, params.id);
  if (!project) return NextResponse.json({ error: "Project not found." }, { status: 404 });
  const deleted = await deleteProject(user.id, project.id);
  if (!deleted) {
    return NextResponse.json({ error: "This project still contains archived non-audio data and cannot be removed from the audio library." }, { status: 409 });
  }
  return NextResponse.json({ ok: true });
}
