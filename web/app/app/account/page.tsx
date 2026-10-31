import { requireAuth } from "@/lib/auth";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { DeleteAccountButton } from "./delete-account-button";

export const dynamic = "force-dynamic";

export default async function AccountPage() {
  const { supabaseUser, dbUser } = await requireAuth();
  return (
    <main className="flex min-h-screen w-full flex-col gap-5 p-4 sm:p-6">
      <header>
        <h1 className="text-xl font-semibold tracking-tight">Account</h1>
        <p className="text-sm text-muted-foreground">Your Audio Studio profile and account controls.</p>
      </header>

      <Card>
        <CardHeader>
          <CardTitle>Profile</CardTitle>
          <CardDescription>Manage your account details from Settings.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-1">
            <p className="text-sm font-medium">Email</p>
            <p className="text-sm text-muted-foreground">{supabaseUser.email ?? dbUser.email}</p>
          </div>
          <div className="space-y-1">
            <p className="text-sm font-medium">Display name</p>
            <p className="text-sm text-muted-foreground">{dbUser.display_name || "—"}</p>
          </div>
          <div className="space-y-1">
            <p className="text-sm font-medium">Full name</p>
            <p className="text-sm text-muted-foreground">{dbUser.full_name || "—"}</p>
          </div>
        </CardContent>
      </Card>

      <Card className="border-destructive/50">
        <CardHeader>
          <CardTitle className="text-destructive">Delete account</CardTitle>
          <CardDescription>Permanently remove your Audio Studio account, projects and files.</CardDescription>
        </CardHeader>
        <CardContent><DeleteAccountButton /></CardContent>
      </Card>
    </main>
  );
}
