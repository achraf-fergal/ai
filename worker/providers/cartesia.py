"""Cartesia TTS client with a fail-closed free-tier guard.

Cartesia's standard API key can generate speech. The separate admin key is
used only to read monthly credit usage so the worker can stay below the
published 20,000-credit Free allowance. The operator must explicitly confirm
that the generation key belongs to a Free account; this module never upgrades
an account or retries a generation request.
"""
from __future__ import annotations

import os
import re
import threading
from datetime import datetime, timezone
from typing import Any

import httpx

from providers.http_helpers import ProviderError, require_env

_BASE = "https://api.cartesia.ai"
_VERSION = os.environ.get("CARTESIA_VERSION", "2026-08-14")
DEFAULT_MODEL = "sonic-3.6"
MAX_TEXT_LENGTH = 5000
PUBLISHED_FREE_MONTHLY_CREDITS = 20_000
_VOICE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
_CLIENT = httpx.Client(timeout=httpx.Timeout(60.0), follow_redirects=False)
_GENERATION_LOCK = threading.Lock()


def _truthy(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def is_configured() -> bool:
    """Return true only when all free-tier safety switches and both keys exist."""
    return (
        _truthy("AUDIO_FREE_ONLY")
        and _truthy("CARTESIA_FREE_TIER_CONFIRMED")
        and bool(os.environ.get("CARTESIA_API_KEY"))
        and bool(os.environ.get("CARTESIA_ADMIN_API_KEY"))
    )


def _headers(*, admin: bool = False) -> dict[str, str]:
    key_name = "CARTESIA_ADMIN_API_KEY" if admin else "CARTESIA_API_KEY"
    return {
        "Authorization": f"Bearer {require_env(key_name)}",
        "Cartesia-Version": _VERSION,
    }


def _request_error(response: httpx.Response, operation: str) -> ProviderError:
    return ProviderError(
        f"cartesia {operation} failed ({response.status_code}): {response.text[:250]}",
        response.status_code,
    )


def list_voices() -> list[dict[str, str]]:
    """List active voices for the Studio selector; this endpoint generates no audio."""
    if not is_configured():
        return []
    try:
        response = _CLIENT.get(
            f"{_BASE}/voices",
            headers=_headers(),
            params={"limit": 100},
            timeout=20,
        )
    except httpx.RequestError as err:
        raise ProviderError("cartesia voice catalog is unavailable") from err
    if response.status_code >= 400:
        raise _request_error(response, "voices")
    payload = response.json()
    result: list[dict[str, str]] = []
    for voice in payload.get("data", []):
        if not isinstance(voice, dict) or not isinstance(voice.get("id"), str):
            continue
        if voice.get("status") not in (None, "active"):
            continue
        result.append({
            "key": voice["id"],
            "name": str(voice.get("name") or "Cartesia voice"),
            "description": str(voice.get("description") or voice.get("tagline") or voice.get("language") or ""),
        })
    return result


def _current_month_usage() -> int:
    """Read account-wide monthly usage from Cartesia's admin usage endpoint."""
    now = datetime.now(timezone.utc)
    start = datetime(now.year, now.month, 1, tzinfo=timezone.utc)
    params = {
        "start_ts": start.isoformat(timespec="seconds").replace("+00:00", "Z"),
        "end_ts": now.isoformat(timespec="seconds").replace("+00:00", "Z"),
    }
    try:
        response = _CLIENT.get(
            f"{_BASE}/usage/credits",
            headers=_headers(admin=True),
            params=params,
            timeout=20,
        )
    except httpx.RequestError as err:
        raise ProviderError("cartesia free quota could not be checked; generation blocked") from err
    if response.status_code >= 400:
        raise ProviderError(
            f"cartesia quota check failed ({response.status_code}); generation blocked",
            response.status_code,
        )
    data = response.json().get("data")
    if not isinstance(data, list):
        raise ProviderError("cartesia quota response was invalid; generation blocked")
    try:
        return sum(max(0, int(item.get("credits", 0))) for item in data if isinstance(item, dict))
    except (TypeError, ValueError) as err:
        raise ProviderError("cartesia quota response was invalid; generation blocked") from err


def _assert_free_budget(estimated_credits: int) -> None:
    if not _truthy("AUDIO_FREE_ONLY"):
        raise ProviderError("audio generation is disabled unless AUDIO_FREE_ONLY=true")
    if not _truthy("CARTESIA_FREE_TIER_CONFIRMED"):
        raise ProviderError("Cartesia is disabled until its Free account is explicitly confirmed")
    if not os.environ.get("CARTESIA_ADMIN_API_KEY"):
        raise ProviderError("Cartesia is disabled because its free quota cannot be verified")
    try:
        configured_limit = int(os.environ.get("CARTESIA_FREE_MONTHLY_CREDIT_LIMIT", str(PUBLISHED_FREE_MONTHLY_CREDITS)))
    except ValueError as err:
        raise ProviderError("CARTESIA_FREE_MONTHLY_CREDIT_LIMIT must be an integer") from err
    # Never permit a configured cap above the published Free allowance.
    safe_limit = max(0, min(configured_limit, PUBLISHED_FREE_MONTHLY_CREDITS))
    used = _current_month_usage()
    if used + estimated_credits > safe_limit:
        raise ProviderError("Cartesia Free monthly audio allowance reached; no generation request was sent")


def generate(input_: dict[str, Any]) -> dict[str, Any]:
    """Generate WAV audio after an account quota preflight; do not retry POSTs."""
    text = input_.get("text")
    if not isinstance(text, str) or not text.strip() or len(text.strip()) > MAX_TEXT_LENGTH:
        raise ProviderError(f"cartesia: text must contain 1 to {MAX_TEXT_LENGTH} characters")
    voice_id = input_.get("voice_id") or os.environ.get("CARTESIA_DEFAULT_VOICE_ID")
    if not isinstance(voice_id, str) or not _VOICE_ID_RE.fullmatch(voice_id):
        raise ProviderError("cartesia: select a valid voice ID")

    model = input_.get("model_id") or DEFAULT_MODEL
    if model != DEFAULT_MODEL:
        raise ProviderError("cartesia: unsupported model")
    payload = {
        "model_id": model,
        "transcript": text.strip(),
        "voice": voice_id,
        "output_format": {"container": "wav", "encoding": "pcm_s16le", "sample_rate": 44100},
    }
    language = input_.get("language")
    if isinstance(language, str) and re.fullmatch(r"[a-zA-Z]{2}", language):
        payload["language"] = language.lower()

    # This lock avoids two local requests both passing the same quota preflight.
    with _GENERATION_LOCK:
        _assert_free_budget(len(text.strip()))
        try:
            response = _CLIENT.post(
                f"{_BASE}/tts/bytes",
                headers={**_headers(), "Content-Type": "application/json"},
                json=payload,
                timeout=120,
            )
        except httpx.TimeoutException as err:
            raise ProviderError("cartesia TTS timed out; it was not retried") from err
        except httpx.RequestError as err:
            raise ProviderError("cartesia TTS connection failed; it was not retried") from err
        if response.status_code >= 400:
            raise _request_error(response, "TTS")
        if not response.content:
            raise ProviderError("cartesia returned an empty audio file")
        mime_type = response.headers.get("content-type", "audio/wav").split(";", 1)[0].strip().lower()
        if mime_type not in {"audio/wav", "audio/wave", "audio/x-wav"}:
            raise ProviderError(f"cartesia returned unsupported audio type: {mime_type}")
        return {
            "audio_bytes": response.content,
            "mime_type": mime_type,
            "extension": "wav",
            "model": model,
            "provider": "cartesia",
            "provider_request_id": response.headers.get("request-id") or response.headers.get("x-request-id"),
            "provider_cost_cents": 0,
        }
