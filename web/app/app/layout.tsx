import { SessionTimeout } from "@/components/auth/session-timeout";
import { AppShell } from "@/components/navigation/app-shell";
import { requireAuth } from "@/lib/auth";
import type { Metadata } from "next";

export const metadata: Metadata = {
  robots: { index: false, follow: false, googleBot: { index: false, follow: false } },
};

export const dynamic = "force-dynamic";

export default async function AppLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  const { dbUser } = await requireAuth();

  return (
    <>
      <SessionTimeout />
      <AppShell user={dbUser}>{children}</AppShell>
    </>
  );
}
