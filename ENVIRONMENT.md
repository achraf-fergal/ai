# Environment configuration

Keep provider secrets in `worker/.env` and authentication/database secrets in `web/.env`. Example files contain placeholders only. Do not commit either real `.env` file.

## Web (`web/.env`)

- `DATABASE_URL`: PostgreSQL connection used by Next.js. The local Compose database is available at `127.0.0.1:5433`.
- `WORKER_BASE_URL`: server-side worker address, normally `http://127.0.0.1:8000`.
- `WORKER_PUBLIC_URL`: worker address reachable by the browser for saved audio playback, normally `http://127.0.0.1:8000` locally.
- `WORKER_API_KEY`: optional shared secret; when set, it must match the worker value.
- `NEXT_PUBLIC_SUPABASE_URL` and `NEXT_PUBLIC_SUPABASE_ANON_KEY`: Supabase Auth configuration.
- `SUPABASE_SERVICE_ROLE_KEY`: server-only key used for account deletion.
- `NEXT_PUBLIC_APP_URL`: local app URL, normally `http://localhost:3000`.
- `AUTH_DEBUG`: optional local development fallback. Leave disabled outside local development.

If a local auth callback logs `permission denied for table users`, the tables may be
owned by a different PostgreSQL role. Apply `db/local-runtime-grants.sql` to the local
database as its owner or administrator; it grants the local `renderstudio` role access
to the tables used by the web app and worker.

## Worker (`worker/.env`)

- `DATABASE_URL`: PostgreSQL connection shared with the web app.
- `WORKER_API_KEY`: optional shared secret matching `web/.env`.
- `STORAGE_DIR`: optional local audio storage directory. Defaults to `worker/storage`.
- `AUDIO_FREE_ONLY=true`: required to enable guarded Free-tier audio calls.
- `CARTESIA_API_KEY`, `CARTESIA_ADMIN_API_KEY`, and `CARTESIA_FREE_TIER_CONFIRMED=true`: Cartesia TTS, multi-speaker dialogue, and its quota check.
- `ELEVENLABS_API_KEY` and `ELEVENLABS_FREE_TIER_CONFIRMED=true`: ElevenLabs TTS and multi-speaker dialogue.
- `CARTESIA_DEFAULT_VOICE_ID`: optional Cartesia voice default.

At least one fully configured provider is required. Keep paid overages disabled in the provider account; the worker fails closed if its Free-tier checks cannot be confirmed. Audio provider credentials must never use a `NEXT_PUBLIC_` prefix.
