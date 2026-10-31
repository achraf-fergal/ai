// Audio application queries. Authentication and project data stay shared by the web and worker.
import type { JSONValue } from "postgres";
import sql from "./index";

export interface DbUser {
  id: string;
  email: string;
  display_name: string;
  full_name: string | null;
  avatar_url: string | null;
}

export interface DbProject {
  id: string;
  user_id: string;
  name: string;
  created_at: string;
  updated_at: string;
}

export interface DbAsset {
  id: string;
  project_id: string;
  user_id: string;
  type: "audio";
  generation_id: string | null;
  storage_path: string;
  is_favorite: boolean;
  is_trashed: boolean;
  trashed_at: string | null;
  created_at: string;
}

export interface DbJob {
  id: string;
  user_id: string;
  project_id: string;
  type: "voice_generator" | "dialogue_generator" | "sound_effect_generator" | "music_generator";
  status: "pending" | "processing" | "complete" | "failed";
  input: Record<string, unknown>;
  result_asset_id: string | null;
  error_message: string | null;
  model_used: string | null;
  credits_charged: number;
  created_at: string;
}

export interface DbProjectWithMeta extends DbProject {
  asset_count: number;
}

export class InsufficientCreditsError extends Error {
  constructor(public readonly balance: number) {
    super("insufficient credits");
    this.name = "InsufficientCreditsError";
  }
}

export async function getDefaultProject(userId: string): Promise<DbProject | null> {
  const rows = await sql<DbProject[]>`SELECT * FROM projects WHERE user_id = ${userId} ORDER BY created_at ASC LIMIT 1`;
  return rows[0] ?? null;
}

export async function ensureDefaultProject(userId: string): Promise<DbProject> {
  const existing = await getDefaultProject(userId);
  if (existing) return existing;
  return createProject(userId, "General");
}

export async function listProjects(userId: string): Promise<DbProjectWithMeta[]> {
  return sql<DbProjectWithMeta[]>`
    SELECT p.*,
      (SELECT count(*)::int FROM assets a
        WHERE a.project_id = p.id AND a.type = 'audio' AND NOT a.is_trashed) AS asset_count
    FROM projects p
    WHERE p.user_id = ${userId}
    ORDER BY p.updated_at DESC`;
}

export async function createProject(userId: string, name: string): Promise<DbProject> {
  const rows = await sql<DbProject[]>`INSERT INTO projects (user_id, name) VALUES (${userId}, ${name}) RETURNING *`;
  return rows[0];
}

export async function getProject(userId: string, projectId: string): Promise<DbProject | null> {
  const rows = await sql<DbProject[]>`SELECT * FROM projects WHERE id = ${projectId} AND user_id = ${userId} LIMIT 1`;
  return rows[0] ?? null;
}

export async function renameProject(userId: string, projectId: string, name: string): Promise<void> {
  await sql`UPDATE projects SET name = ${name}, updated_at = now() WHERE id = ${projectId} AND user_id = ${userId}`;
}

export async function deleteProject(userId: string, projectId: string): Promise<boolean> {
  return sql.begin(async (tx) => {
    const legacyRows = await tx<Array<{ has_legacy_data: boolean }>>`
      SELECT (
        EXISTS (SELECT 1 FROM assets WHERE project_id = ${projectId} AND type <> 'audio')
        OR EXISTS (SELECT 1 FROM jobs WHERE project_id = ${projectId}
          AND type NOT IN ('voice_generator', 'dialogue_generator', 'sound_effect_generator', 'music_generator'))
      ) AS has_legacy_data`;
    if (legacyRows[0]?.has_legacy_data) return false;
    await tx`DELETE FROM projects WHERE id = ${projectId} AND user_id = ${userId}`;
    return true;
  });
}

export async function createAudioJobWithReservation(input: {
  userId: string;
  projectId: string;
  type: DbJob["type"];
  jobInput: Record<string, unknown>;
  idempotencyKey: string;
  creditCost: number;
}): Promise<{ jobId: string; status: DbJob["status"]; duplicate: boolean }> {
  return sql.begin(async (tx) => {
    const users = await tx<Array<{ id: string }>>`SELECT id FROM users WHERE id = ${input.userId} FOR UPDATE`;
    if (!users[0]) throw new Error("user not found");

    const existing = await tx<Array<{ id: string; status: DbJob["status"] }>>`
      SELECT id, status FROM jobs WHERE user_id = ${input.userId} AND idempotency_key = ${input.idempotencyKey} LIMIT 1`;
    if (existing[0]) return { jobId: existing[0].id, status: existing[0].status, duplicate: true };

    const projects = await tx<Array<{ id: string }>>`SELECT id FROM projects WHERE id = ${input.projectId} AND user_id = ${input.userId}`;
    if (!projects[0]) throw new Error("project not found");

    const balances = await tx<Array<{ available: number }>>`
      SELECT (
        COALESCE((SELECT SUM(delta) FROM credit_ledger WHERE user_id = ${input.userId}), 0)
        - COALESCE((SELECT SUM(amount) FROM audio_credit_reservations WHERE user_id = ${input.userId} AND status = 'reserved'), 0)
      )::int AS available`;
    const available = balances[0]?.available ?? 0;
    if (input.creditCost > 0 && available < input.creditCost) throw new InsufficientCreditsError(available);

    const jobs = await tx<Array<{ id: string }>>`
      INSERT INTO jobs (user_id, project_id, type, input, idempotency_key)
      VALUES (${input.userId}, ${input.projectId}, ${input.type}, ${tx.json(input.jobInput as JSONValue)}, ${input.idempotencyKey})
      RETURNING id`;
    const jobId = jobs[0].id;
    await tx`INSERT INTO audio_credit_reservations (job_id, user_id, amount, status) VALUES (${jobId}, ${input.userId}, ${input.creditCost}, 'reserved')`;
    return { jobId, status: "pending", duplicate: false };
  });
}

export async function insertSourceAsset(input: {
  userId: string;
  projectId: string;
  type: "audio";
  storagePath: string;
}): Promise<string> {
  const rows = await sql<Array<{ id: string }>>`
    INSERT INTO assets (project_id, user_id, type, generation_id, storage_path)
    VALUES (${input.projectId}, ${input.userId}, 'audio', NULL, ${input.storagePath}) RETURNING id`;
  return rows[0].id;
}

export async function getJobForUser(jobId: string, userId: string): Promise<DbJob | null> {
  const rows = await sql<DbJob[]>`SELECT * FROM jobs WHERE id = ${jobId} AND user_id = ${userId} LIMIT 1`;
  return rows[0] ?? null;
}

export async function markJobFailed(jobId: string): Promise<void> {
  await sql.begin(async (tx) => {
    const failed = await tx<Array<{ id: string }>>`
      UPDATE jobs SET status = 'failed', error_message = 'Audio generation failed, please try again.'
      WHERE id = ${jobId} AND status = 'pending' RETURNING id`;
    if (failed[0]) {
      await tx`UPDATE audio_credit_reservations SET status = 'released', updated_at = now() WHERE job_id = ${jobId} AND status = 'reserved'`;
    }
  });
}

export async function listAssetsForJob(jobId: string): Promise<DbAsset[]> {
  return sql<DbAsset[]>`SELECT * FROM assets WHERE generation_id = ${jobId} AND type = 'audio' ORDER BY created_at ASC`;
}

export async function getAsset(userId: string, assetId: string): Promise<DbAsset | null> {
  const rows = await sql<DbAsset[]>`SELECT * FROM assets WHERE id = ${assetId} AND user_id = ${userId} AND type = 'audio' LIMIT 1`;
  return rows[0] ?? null;
}

export async function listAssets(
  userId: string,
  filters: { projectId?: string; favorite?: boolean; trashed?: boolean; uploadsOnly?: boolean } = {}
): Promise<DbAsset[]> {
  return sql<DbAsset[]>`
    SELECT * FROM assets
    WHERE user_id = ${userId}
      AND type = 'audio'
      AND (${filters.projectId ?? null}::uuid IS NULL OR project_id = ${filters.projectId ?? null}::uuid)
      AND (${filters.favorite ?? null}::boolean IS NULL OR is_favorite = ${filters.favorite ?? null})
      AND is_trashed = ${filters.trashed ?? false}
      AND (${!filters.uploadsOnly}::boolean OR generation_id IS NULL)
    ORDER BY created_at DESC`;
}

export async function setAssetFlags(
  userId: string,
  assetId: string,
  flags: { isFavorite?: boolean; isTrashed?: boolean }
): Promise<void> {
  if (flags.isFavorite !== undefined) {
    await sql`UPDATE assets SET is_favorite = ${flags.isFavorite} WHERE id = ${assetId} AND user_id = ${userId} AND type = 'audio'`;
  }
  if (flags.isTrashed !== undefined) {
    await sql`UPDATE assets SET is_trashed = ${flags.isTrashed}, trashed_at = ${flags.isTrashed ? sql`now()` : null}
      WHERE id = ${assetId} AND user_id = ${userId} AND type = 'audio'`;
  }
}

export async function deleteAsset(userId: string, assetId: string): Promise<void> {
  await sql`DELETE FROM assets WHERE id = ${assetId} AND user_id = ${userId} AND type = 'audio'`;
}
