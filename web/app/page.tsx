import { redirect } from "next/navigation";
import { getCurrentUser } from "@/lib/auth";
import { LandingPage } from "@/components/landing/landing-page";

export const dynamic = "force-dynamic";

export default async function RootPage({ searchParams }: {
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>;
}) {
  const params = await searchParams;
  if (params.login === "true") {
    redirect(params.mode === "signup" ? "/signup" : "/login");
  }
  if (await getCurrentUser()) redirect("/app/audio-studio");
  return <LandingPage />;
}
