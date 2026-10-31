# Repository notes

This repository is an audio-only generation workspace. The current product scope is text-to-speech, multi-speaker dialogue, audio uploads, and audio library management. Do not restore image, video, 3D, or billing services without an explicit product decision.

## Architecture

- `web/`: Next.js 14 App Router. The server owns authentication, projects, assets, and audio job records.
- `worker/`: FastAPI. It owns Cartesia and ElevenLabs credentials, provider calls, free-tier checks, and audio storage.
- `db/`: shared PostgreSQL schema and historical migrations. Existing migration history and user data are retained.

The web app calls the worker; browsers never receive provider keys. Audio jobs are idempotent and their provider Free-tier guards fail closed.

## Local development

- Start the web app from `web/` with `npm run dev`; it listens on `localhost:3000`.
- Start the worker from `worker/` with `python -m uvicorn main:app --reload --port 8000`.
- Start PostgreSQL with `docker compose up -d db` from the repository root.
- Copy `.env.example` to `.env` only when a local `.env` does not already exist. Never print, replace, or commit real environment files.

See `README.md` and `ENVIRONMENT.md` for setup and configuration.
