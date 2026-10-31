# Audio Studio

Audio Studio is an audio generation workspace. It supports text-to-speech, multi-speaker dialogue, audio uploads, and a library for generated recordings. Image, video, 3D, and subscription services have been removed from the application.

## Stack

- `web/`: Next.js 14, including authentication, audio pages, and the audio library.
- `worker/`: FastAPI worker for Cartesia and ElevenLabs audio generation and file storage.
- `db/`: PostgreSQL schema and migration history.

## Run locally

1. Start PostgreSQL from the repository root:

   ```powershell
   docker compose up -d db
   ```

   The local database listens on `127.0.0.1:5433`. Apply `db/schema.sql` to a new database.

2. Start the audio worker in a terminal:

   ```powershell
   cd worker
   python -m venv .venv
   .\.venv\Scripts\python -m pip install -r requirements.txt
   if (!(Test-Path .env)) { Copy-Item .env.example .env }
   .\.venv\Scripts\python -m uvicorn main:app --reload --port 8000
   ```

   Add at least one supported audio provider and its Free-tier confirmation settings to `worker/.env`. The worker rejects generation unless the Free-only safeguards are enabled.

3. Start the web app in another terminal:

   ```powershell
   cd web
   npm install
   if (!(Test-Path .env)) { Copy-Item .env.example .env }
   npm run dev
   ```

   Open [http://localhost:3000](http://localhost:3000). If port 3000 is already occupied, use the existing Next.js server or stop that process before starting another one.

Set up Supabase Auth values in `web/.env`; the app uses Supabase for login and PostgreSQL for audio projects and assets. See [ENVIRONMENT.md](ENVIRONMENT.md) for the variables.

## Audio routes

- `/app/audio-studio`: single-speaker text-to-speech.
- `/app/voice-generator`: text-to-speech and multi-speaker dialogue.
- `/app/projects`: projects and generated or uploaded audio.
- `/app/favorites`, `/app/uploads`, `/app/trash`: audio library management.
- `POST /api/audio/generate`, `GET /api/audio/{id}`: authenticated generation and status.
- `GET /api/models`: configured audio voices and provider status.
- Worker routes: `/audio/generate`, `/models`, `/health`, and `/storage/*`.

The migration files include the database's earlier product history. They are retained so existing installations and user data are not affected; the current web and worker code expose audio features only.









run worker :
.\.venv\Scripts\python.exe -m uvicorn main:app --reload --port 8000
