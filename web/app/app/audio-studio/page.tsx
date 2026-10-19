"use client";

import { useEffect, useState } from "react";
import { Download, Loader2, Mic, Sparkles } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

type Provider = "cartesia" | "elevenlabs";
type JobStatus = "idle" | "submitting" | "processing" | "complete" | "failed";

interface VoiceOption {
  key: string;
  name: string;
  description?: string;
}

interface ConfiguredProvider {
  configured?: boolean;
  voices?: VoiceOption[];
}

interface AudioProviderCatalog {
  cartesia?: ConfiguredProvider;
  elevenlabs?: ConfiguredProvider;
}

const POLL_INTERVAL_MS = 2500;
const MAX_POLL_ATTEMPTS = 120;
const MAX_TEXT_LENGTH = 5000;

function wait(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export default function AudioStudioPage() {
  const [catalog, setCatalog] = useState<AudioProviderCatalog>({});
  const [speechProvider, setSpeechProvider] = useState<Provider>("cartesia");
  const [voiceId, setVoiceId] = useState("");
  const [text, setText] = useState("");
  const [status, setStatus] = useState<JobStatus>("idle");
  const [message, setMessage] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [assetId, setAssetId] = useState<string | null>(null);
  const [loadingCatalog, setLoadingCatalog] = useState(true);

  const cartesiaReady = Boolean(catalog.cartesia?.configured);
  const elevenLabsReady = Boolean(catalog.elevenlabs?.configured);
  const voices = speechProvider === "cartesia"
    ? catalog.cartesia?.voices ?? []
    : catalog.elevenlabs?.voices ?? [];
  const providerReady = speechProvider === "cartesia"
    ? cartesiaReady || elevenLabsReady
    : elevenLabsReady;
  const busy = status === "submitting" || status === "processing";

  useEffect(() => {
    let active = true;
    fetch("/api/models", { cache: "no-store" })
      .then(async (response) => {
        if (!response.ok) throw new Error("Audio provider status could not be loaded.");
        return response.json();
      })
      .then((data: { audioProviders?: AudioProviderCatalog }) => {
        if (!active) return;
        const providers = data.audioProviders ?? {};
        setCatalog(providers);
        const preferred: Provider =
          providers.cartesia?.configured && (providers.cartesia.voices?.length ?? 0) > 0
            ? "cartesia"
            : "elevenlabs";
        setSpeechProvider(preferred);
        const available = preferred === "cartesia"
          ? providers.cartesia?.voices ?? []
          : providers.elevenlabs?.voices ?? [];
        setVoiceId(available[0]?.key ?? "");
      })
      .catch((err: unknown) => {
        if (active) {
          setError(err instanceof Error ? err.message : "Could not load audio providers.");
        }
      })
      .finally(() => {
        if (active) setLoadingCatalog(false);
      });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    const selectedVoiceStillExists = voices.some((voice) => voice.key === voiceId);
    if (!selectedVoiceStillExists) setVoiceId(voices[0]?.key ?? "");
  }, [speechProvider, catalog, voiceId, voices]);

  const handleGenerate = async () => {
    const transcript = text.trim();
    if (!transcript) {
      setError("Enter the text you want spoken.");
      return;
    }
    if (transcript.length > MAX_TEXT_LENGTH) {
      setError(`Text must be ${MAX_TEXT_LENGTH} characters or fewer.`);
      return;
    }
    if (!voiceId) {
      setError("No voice is available for the selected provider.");
      return;
    }
    if (!providerReady) {
      setError("No configured Free audio provider is available. Check worker/.env.");
      return;
    }

    setStatus("submitting");
    setMessage("Checking the provider's Free allowance before generation…");
    setError(null);
    setAudioUrl(null);
    setAssetId(null);

    try {
      const form = new FormData();
      form.append("mode", "single");
      form.append("text", transcript);
      form.append("provider", speechProvider);
      form.append("voiceId", voiceId);
      form.append("model", speechProvider === "cartesia" ? "sonic-3.6" : "eleven_multilingual_v2");

      const response = await fetch("/api/audio/generate", {
        method: "POST",
        headers: { "idempotency-key": crypto.randomUUID() },
        body: form,
      });
      const created = await response.json();
      if (!response.ok) {
        throw new Error(typeof created.error === "string" ? created.error : "Could not start audio generation.");
      }
      if (typeof created.jobId !== "string") {
        throw new Error("The server did not return a job ID.");
      }

      setStatus("processing");
      setMessage("Generating speech. ElevenLabs fallback must pass its own Free-tier checks.");
      for (let attempt = 0; attempt < MAX_POLL_ATTEMPTS; attempt += 1) {
        await wait(POLL_INTERVAL_MS);
        const pollResponse = await fetch(`/api/audio/${created.jobId}`, { cache: "no-store" });
        const result = await pollResponse.json();
        if (!pollResponse.ok) throw new Error(result.error ?? "Could not check generation status.");
        if (result.status === "complete") {
          if (typeof result.resultUrl !== "string") {
            throw new Error("The job completed but no audio URL was returned.");
          }
          setAudioUrl(result.resultUrl);
          setAssetId(typeof result.assetId === "string" ? result.assetId : null);
          setStatus("complete");
          setMessage("Speech saved in your existing project storage.");
          return;
        }
        if (result.status === "failed") {
          throw new Error(typeof result.error === "string" ? result.error : "Speech generation failed.");
        }
      }
      throw new Error("Generation is taking longer than expected. Check your project history before retrying.");
    } catch (err) {
      setStatus("failed");
      setMessage("");
      setError(err instanceof Error ? err.message : "Speech generation failed.");
    }
  };

  return (
    <main className="mx-auto w-full max-w-5xl space-y-6 px-4 py-8 sm:px-6">
      <header className="space-y-2">
        <div className="flex items-center gap-2 text-sm font-medium text-primary">
          <Sparkles className="h-4 w-4" />
          Free-tier Audio Studio
        </div>
        <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">Text to Speech</h1>
        <p className="max-w-3xl text-sm leading-6 text-muted-foreground">
          Cartesia is the primary provider. ElevenLabs is a guarded Free-tier fallback. Multi-speaker dialogue
          remains available in the existing Dialogue Generator.
        </p>
      </header>

      <Card>
        <CardContent className="space-y-5 p-5 sm:p-7">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2 className="text-xl font-semibold">Speech settings</h2>
              <p className="mt-1 text-sm text-muted-foreground">
                Enter up to {MAX_TEXT_LENGTH.toLocaleString()} characters and choose an available voice.
              </p>
            </div>
            <span className="rounded-full border px-3 py-1 text-xs font-medium">App credit cost: 0</span>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <label className="space-y-2 text-sm">
              <span className="font-medium">Speech provider</span>
              <select
                value={speechProvider}
                onChange={(event) => setSpeechProvider(event.target.value as Provider)}
                disabled={busy || loadingCatalog}
                className="h-10 w-full rounded-md border bg-background px-3"
              >
                <option value="cartesia" disabled={!cartesiaReady}>Cartesia (primary)</option>
                <option value="elevenlabs" disabled={!elevenLabsReady}>ElevenLabs (Free fallback/provider)</option>
              </select>
            </label>
            <label className="space-y-2 text-sm">
              <span className="font-medium">Voice</span>
              <select
                value={voiceId}
                onChange={(event) => setVoiceId(event.target.value)}
                disabled={busy || loadingCatalog || voices.length === 0}
                className="h-10 w-full rounded-md border bg-background px-3"
              >
                {voices.length === 0 && <option value="">No voices available</option>}
                {voices.map((voice) => (
                  <option key={voice.key} value={voice.key}>{voice.name}</option>
                ))}
              </select>
              <span className="block text-xs text-muted-foreground">
                {speechProvider === "cartesia"
                  ? "Cartesia is attempted first. ElevenLabs fallback must independently pass its Free-tier quota and billing checks."
                  : "ElevenLabs is used only after the worker verifies Free-tier access and remaining quota."}
              </span>
            </label>
          </div>

          <label className="block space-y-2 text-sm">
            <span className="font-medium">Text to speak</span>
            <textarea
              value={text}
              onChange={(event) => setText(event.target.value)}
              maxLength={MAX_TEXT_LENGTH}
              rows={8}
              disabled={busy}
              placeholder="Write the narration for your portfolio, project demo, or presentation…"
              className="w-full resize-y rounded-md border bg-background px-3 py-3 leading-6 outline-none focus:ring-2 focus:ring-primary/30"
            />
            <div className="flex justify-between text-xs text-muted-foreground">
              <span>{text.length} / {MAX_TEXT_LENGTH}</span>
              <span>Estimated Cartesia usage: {text.trim().length.toLocaleString()} characters</span>
            </div>
          </label>

          <div className="rounded-lg bg-muted/40 p-3 text-xs leading-5 text-muted-foreground">
            <strong className="text-foreground">Free-only protection:</strong> the worker checks Cartesia usage
            before sending a request and verifies ElevenLabs account tier, overage settings, and remaining quota
            before any fallback. Keep provider overages disabled. Free-plan outputs may have non-commercial-use
            limits; review each provider&apos;s current terms before publishing portfolio work commercially.
          </div>

          {!loadingCatalog && !providerReady && (
            <div role="status" className="rounded-lg border border-dashed p-3 text-sm text-muted-foreground">
              No available Free-tier provider. Configure the API keys and Free-tier confirmation flags in
              worker/.env, then restart FastAPI.
            </div>
          )}

          {error && <div role="alert" className="rounded-lg border border-destructive/40 bg-destructive/5 p-3 text-sm">{error}</div>}
          {message && <p className="text-sm text-muted-foreground">{message}</p>}

          <div className="flex flex-wrap items-center gap-3">
            <Button onClick={handleGenerate} disabled={busy || loadingCatalog || !providerReady || !voiceId || !text.trim()}>
              {busy ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Mic className="mr-2 h-4 w-4" />}
              {status === "processing" ? "Generating…" : status === "submitting" ? "Starting…" : "Generate speech"}
            </Button>
            {status === "failed" && (
              <Button variant="outline" onClick={() => { setStatus("idle"); setError(null); setMessage(""); }} disabled={busy}>
                Try again
              </Button>
            )}
            {status === "complete" && audioUrl && (
              <a href={audioUrl} download className="inline-flex items-center rounded-md border px-4 py-2 text-sm font-medium hover:bg-muted">
                <Download className="mr-2 h-4 w-4" /> Download audio
              </a>
            )}
          </div>

          {status === "complete" && audioUrl && (
            <div className="space-y-3 rounded-xl border p-4">
              <div className="font-medium">Generated speech</div>
              <audio controls preload="metadata" src={audioUrl} className="w-full" />
              {assetId && <p className="text-xs text-muted-foreground">Saved asset ID: {assetId}</p>}
            </div>
          )}
        </CardContent>
      </Card>
    </main>
  );
}
