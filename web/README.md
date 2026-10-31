# Audio Studio web app

Next.js frontend and server API for authenticated audio generation and audio library management.

## Start

```powershell
npm install
if (!(Test-Path .env)) { Copy-Item .env.example .env }
npm run dev
```

The app is served at `http://localhost:3000`. Configure Supabase Auth, PostgreSQL, and the FastAPI worker in `.env`; keep all audio provider keys in `worker/.env`.

## Main app routes

- `/app/audio-studio`: single-speaker text-to-speech.
- `/app/voice-generator`: speech and multi-speaker dialogue.
- `/app/projects`: audio projects and recordings.
- `/app/favorites`, `/app/uploads`, `/app/trash`: audio file management.

The root page sends authenticated users to `/app/audio-studio`.

If a local auth callback reports `permission denied for table users`, the database
tables may belong to a different PostgreSQL role. Apply `../db/local-runtime-grants.sql`
to the local database as its owner or administrator.
