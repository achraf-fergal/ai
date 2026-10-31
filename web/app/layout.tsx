import type { Metadata } from "next";
import localFont from "next/font/local";
import "./globals.css";
import { ThemeProvider } from "@/components/theme-provider";
import { getSiteUrl } from "@/lib/site-url";

const geistSans = localFont({
  src: "./fonts/GeistVF.woff",
  variable: "--font-geist-sans",
  weight: "100 900",
});
const geistMono = localFont({
  src: "./fonts/GeistMonoVF.woff",
  variable: "--font-geist-mono",
  weight: "100 900",
});

export const metadata: Metadata = {
  metadataBase: getSiteUrl(),
  title: {
    default: "Audio Studio | AI Voice and Speech",
    template: "%s | Audio Studio",
  },
  description:
    "Create AI-generated speech and multi-speaker dialogue, then organize your audio in one workspace.",
  alternates: {
    canonical: "/",
  },
  openGraph: {
    type: "website",
    siteName: "Audio Studio",
    title: "Audio Studio | AI Voice and Speech",
    description: "Create AI-generated speech and multi-speaker dialogue in one audio workspace.",
    url: "/",
  },
  twitter: {
    card: "summary_large_image",
    title: "Audio Studio | AI Voice and Speech",
    description: "Create AI-generated speech and multi-speaker dialogue in one audio workspace.",
  },
};

const themeInitScript = `
  (function() {
    let theme = "dark";
    try {
      theme = localStorage.getItem("audio-studio-theme") === "light" ? "light" : "dark";
    } catch {}
    document.documentElement.classList.remove("light", "dark");
    document.documentElement.classList.add(theme);
  })();
`;

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeInitScript }} />
      </head>
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased`}
      >
        <ThemeProvider>
          {children}
        </ThemeProvider>
      </body>
    </html>
  );
}
