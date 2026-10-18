"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { AudioLines, Download, Loader2, Mic, Music, Sparkles } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

type Mode = "speech" | "sound_effect" | "music";
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
  maxDurationSeconds?: number;
  description?: string;
  provider?: string | null;
}

interface AudioProviderCatalog {
  cartesia?: ConfiguredProvider;
  elevenlabs?: ConfiguredProvider;
  soundEffects?: ConfiguredProvider;
  musicLoops?: ConfiguredProvider;
  fullMusic?: ConfiguredProvider;
}

const POLL_INTERVAL_MS = 2500;
const MAX_POLL_ATTEMPTS = 120;
const MAX_TEXT_LENGTH = 5000;

function wait(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export default function AudioStudioPage() {
  const [mode, setMode] = useState<Mode>("speech");
  const [catalog, setCatalog] = useState<AudioProviderCatalog>({});
  const [speechProvider, setSpeechProvider] = useState<Provider>("cartesia");
  const [voices, setVoices] = useState<VoiceOption[]>([]);
  const [voiceId, setVoiceId] = useState("");
  const [prompt, setPrompt] = useState("");
  const [durationSeconds, setDurationSeconds] = useState(10);
  const [loop, setLoop] = useState(true);
  const [status, setStatus] = useState<JobStatus>("idle");
  const [message, setMessage] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [assetId, setAssetId] = useState<string | null>(null);

  const cartesiaReady = Boolean(catalog.cartesia?.configured);
  const elevenLabsReady = Boolean(catalog.elevenlabs?.configured);
  const effectsReady = Boolean(catalog.soundEffects?.configured);
  const musicReady = Boolean(catalog.musicLoops?.configured);

  useEffect(() => {
    const queryMode = new URLSearchParams(window.location.search).get("mode");
    if (queryMode === "speech" || queryMode === "sound_effect" || queryMode === "music") {
      setMode(queryMode);
    }
  }, []);

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
        const selectedProvider: Provider =
          providers.cartesia?.configured && providers.cartesia.voices?.length
            ? "cartesia"
            : "elevenlabs";
        setSpeechProvider(selectedProvider);
        const availableVoices =
          selectedProvider === "cartesia"
            ? providers.cartesia?.voices ?? []
            : providers.elevenlabs?.voices ?? [];
        setVoices(availableVoices);
        setVoiceId(availableVoices[0]?.key ?? "");
      })
      .catch(() => {
        if (active) setError("Could not load audio providers. Check worker/.env and restart the worker.");
      });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    const availableVoices =
      speechProvider === "cartesia"
        ? catalog.cartesia?.voices ?? []
        : catalog.elevenlabs?.voices ?? [];
    setVoices(availableVoices);
    setVoiceId(availableVoices[0]?.key ?? "");
  }, [speechProvider, catalog]);

  const modeAvailable = useMemo(() => {
    if (mode === "speech") {
      return speechProvider === "cartesia"
        ? cartesiaReady || elevenLabsReady
        : elevenLabsReady;
    }
    return mode === "sound_effect" ? effectsReady : musicReady;
  }, [mode, speechProvider, cartesiaReady, elevenLabsReady, effectsReady, musicReady]);

  const estimatedCredits = useMemo(() => {
    if (mode === "speech") return prompt.trim().length;
    return Math.ceil(durationSeconds * 40) + prompt.trim().length;
  }, [mode, durationSeconds, prompt]);

  const switchMode = useCallback((nextMode: Mode) => {
    setMode(nextMode);
    setStatus("idle");
    setMessage("");
    setError(null);
    setAudioUrl(null);
    setAssetId(null);
    if (nextMode === "music") {
      setDurationSeconds((current) => Math.max(5, current));
      setLoop(true);
    } else if (nextMode === "sound_effect") {
      setDurationSeconds((current) => Math.max(0.5, Math.min(current, 30)));
    }
  }, []);

  const handleGenerate = async () => {
    const text = prompt.trim();
    if (!text) {
      setError("Enter a text or prompt first.");
      return;
    }
    if (mode === "speech" && !voiceId) {
      setError("No voice is available for the selected provider.");
      return;
    }
    if (mode === "sound_effect" && (durationSeconds < 0.5 || durationSeconds > 30)) {
      setError("Sound effects must be between 0.5 and 30 seconds.");
      return;
    }
    if (mode === "music" && (durationSeconds < 5 || durationSeconds > 30)) {
      setError("Music loops must be between 5 and 30 seconds.");
      return;
    }

    setStatus("submitting");
    setMessage("Preparing a free-tier generation request…");
    setError(null);
    setAudioUrl(null);
    setAssetId(null);

    try {
      const form = new FormData();
      if (mode === "speech") {
        form.append("mode", "single");
        form.append("text", text);
        form.append("provider", speechProvider);
        form.append("voiceId", voiceId);
        form.append("model", speechProvider === "cartesia" ? "sonic-3.6" : "eleven_multilingual_v2");
      } else {
        form.append("mode", mode);
        form.append("text", text);
        form.append("durationSeconds", String(durationSeconds));
        form.append("loop", String(mode === "music" || loop));
      }

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
      setMessage("Generating audio. The provider quota is checked before every generation request…");
      for (let attempt = 0; attempt < MAX_POLL_ATTEMPTS; attempt += 1) {
        await wait(POLL_INTERVAL_MS);
        const pollResponse = await fetch(`/api/audio/${created.jobId}`, { cache: "no-store" });
        const result = await pollResponse.json();
        if (!pollResponse.ok) throw new Error(result.error ?? "Could not check generation status.");
        if (result.status === "complete") {
          if (typeof result.resultUrl !== "string") throw new Error("The job completed but no audio URL was returned.");
          setAudioUrl(result.resultUrl);
          setAssetId(typeof result.assetId === "string" ? result.assetId : null);
          setStatus("complete");
          setMessage("Audio saved in your existing project storage.");
          return;
        }
        if (result.status === "failed") {
          throw new Error(typeof result.error === "string" ? result.error : "Audio generation failed.");
        }
      }
      throw new Error("Generation is taking longer than expected. Check your project history before retrying.");
    } catch (err) {
      setStatus("failed");
      setMessage("");
      setError(err instanceof Error ? err.message : "Audio generation failed.");
    }
  };

  const busy = status === "submitting" || status === "processing";
  const modeLabel =
    mode === "speech" ? "Text to Speech" : mode === "sound_effect" ? "Sound Effects" : "Music Loop";

  return (
    <main className="mx-auto w-full max-w-5xl space-y-6 px-4 py-8 sm:px-6">
      <header className="space-y-2">
        <div className="flex items-center gap-2 text-sm font-medium text-primary">
          <Sparkles className="h-4 w-4" />
          Free-tier Audio Studio
        </div>
        <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">Audio Studio</h1>
        <p className="max-w-3xl text-sm leading-6 text-muted-foreground">
          Generate speech with Cartesia first and a guarded ElevenLabs Free fallback. Sound effects and
          short music loops use the ElevenLabs Free allowance. No paid Music API is called.
        </p>
      </header>

      <div className="grid gap-3 sm:grid-cols-3">
        <button
          type="button"
          onClick={() => switchMode("speech")}
          className={`rounded-xl border p-4 text-left transition ${mode === "speech" ? "border-primary bg-primary/5" : "hover:bg-muted/40"}`}
        >
          <Mic className="mb-3 h-5 w-5" />
          <div className="font-medium">Text to Speech</div>
          <p className="mt-1 text-xs leading-5 text-muted-foreground">Natural voiceovers from text.</p>
        </button>
        <button
          type="button"
          onClick={() => switchMode("sound_effect")}
          className={`rounded-xl border p-4 text-left transition ${mode === "sound_effect" ? "border-primary bg-primary/5" : "hover:bg-muted/40"}`}
        >
          <AudioLines className="mb-3 h-5 w-5" />
          <div className="font-medium">Sound Effects</div>
          <p className="mt-1 text-xs leading-5 text-muted-foreground">Foley, ambience, impacts and transitions.</p>
        </button>
        <button
          type="button"
          onClick={() => switchMode("music")}
          className={`rounded-xl border p-4 text-left transition ${mode === "music" ? "border-primary bg-primary/5" : "hover:bg-muted/40"}`}
        >
          <Music className="mb-3 h-5 w-5" />
          <div className="font-medium">Music Loop</div>
          <p className="mt-1 text-xs leading-5 text-muted-foreground">Short instrumental elements, 5–30 seconds.</p>
        </button>
      </div>

      <Card>
        <CardContent className="space-y-5 p-5 sm:p-7">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2 className="text-xl font-semibold">{modeLabel}</h2>
              <p className="mt-1 text-sm text-muted-foreground">
                {mode === "speech"
                  ? "Paste the script you want spoken."
                  : mode === "sound_effect"
                    ? "Describe the sound in plain language. Choose a duration to estimate quota use."
                    : "Describe the style, instruments and mood. This makes a short loop, not a full-length song."}
              </p>
            </div>
            <span className="rounded-full border px-3 py-1 text-xs font-medium">App credit cost: 0</span>
          </div>

          {mode === "speech" && (
            <div className="grid gap-4 sm:grid-cols-2">
              <label className="space-y-2 text-sm">
                <span className="font-medium">Speech provider</span>
                <select
                  value={speechProvider}
                  onChange={(event) => setSpeechProvider(event.target.value as Provider)}
                  disabled={busy}
                  className="h-10 w-full rounded-md border bg-background px-3"
                >
                  <option value="cartesia">Cartesia (primary)</option>
                  <option value="elevenlabs">ElevenLabs (Free fallback/provider)</option>
                </select>
              </label>
              <label className="space-y-2 text-sm">
                <span className="font-medium">Voice</span>
                <select
                  value={voiceId}
                  onChange={(event) => setVoiceId(event.target.value)}
                  disabled={busy || voices.length === 0}
                  className="h-10 w-full rounded-md border bg-background px-3"
                >
                  {voices.length === 0 && <option value="">No voices available</option>}
                  {voices.map((voice) => (
                    <option key={voice.key} value={voice.key}>{voice.name}</option>
                  ))}
                </select>
                <span className="block text-xs text-muted-foreground">
                  {speechProvider === "cartesia"
                    ? "Cartesia is attempted first; ElevenLabs is used only if its separate Free quota permits."
                    : "ElevenLabs is used only if the account and remaining Free quota pass server checks."}
                </span>
              </label>
            </div>
          )}

          {mode !== "speech" && (
            <div className="grid gap-4 sm:grid-cols-2">
              <label className="space-y-2 text-sm">
                <span className="font-medium">Duration: {durationSeconds} seconds</span>
                <input
                  type="range"
                  min={mode === "music" ? 5 : 0.5}
                  max={30}
                  step={mode === "music" ? 1 : 0.5}
                  value={durationSeconds}
                  onChange={(event) => setDurationSeconds(Number(event.target.value))}
                  disabled={busy}
                  className="w-full"
                />
              </label>
              {mode === "sound_effect" && (
                <label className="flex items-center gap-3 rounded-lg border p-3 text-sm">
                  <input type="checkbox" checked={loop} onChange={(event) => setLoop(event.target.checked)} disabled={busy} />
                  <span>
                    <span className="block font-medium">Loop seamlessly</span>
                    <span className="text-xs text-muted-foreground">Supported by the sound-effects model.</span>
                  </span>
                </label>
              )}
            </div>
          )}

          <label className="block space-y-2 text-sm">
            <span className="font-medium">{mode === "speech" ? "Text" : "Prompt"}</span>
            <textarea
              value={prompt}
              onChange={(event) => setPrompt(event.target.value)}
              maxLength={mode === "speech" ? 5000 : 1000}
              rows={7}
              disabled={busy}
              placeholder={
                mode === "speech"
                  ? "Type the words you want spoken…"
                  : mode === "sound_effect"
                    ? "Example: rain hitting a metal roof, distant thunder and soft wind…"
                    : "Example: warm ambient synth pads, mellow piano, slow cinematic pulse, instrumental, no vocals…"
              }
              className="w-full resize-y rounded-md border bg-background px-3 py-3 leading-6 outline-none focus:ring-2 focus:ring-primary/30"
            />
            <div className="flex justify-between text-xs text-muted-foreground">
              <span>{prompt.length} / {mode === "speech" ? MAX_TEXT_LENGTH : 1000}</span>
              <span>Estimated quota reservation: about {estimatedCredits.toLocaleString()} credits</span>
            </div>
          </label>

          <div className="rounded-lg bg-muted/40 p-3 text-xs leading-5 text-muted-foreground">
            <strong className="text-foreground">Free-only protection:</strong> ElevenLabs account tier and
            remaining allowance are checked by the worker. Cartesia’s current usage endpoint does not expose
            an account-plan check here, so its Free plan must be confirmed manually in the dashboard before
            enabling its confirmation flag; usage is still checked before each generation. The worker reserves
            an estimate and never retries generation POSTs after timeouts. Keep usage-based billing/overage
            disabled. Estimates are conservative, and provider usage can update with delay.
          </div>

          {mode === "music" && (
            <p className="text-xs leading-5 text-muted-foreground">
              Full-length music generation through ElevenLabs Music API is intentionally disabled because
              that API is limited to paid subscribers. This option creates a short loop using the sound-effects
              endpoint, which also supports musical elements.
            </p>
          )}

          {!modeAvailable && (
            <div role="status" className="rounded-lg border border-dashed p-3 text-sm text-muted-foreground">
              This mode is unavailable until its Free-tier provider is configured. Check the free-only
              flags and API keys in worker/.env, then restart FastAPI.
            </div>
          )}

          {error && <div role="alert" className="rounded-lg border border-destructive/40 bg-destructive/5 p-3 text-sm">{error}</div>}
          {message && <p className="text-sm text-muted-foreground">{message}</p>}

          <div className="flex flex-wrap items-center gap-3">
            <Button onClick={handleGenerate} disabled={busy || !modeAvailable || !prompt.trim()}>
              {busy ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Sparkles className="mr-2 h-4 w-4" />}
              {status === "processing" ? "Generating…" : status === "submitting" ? "Starting…" : "Generate audio"}
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
              <div className="font-medium">Generated audio</div>
              <audio controls preload="metadata" src={audioUrl} className="w-full" />
              {assetId && <p className="text-xs text-muted-foreground">Saved asset ID: {assetId}</p>}
            </div>
          )}
        </CardContent>
      </Card>
    </main>
  );
}
