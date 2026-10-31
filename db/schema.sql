-- Audio Studio baseline schema. It creates the tables used by the current
-- audio application and does not drop or rewrite existing tables or data.
-- Existing databases may still contain tables from earlier product versions.
-- Apply with: docker compose exec -T db psql -U renderstudio -d renderstudio < db/schema.sql

BEGIN;

CREATE TABLE IF NOT EXISTS users (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  email        text NOT NULL UNIQUE,
  display_name text NOT NULL DEFAULT '',
  avatar_url   text,
  full_name    text,
  preferences  jsonb NOT NULL DEFAULT '{}',
  created_at   timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS projects (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id    uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  name       text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS jobs (
  id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id             uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  project_id          uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  type                text NOT NULL CHECK (type IN (
                        'voice_generator', 'dialogue_generator',
                        'sound_effect_generator', 'music_generator'
                      )),
  status              text NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending', 'processing', 'complete', 'failed')),
  input               jsonb NOT NULL DEFAULT '{}',
  idempotency_key     text,
  result_asset_id     uuid,
  error_message       text,
  model_used          text,
  provider_request_id text,
  credits_charged     int NOT NULL DEFAULT 0,
  provider_cost_cents int,
  created_at          timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS idempotency_key text;
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS model_used text;
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS provider_request_id text;
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS credits_charged int NOT NULL DEFAULT 0;
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS provider_cost_cents int;
CREATE INDEX IF NOT EXISTS jobs_user_created ON jobs(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS jobs_project ON jobs(project_id);
CREATE UNIQUE INDEX IF NOT EXISTS jobs_user_idempotency_unique
  ON jobs(user_id, idempotency_key) WHERE idempotency_key IS NOT NULL;

CREATE TABLE IF NOT EXISTS assets (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id    uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  user_id       uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  type          text NOT NULL CHECK (type = 'audio'),
  generation_id uuid REFERENCES jobs(id) ON DELETE SET NULL,
  storage_path  text NOT NULL,
  is_favorite   boolean NOT NULL DEFAULT false,
  is_trashed    boolean NOT NULL DEFAULT false,
  trashed_at    timestamptz,
  created_at    timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS assets_project_visible ON assets(project_id) WHERE NOT is_trashed;
CREATE INDEX IF NOT EXISTS assets_user_created ON assets(user_id, created_at DESC);

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname IN ('jobs_result_asset_fk', 'jobs_result_fk')
  ) THEN
    ALTER TABLE jobs ADD CONSTRAINT jobs_result_asset_fk
      FOREIGN KEY (result_asset_id) REFERENCES assets(id) ON DELETE SET NULL;
  END IF;
END
$$;

CREATE TABLE IF NOT EXISTS credit_ledger (
  id         bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  user_id    uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  delta      int NOT NULL,
  reason     text NOT NULL CHECK (reason IN ('mint', 'spend', 'refund', 'expire')),
  ref_job_id uuid REFERENCES jobs(id) ON DELETE SET NULL,
  metadata   jsonb NOT NULL DEFAULT '{}',
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (ref_job_id, reason)
);
CREATE INDEX IF NOT EXISTS credit_ledger_user_created
  ON credit_ledger(user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS audio_credit_reservations (
  job_id     uuid PRIMARY KEY REFERENCES jobs(id) ON DELETE CASCADE,
  user_id    uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  amount     int NOT NULL CHECK (amount >= 0),
  status     text NOT NULL DEFAULT 'reserved'
               CHECK (status IN ('reserved', 'consumed', 'released')),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS audio_credit_reservations_user_status
  ON audio_credit_reservations(user_id, status);

CREATE TABLE IF NOT EXISTS app_config (
  key        text PRIMARY KEY,
  value_int  int,
  value_text text,
  updated_at timestamptz NOT NULL DEFAULT now()
);

INSERT INTO users (email, display_name)
VALUES ('dev@renderstudio.local', 'Dev User')
ON CONFLICT (email) DO NOTHING;

INSERT INTO projects (user_id, name)
SELECT id, 'General' FROM users
WHERE email = 'dev@renderstudio.local'
  AND NOT EXISTS (
    SELECT 1 FROM projects p JOIN users u ON u.id = p.user_id
    WHERE u.email = 'dev@renderstudio.local' AND p.name = 'General'
  );

INSERT INTO app_config (key, value_int) VALUES ('signup_bonus_credits', 100)
ON CONFLICT (key) DO NOTHING;

INSERT INTO credit_ledger (user_id, delta, reason)
SELECT id, 100, 'mint' FROM users
WHERE email = 'dev@renderstudio.local'
  AND NOT EXISTS (
    SELECT 1 FROM credit_ledger l JOIN users u ON u.id = l.user_id
    WHERE u.email = 'dev@renderstudio.local' AND l.reason = 'mint'
  );

COMMIT;
