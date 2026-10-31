"""FastAPI worker for audio generation and audio-file storage."""
from fastapi import Depends, FastAPI
from fastapi.staticfiles import StaticFiles

from config import STORAGE_DIR
from dependencies import require_worker_key
from providers import is_any_provider_configured
from routes import audio, models
from routes import storage as storage_routes

app = FastAPI(title="Audio Studio Worker")
_protected = dict(dependencies=[Depends(require_worker_key)])

app.include_router(models.router)
app.include_router(audio.router, **_protected)
app.include_router(storage_routes.router, **_protected)


@app.get("/health")
def health() -> dict:
    """Expose worker health and whether an audio provider is available."""
    return {"status": "ok", "providers_configured": is_any_provider_configured()}


STORAGE_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/storage", StaticFiles(directory=STORAGE_DIR), name="storage")
