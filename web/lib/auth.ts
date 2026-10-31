import { redirect } from "next/navigation";
import { cookies } from "next/headers";
import { createServerClient } from "@supabase/ssr";

import sql from "./db";
import { ensureDefaultProject, type DbUser } from "./db/queries";

const DEV_USER_EMAIL = "dev@renderstudio.local";

function hasSupabaseConfig() {
  return Boolean(process.env.NEXT_PUBLIC_SUPABASE_URL && process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY);
}

export async function getSupabaseClient() {
  if (!hasSupabaseConfig()) {
    throw new Error(
      "Supabase is not configured. Set NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY."
    );
  }
  const cookieStore = cookies();
  return createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll() {
          return cookieStore.getAll();
        },
        setAll(cookiesToSet) {
          // En Server Component les cookies sont en lecture seule ; seuls
          // les Route Handlers / Server Actions peuvent écrire. On ignore
          // silencieusement les écritures interdites pour éviter le crash
          // lors du refresh implicite du token par Supabase SSR.
          try {
            cookiesToSet.forEach(({ name, value, options }) => {
              cookieStore.set(name, value, options);
            });
          } catch {
            // ignore
          }
        },
      },
    }
  );
}

async function getDevUserFallback(): Promise<DbUser> {
  const rows = await sql<DbUser[]>`
    SELECT id, email, display_name, full_name, avatar_url FROM users WHERE email = ${DEV_USER_EMAIL} LIMIT 1
  `;
  if (!rows[0]) {
    throw new Error("dev user missing — apply db/schema.sql");
  }
  return rows[0];
}

export async function syncUserFromAuth(authUser: {
  id: string;
  email?: string;
  user_metadata?: Record<string, unknown>;
}): Promise<DbUser | null> {
  const email = authUser.email ?? "";
  const fullName = String(authUser.user_metadata?.full_name ?? "");
  const inserted = await sql<{ id: string }[]>`
    INSERT INTO users (id, email, display_name)
    VALUES (${authUser.id}, ${email}, ${fullName})
    ON CONFLICT (id) DO NOTHING
    RETURNING id
  `;

  const rows = await sql<DbUser[]>`
    SELECT id, email, display_name, full_name, avatar_url
    FROM users WHERE id = ${authUser.id} LIMIT 1
  `;
  const dbUser = rows[0];
  if (!dbUser) return null;

  const project = await ensureDefaultProject(authUser.id);
  if (inserted.length > 0) {
    const configRows = await sql<Array<{ value_int: number | null }>>`
      SELECT value_int FROM app_config WHERE key = 'signup_bonus_credits'
    `;
    const bonus = configRows[0]?.value_int ?? 0;
    if (bonus > 0) {
      await sql`INSERT INTO credit_ledger (user_id, delta, reason) VALUES (${authUser.id}, ${bonus}, 'mint')`;
    }
  }
  await sql`
    UPDATE users SET preferences = jsonb_set(
      COALESCE(preferences, '{}'::jsonb),
      '{default_project_id}',
      to_jsonb(${project.id}::text),
      true
    ) WHERE id = ${authUser.id}
      AND NOT (COALESCE(preferences, '{}'::jsonb) ? 'default_project_id')
  `;

  return dbUser;
}

export async function getCurrentUser(): Promise<DbUser | null> {
  if (!hasSupabaseConfig()) {
    if (process.env.AUTH_DEBUG === "true") {
      return getDevUserFallback();
    }
    return null;
  }

  const supabase = await getSupabaseClient();
  const {
    data: { user },
    error,
  } = await supabase.auth.getUser();

  if (error || !user) {
    if (process.env.AUTH_DEBUG === "true") {
      return getDevUserFallback();
    }
    return null;
  }

  const rows = await sql<DbUser[]>`
    SELECT id, email, display_name, full_name, avatar_url FROM users WHERE id = ${user.id} LIMIT 1
  `;
  if (rows[0]) return rows[0];

  try {
    return await syncUserFromAuth(user);
  } catch (err) {
    console.error("syncUserFromAuth failed", err);
    return null;
  }
}

export async function requireAuth(): Promise<{ supabaseUser: { id: string; email?: string }; dbUser: DbUser }> {
  if (!hasSupabaseConfig()) {
    if (process.env.AUTH_DEBUG === "true") {
      const dbUser = await getDevUserFallback();
      return { supabaseUser: { id: dbUser.id, email: dbUser.email }, dbUser };
    }
    redirect("/login");
  }

  const supabase = await getSupabaseClient();
  const {
    data: { user },
    error,
  } = await supabase.auth.getUser();

  if (error || !user) {
    if (process.env.AUTH_DEBUG === "true") {
      const dbUser = await getDevUserFallback();
      return { supabaseUser: { id: dbUser.id, email: dbUser.email }, dbUser };
    }
    redirect("/login");
  }

  const rows = await sql<DbUser[]>`
    SELECT id, email, display_name, full_name, avatar_url FROM users WHERE id = ${user.id} LIMIT 1
  `;
  let dbUser = rows[0];
  if (!dbUser) {
    try {
      dbUser = (await syncUserFromAuth(user)) ?? undefined;
    } catch (err) {
      console.error("syncUserFromAuth failed", err);
    }
  }
  if (!dbUser) {
    redirect("/login");
  }

  return {
    supabaseUser: { id: user.id, email: user.email ?? dbUser.email },
    dbUser,
  };
}

export async function requireServiceRoleClient() {
  const { createClient } = await import("@supabase/supabase-js");
  return createClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.SUPABASE_SERVICE_ROLE_KEY!
  );
}
