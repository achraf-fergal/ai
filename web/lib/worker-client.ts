// The audio worker owns generation, provider credentials, and audio storage.
export function baseUrl(): string {
  return (process.env.WORKER_BASE_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");
}

const publicBaseUrl = () =>
  (process.env.WORKER_PUBLIC_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");

export function publicUrl(storagePath: string): string {
  return `${publicBaseUrl()}${storagePath}`;
}

export class WorkerNotConfiguredError extends Error {
  constructor() {
    super("audio worker has no provider configured");
    this.name = "WorkerNotConfiguredError";
  }
}

export class AudioWorkerStartError extends Error {
  constructor(readonly statusCode: number, message: string) {
    super(message);
    this.name = "AudioWorkerStartError";
  }
}

export async function isWorkerConfigured(): Promise<boolean> {
  try {
    const response = await fetch(`${baseUrl()}/health`, { cache: "no-store" });
    if (!response.ok) return false;
    const data = (await response.json()) as { providers_configured?: boolean };
    return data.providers_configured === true;
  } catch {
    return false;
  }
}

function workerHeaders(): Record<string, string> {
  const key = process.env.WORKER_API_KEY;
  return {
    "Content-Type": "application/json",
    ...(key ? { "X-Worker-Key": key } : {}),
  };
}

export async function startAudioJob(jobId: string): Promise<void> {
  const response = await fetch(`${baseUrl()}/audio/generate`, {
    method: "POST",
    headers: workerHeaders(),
    body: JSON.stringify({ job_id: jobId }),
  });
  if (response.status === 503) throw new WorkerNotConfiguredError();
  if (!response.ok) {
    let detail = "";
    try {
      const payload = (await response.json()) as { detail?: unknown };
      if (typeof payload.detail === "string") detail = payload.detail;
    } catch {
      // Non-JSON worker errors are mapped to a safe explanation by the route.
    }
    throw new AudioWorkerStartError(response.status, detail);
  }
}

export async function uploadSource(data: Buffer, mime: string): Promise<string> {
  const form = new FormData();
  const extension = mime.split("/")[1] ?? "audio";
  form.append("file", new Blob([new Uint8Array(data)], { type: mime }), `upload.${extension}`);
  const headers: Record<string, string> = {};
  const key = process.env.WORKER_API_KEY;
  if (key) headers["X-Worker-Key"] = key;
  const response = await fetch(`${baseUrl()}/storage/upload`, { method: "POST", headers, body: form });
  if (!response.ok) throw new Error(`audio worker upload failed (${response.status})`);
  const payload = (await response.json()) as { path?: string };
  if (!payload.path) throw new Error("audio worker upload returned no path");
  return payload.path;
}
