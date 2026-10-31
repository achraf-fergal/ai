# Audio worker

FastAPI service for speech, multi-speaker dialogue, audio uploads, and local audio-file delivery. Provider keys stay in this service.

## Local setup

From this directory:

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
if (!(Test-Path .env)) { Copy-Item .env.example .env }
.\.venv\Scripts\python -m uvicorn main:app --reload --port 8000
```

Set a database URL shared with `web/.env`. Enable at least one provider only after confirming the provider account is on a Free tier, setting its confirmation flag, and disabling paid overages. See [../ENVIRONMENT.md](../ENVIRONMENT.md).

## Routes

- `GET /health`: health and whether a guarded audio provider is configured.
- `GET /models`: available audio voices and provider readiness.
- `POST /audio/generate`: start a pending text-to-speech or dialogue job. The route requires `WORKER_API_KEY` when configured.
- `POST /storage/upload`: store an uploaded audio file.
- `GET /storage/{name}`: play or download a stored audio file.
- `DELETE /storage/{name}`: remove an expired audio file.

Generated files are saved under `worker/storage` by default. Keep that directory persistent if audio needs to survive worker restarts.
