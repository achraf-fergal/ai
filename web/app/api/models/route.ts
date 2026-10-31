// Public-safe proxy for the configured audio provider catalog.
import { NextResponse } from "next/server";
import { WorkerNotConfiguredError, baseUrl } from "@/lib/worker-client";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET() {
  try {
    const response = await fetch(`${baseUrl()}/models`, { cache: "no-store" });
    if (!response.ok) throw new Error(`worker /models failed (${response.status})`);
    const data = (await response.json()) as { audio?: unknown[]; audioProviders?: Record<string, unknown> };
    return NextResponse.json({
      audio: Array.isArray(data.audio) ? data.audio : [],
      audioProviders: data.audioProviders && typeof data.audioProviders === "object" ? data.audioProviders : {},
    });
  } catch (error) {
    if (error instanceof WorkerNotConfiguredError) {
      return NextResponse.json({ audio: [], audioProviders: {} }, { status: 503 });
    }
    return NextResponse.json({ error: "Failed to load audio providers." }, { status: 502 });
  }
}
