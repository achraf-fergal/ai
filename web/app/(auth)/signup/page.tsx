import { Suspense } from "react";

import { AuthForm } from "@/components/auth/auth-form";

export const dynamic = "force-dynamic";

export default function SignupPage() {
  return (
    <main className="flex min-h-screen w-full items-center justify-center p-4">
      <div className="w-full max-w-sm rounded-2xl border border-border bg-card p-6 shadow-sm sm:p-8">
        <Suspense fallback={null}>
          <AuthForm initialMode="signup" />
        </Suspense>
      </div>
    </main>
  );
}
