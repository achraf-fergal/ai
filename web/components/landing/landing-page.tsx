import Link from "next/link";
import { AudioLines, Mic, Sparkles, Waves } from "lucide-react";

import { Button } from "@/components/ui/button";
import { ThemeToggle } from "@/components/theme-toggle";

const FEATURES = [
  { icon: AudioLines, title: "Text to speech", description: "Turn a script into clear, natural sounding speech." },
  { icon: Mic, title: "Voice selection", description: "Choose from voices provided by your configured audio services." },
  { icon: Waves, title: "Dialogue generation", description: "Build multi-speaker dialogue from a script." },
];

export function LandingPage() {
  return (
    <main className="min-h-screen overflow-hidden bg-background">
      <header className="mx-auto flex h-16 max-w-6xl items-center justify-between px-5">
        <Link href="/" className="flex items-center gap-2 font-semibold">
          <Waves className="h-5 w-5 text-primary" />
          <span>Audio Studio</span>
        </Link>
        <div className="flex items-center gap-3">
          <ThemeToggle variant="ghost" size="icon" />
          <Button variant="ghost" asChild><Link href="/login">Sign in</Link></Button>
          <Button asChild><Link href="/signup">Get started</Link></Button>
        </div>
      </header>

      <section className="relative mx-auto grid min-h-[68vh] max-w-6xl items-center gap-12 px-5 py-16 md:grid-cols-[1.1fr_0.9fr] md:py-24">
        <div className="relative z-10 space-y-7">
          <div className="inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-sm text-muted-foreground">
            <Sparkles className="h-4 w-4 text-primary" />
            A workspace for AI audio creation
          </div>
          <h1 className="max-w-2xl text-4xl font-semibold tracking-tight sm:text-6xl">
            Give your words a voice.
          </h1>
          <p className="max-w-xl text-lg leading-8 text-muted-foreground">
            Create speech and multi-speaker dialogue, then keep every recording organized in your audio library.
          </p>
          <div className="flex flex-wrap gap-3">
            <Button size="lg" asChild><Link href="/signup">Start creating</Link></Button>
            <Button size="lg" variant="outline" asChild><Link href="/login">Sign in</Link></Button>
          </div>
          <p className="text-xs text-muted-foreground">Audio providers and their usage limits are configured by your workspace administrator.</p>
        </div>

        <div className="relative mx-auto flex aspect-square w-full max-w-md items-center justify-center rounded-full border bg-card/70 p-8 shadow-2xl shadow-primary/10">
          <div className="absolute inset-8 rounded-full border border-dashed border-primary/25" />
          <div className="absolute inset-16 rounded-full border border-primary/20" />
          <div className="flex h-36 w-36 items-center justify-center rounded-full bg-primary/10 text-primary">
            <AudioLines className="h-20 w-20" strokeWidth={1.2} />
          </div>
          <div className="absolute bottom-[24%] left-[8%] flex h-12 w-12 items-center justify-center rounded-2xl border bg-background shadow-lg"><Mic className="h-5 w-5" /></div>
          <div className="absolute right-[9%] top-[22%] flex h-12 w-12 items-center justify-center rounded-2xl border bg-background shadow-lg"><Waves className="h-5 w-5" /></div>
          <div className="absolute bottom-[19%] right-[18%] h-2 w-2 rounded-full bg-primary" />
        </div>
      </section>

      <section className="mx-auto grid max-w-6xl gap-4 px-5 pb-20 md:grid-cols-3">
        {FEATURES.map(({ icon: Icon, title, description }) => (
          <article key={title} className="rounded-xl border bg-card p-6">
            <Icon className="mb-4 h-5 w-5 text-primary" />
            <h2 className="font-semibold">{title}</h2>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">{description}</p>
          </article>
        ))}
      </section>

      <footer className="border-t px-5 py-6 text-center text-xs text-muted-foreground">
        <Link href="/terms" className="hover:text-foreground">Terms</Link>
        <span className="mx-3">·</span>
        <Link href="/privacy" className="hover:text-foreground">Privacy</Link>
      </footer>
    </main>
  );
}
