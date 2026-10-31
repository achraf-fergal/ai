"""Expose configured audio voices without leaking provider credentials."""
import logging

import httpx
from fastapi import APIRouter

from providers import cartesia, elevenlabs

router = APIRouter()
log = logging.getLogger("routes.models")


def _provider_catalog(name: str, provider) -> dict:
    enabled = provider.is_configured()
    error = None
    try:
        voices = provider.list_voices() if enabled else []
    except Exception as exc:
        status_code = getattr(exc, "status_code", None)
        if status_code is None and len(getattr(exc, "args", ())) > 1:
            candidate_status = exc.args[1]
            if isinstance(candidate_status, int):
                status_code = candidate_status
        if status_code in (401, 403):
            error = "credentials_rejected"
        elif status_code == 429:
            error = "rate_limited"
        elif isinstance(exc, httpx.RequestError):
            error = "network_unavailable"
        elif isinstance(status_code, int):
            error = f"http_{status_code}"
        else:
            error = "upstream_unavailable"
        log.warning(
            "%s voice catalog request failed (%s, status=%s)",
            name,
            type(exc).__name__,
            status_code,
        )
        voices = []
    return {
        "configured": bool(voices),
        "enabled": enabled,
        "catalogError": error,
        "voices": voices,
    }


def audio_provider_catalog() -> dict:
    return {
        "cartesia": _provider_catalog("cartesia", cartesia),
        "elevenlabs": _provider_catalog("elevenlabs", elevenlabs),
    }


@router.get("/models")
def list_models() -> dict:
    """Return only the audio catalog used by the web studio."""
    providers = audio_provider_catalog()
    return {"audio": providers["elevenlabs"]["voices"], "audioProviders": providers}


@router.get("/models/audio")
def list_audio_models() -> list[dict]:
    return audio_provider_catalog()["elevenlabs"]["voices"]
