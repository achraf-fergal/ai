import * as React from "react";
import { cn } from "@/lib/utils";

interface AudioStudioLogoProps extends React.SVGProps<SVGSVGElement> {
  showWordmark?: boolean;
  wordmarkClassName?: string;
}

export function AudioStudioLogo({ className, showWordmark = false, wordmarkClassName, ...props }: AudioStudioLogoProps) {
  return (
    <div className={cn("flex items-center gap-2", showWordmark ? "" : "inline-flex")}>
      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" fill="none" className={cn("h-8 w-8", className)} {...props}>
        <defs>
          <linearGradient id="audio-studio-gradient" x1="2" y1="2" x2="30" y2="30" gradientUnits="userSpaceOnUse">
            <stop offset="0%" stopColor="#2563EB" />
            <stop offset="100%" stopColor="#7C3AED" />
          </linearGradient>
        </defs>
        <rect x="2" y="2" width="28" height="28" rx="7" stroke="url(#audio-studio-gradient)" strokeWidth="2" opacity="0.25" />
        <path d="M8.5 18v-4m5 9V9m5 14V12m5 6v-4" stroke="url(#audio-studio-gradient)" strokeWidth="2.5" strokeLinecap="round" />
      </svg>
      {showWordmark && <span className={cn("text-lg font-semibold tracking-tight text-foreground", wordmarkClassName)}>Audio Studio</span>}
    </div>
  );
}
