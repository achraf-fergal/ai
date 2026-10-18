"""Client ElevenLabs pour TTS mono-voix et Text-to-Dialogue.

Le worker reste l'unique détenteur de la clé API. Les réponses audio sont
normalisées en octets et métadonnées pour que les workflows ne connaissent
ni le protocole HTTP ni le format de transport du fournisseur.
"""
from __future__ import annotations

import os
import re
import threading
import time
from typing import Any

import httpx

from providers.http_helpers import ProviderError, require_env

_BASE = "https://api.elevenlabs.io/v1"
DEFAULT_MODEL = "eleven_multilingual_v2"
DIALOGUE_MODEL = "eleven_v3"
DEFAULT_VOICE = "CwhRBWXzGAHq8TQ4Fs17"
ALLOWED_VOICE_MODELS = {DEFAULT_MODEL, "eleven_flash_v2_5", "eleven_turbo_v2_5", "eleven_v3"}
MAX_SINGLE_TEXT_LENGTH = 5000
MAX_DIALOGUE_CHARACTERS = 2000
MAX_DIALOGUE_TURNS = 50
MAX_UNIQUE_DIALOGUE_VOICES = 10
MAX_EMOTION_LENGTH = 80
VOICE_CACHE_TTL_SECONDS = 300

COST_PER_GENERATION_CENTS = 0

_AUDIO_EXTENSIONS = {
    "audio/mpeg": "mp3",
    "audio/mp3": "mp3",
    "audio/wav": "wav",
    "audio/wave": "wav",
    "audio/x-wav": "wav",
    "audio/ogg": "ogg",
    "audio/webm": "webm",
    "audio/mp4": "mp4",
}
_VOICE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
_LANGUAGE_CODE_RE = re.compile(r"^[a-zA-Z]{2}$")

# Client partagé : réutilise le pool HTTP entre générations dans le processus worker.
_CLIENT = httpx.Client(timeout=httpx.Timeout(120.0), follow_redirects=True)
_VOICE_CACHE_LOCK = threading.Lock()
_VOICE_CACHE: tuple[float, list[dict[str, str]]] | None = None


def _truthy(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def is_configured() -> bool:
    """Enabled only when the operator explicitly enables free-only audio."""
    return (
        bool(os.environ.get("ELEVENLABS_API_KEY"))
        and _truthy("AUDIO_FREE_ONLY")
        and _truthy("ELEVENLABS_FREE_TIER_CONFIRMED")
    )


_FREE_MONTHLY_CREDIT_CAP = 10_000
_FREE_USAGE_LOCK = threading.Lock()
_FREE_USAGE_LAST_SERVER_COUNT: int | None = None
_FREE_USAGE_RESERVED = 0


def _reserve_free_credits(estimated_credits: int) -> None:
    """Fail closed unless the account is Free and the current quota fits.

    Reservations are held locally before POST because a timeout can happen
    after the provider has started billing. The remote subscription count is
    reconciled with local reservations on each call.
    """
    global _FREE_USAGE_LAST_SERVER_COUNT, _FREE_USAGE_RESERVED
    if estimated_credits < 1:
        raise ProviderError("elevenlabs: invalid free quota estimate")
    if not _truthy("AUDIO_FREE_ONLY"):
        raise ProviderError("ElevenLabs generation is disabled unless AUDIO_FREE_ONLY=true")
    if not _truthy("ELEVENLABS_FREE_TIER_CONFIRMED"):
        raise ProviderError("ElevenLabs is disabled until its Free tier is explicitly confirmed")

    try:
        response = _CLIENT.get(
            f"{_BASE}/user/subscription",
            headers=_headers(),
            timeout=20,
        )
    except httpx.RequestError as err:
        raise ProviderError("ElevenLabs Free quota could not be checked; generation blocked") from err
    if response.status_code >= 400:
        raise _provider_error(response, "free quota check")
    data = response.json()

    if str(data.get("tier", "")).lower() != "free" or str(data.get("status", "")).lower() != "active":
        raise ProviderError("ElevenLabs request blocked: account is not on an active Free tier")
    overage = data.get("current_overage")
    if not isinstance(overage, dict) or "amount" not in overage:
        raise ProviderError("ElevenLabs overage status could not be verified; generation blocked")
    try:
        if float(overage["amount"]) > 0:
            raise ProviderError("ElevenLabs request blocked because the account reports paid overage")
    except (TypeError, ValueError) as err:
        raise ProviderError("ElevenLabs overage status could not be verified; generation blocked") from err

    # Refuse accounts configured to extend their monthly allowance through
    # usage-based billing. Even a Free tier key must not be allowed to overage.
    extension = data.get("max_credit_limit_extension")
    if data.get("can_extend_character_limit") is not False or extension not in (0, "0"):
        raise ProviderError("ElevenLabs request blocked: paid overage is not explicitly disabled")
    if data.get("has_open_invoices") is True:
        raise ProviderError("ElevenLabs request blocked because the account has open invoices")

    count, limit = data.get("character_count"), data.get("character_limit")
    if isinstance(count, bool) or not isinstance(count, int) or isinstance(limit, bool) or not isinstance(limit, int):
        raise ProviderError("ElevenLabs Free quota response was incomplete; generation blocked")
    try:
        configured_cap = int(os.environ.get("ELEVENLABS_FREE_MONTHLY_CREDIT_LIMIT", str(_FREE_MONTHLY_CREDIT_CAP)))
    except ValueError as err:
        raise ProviderError("ELEVENLABS_FREE_MONTHLY_CREDIT_LIMIT must be an integer") from err
    safe_limit = max(0, min(limit, configured_cap, _FREE_MONTHLY_CREDIT_CAP))

    # Subscription counters reset at the provider's billing-cycle boundary.
    if _FREE_USAGE_LAST_SERVER_COUNT is not None:
        if count < _FREE_USAGE_LAST_SERVER_COUNT:
            _FREE_USAGE_RESERVED = 0
        else:
            newly_reported = count - _FREE_USAGE_LAST_SERVER_COUNT
            _FREE_USAGE_RESERVED = max(0, _FREE_USAGE_RESERVED - newly_reported)
    _FREE_USAGE_LAST_SERVER_COUNT = count

    if count + _FREE_USAGE_RESERVED + estimated_credits > safe_limit:
        raise ProviderError("ElevenLabs Free monthly allowance reached; no generation request was sent")
    # Reserve before POST. Failures/timeouts keep the estimate reserved safely.
    _FREE_USAGE_RESERVED += estimated_credits

def _headers() -> dict[str, str]:
    return {"xi-api-key": require_env("ELEVENLABS_API_KEY")}


def _provider_error(response: httpx.Response, operation: str) -> ProviderError:
    return ProviderError(
        f"elevenlabs {operation} failed ({response.status_code}): {response.text[:300]}",
        response.status_code,
    )


def _post_audio(
    url: str,
    payload: dict[str, Any],
    operation: str,
    timeout_s: int = 120,
    estimated_credits: int = 1,
) -> dict[str, Any]:
    """One provider POST after preflight; never retry generation in free-only mode.

    A connection timeout can occur after a request was billed, so the quota
    is reserved before transmission and each generation request is sent once.
    """
    with _FREE_USAGE_LOCK:
        _reserve_free_credits(estimated_credits)
        try:
            response = _CLIENT.post(
                url,
                headers={**_headers(), "Content-Type": "application/json"},
                json=payload,
                timeout=timeout_s,
            )
        except httpx.TimeoutException as err:
            raise ProviderError(f"elevenlabs {operation} timed out; request was not retried") from err
        except httpx.RequestError as err:
            raise ProviderError(f"elevenlabs {operation} connection failed; request was not retried") from err

        if response.status_code >= 400:
            raise _provider_error(response, operation)
        if not response.content:
            raise ProviderError(f"elevenlabs {operation}: empty response")
        return _normalize_audio_response(response, operation)

def _normalize_audio_response(response: httpx.Response, model: str) -> dict[str, Any]:
    mime_type = response.headers.get("content-type", "audio/mpeg").split(";", 1)[0].strip().lower()
    extension = _AUDIO_EXTENSIONS.get(mime_type)
    if extension is None:
        raise ProviderError(f"elevenlabs returned unsupported audio content type: {mime_type}")
    return {
        "audio_bytes": response.content,
        "mime_type": mime_type,
        "extension": extension,
        "model": model,
        "provider_request_id": response.headers.get("request-id") or response.headers.get("xi-request-id"),
    }


def list_voices(force_refresh: bool = False) -> list[dict[str, str]]:
    """Return the account voice catalog, cached briefly for UI and validation."""
    global _VOICE_CACHE
    now = time.monotonic()
    with _VOICE_CACHE_LOCK:
        if not force_refresh and _VOICE_CACHE and now - _VOICE_CACHE[0] < VOICE_CACHE_TTL_SECONDS:
            return [dict(voice) for voice in _VOICE_CACHE[1]]

    try:
        response = _CLIENT.get(f"{_BASE}/voices", headers=_headers(), timeout=30)
    except httpx.RequestError as err:
        raise ProviderError(f"elevenlabs voices connection failed: {err}") from err
    if response.status_code >= 400:
        raise _provider_error(response, "voices")

    data = response.json()
    voices = [
        {
            "key": voice["voice_id"],
            "name": voice.get("name", "Unknown"),
            "description": voice.get("description")
            or f"{voice.get('labels', {}).get('accent', '')} {voice.get('labels', {}).get('gender', '')}".strip(),
        }
        for voice in (data.get("voices") or [])
        if isinstance(voice, dict) and isinstance(voice.get("voice_id"), str)
    ]
    with _VOICE_CACHE_LOCK:
        _VOICE_CACHE = (time.monotonic(), voices)
    return [dict(voice) for voice in voices]


def validate_voice_ids(voice_ids: set[str]) -> None:
    """Reject voice IDs outside the configured ElevenLabs account catalog."""
    if not voice_ids:
        return
    available = {voice["key"] for voice in list_voices()}
    missing = voice_ids - available
    if missing:
        raise ProviderError("elevenlabs: one or more voice IDs are unavailable")


def _validate_voice_id(voice_id: Any) -> str:
    if not isinstance(voice_id, str) or not _VOICE_ID_RE.fullmatch(voice_id):
        raise ProviderError("elevenlabs: invalid voice ID")
    return voice_id


def normalize_dialogue_inputs(inputs: Any) -> list[dict[str, str]]:
    """Validate structured turns and apply optional natural-language tags.

    Speaker boundaries are supplied by the frontend; this function never
    parses or infers speakers from text.
    """
    if not isinstance(inputs, list) or not 2 <= len(inputs) <= MAX_DIALOGUE_TURNS:
        raise ProviderError(f"elevenlabs: dialogue must contain 2 to {MAX_DIALOGUE_TURNS} turns")

    normalized: list[dict[str, str]] = []
    total_characters = 0
    unique_voices: set[str] = set()
    for item in inputs:
        if not isinstance(item, dict):
            raise ProviderError("elevenlabs: invalid dialogue turn")
        text = item.get("text")
        if not isinstance(text, str) or not text.strip():
            raise ProviderError("elevenlabs: dialogue turns require text")
        voice_id = _validate_voice_id(item.get("voiceId") or item.get("voice_id"))
        emotion = item.get("emotion")
        if emotion is not None:
            if not isinstance(emotion, str) or len(emotion) > MAX_EMOTION_LENGTH:
                raise ProviderError("elevenlabs: invalid dialogue emotion")
            emotion = emotion.strip()
            if any(char in emotion for char in "[]\r\n"):
                raise ProviderError("elevenlabs: emotion must be plain text without brackets")
        rendered_text = f"[{emotion}] {text.strip()}" if emotion else text.strip()
        total_characters += len(rendered_text)
        unique_voices.add(voice_id)
        normalized.append({"text": rendered_text, "voice_id": voice_id})

    if total_characters > MAX_DIALOGUE_CHARACTERS:
        raise ProviderError(f"elevenlabs: dialogue exceeds {MAX_DIALOGUE_CHARACTERS} characters")
    if len(unique_voices) > MAX_UNIQUE_DIALOGUE_VOICES:
        raise ProviderError(f"elevenlabs: dialogue supports at most {MAX_UNIQUE_DIALOGUE_VOICES} distinct voices")
    return normalized


def validate_single_input(input_: dict[str, Any]) -> tuple[str, str, str]:
    text = input_.get("text")
    if not isinstance(text, str) or not text.strip() or len(text.strip()) > MAX_SINGLE_TEXT_LENGTH:
        raise ProviderError(f"elevenlabs: text must contain 1 to {MAX_SINGLE_TEXT_LENGTH} characters")
    voice_id = input_.get("voiceId") or input_.get("voice_id") or DEFAULT_VOICE
    voice_id = _validate_voice_id(voice_id)
    model = input_.get("model") or input_.get("model_id") or DEFAULT_MODEL
    if model not in ALLOWED_VOICE_MODELS:
        raise ProviderError("elevenlabs: unsupported voice model")
    return text.strip(), voice_id, model


def generate(input_: dict[str, Any], timeout_s: int = 120) -> dict[str, Any]:
    """Generate one narration turn using an allowlisted TTS model."""
    text, voice_id, model = validate_single_input(input_)

    response_data = _post_audio(
        f"{_BASE}/text-to-speech/{voice_id}",
        {"text": text.strip(), "model_id": model},
        "text-to-speech",
        timeout_s,
        estimated_credits=len(text.strip()),
    )
    response_data["model"] = model
    response_data["provider"] = "elevenlabs"
    response_data["provider_cost_cents"] = 0
    return response_data


def generate_dialogue(input_: dict[str, Any]) -> dict[str, Any]:
    """Generate dialogue from frontend-provided turns through the official API."""
    inputs = normalize_dialogue_inputs(input_.get("inputs"))
    payload: dict[str, Any] = {"inputs": inputs, "model_id": DIALOGUE_MODEL}

    language_code = input_.get("languageCode") or input_.get("language_code")
    if language_code:
        if not isinstance(language_code, str) or not _LANGUAGE_CODE_RE.fullmatch(language_code):
            raise ProviderError("elevenlabs: language code must be a two-letter ISO code")
        payload["language_code"] = language_code.lower()

    seed = input_.get("seed")
    if seed is not None:
        if isinstance(seed, bool) or not isinstance(seed, int) or not 0 <= seed <= 4_294_967_295:
            raise ProviderError("elevenlabs: seed must be between 0 and 4294967295")
        payload["seed"] = seed

    estimated_credits = sum(len(turn["text"]) for turn in inputs)
    result = _post_audio(
        f"{_BASE}/text-to-dialogue",
        payload,
        "text-to-dialogue",
        estimated_credits=estimated_credits,
    )
    result["model"] = DIALOGUE_MODEL
    result["provider"] = "elevenlabs"
    result["provider_cost_cents"] = 0
    return result

def generate_sound_effect(input_: dict[str, Any]) -> dict[str, Any]:
    """Generate a bounded-duration sound effect within the verified Free quota."""
    text = input_.get("text")
    if not isinstance(text, str) or not text.strip() or len(text.strip()) > 1000:
        raise ProviderError("elevenlabs: sound-effect prompt must contain 1 to 1000 characters")
    duration = input_.get("durationSeconds", input_.get("duration_seconds"))
    if isinstance(duration, bool) or not isinstance(duration, (int, float)) or not 0.5 <= duration <= 30:
        raise ProviderError("elevenlabs: sound-effect duration must be between 0.5 and 30 seconds")
    loop = input_.get("loop", False)
    if not isinstance(loop, bool):
        raise ProviderError("elevenlabs: loop must be a boolean")
    # Official sound-effects guidance: 40 credits/second when duration is set.
    estimate = int(duration * 40 + 0.999999) + len(text.strip())
    result = _post_audio(
        f"{_BASE}/sound-generation",
        {
            "text": text.strip(),
            "duration_seconds": float(duration),
            "loop": loop,
            "model_id": "eleven_text_to_sound_v2",
            "prompt_influence": 0.3,
        },
        "sound-generation",
        timeout_s=120,
        estimated_credits=estimate,
    )
    result["model"] = "eleven_text_to_sound_v2"
    result["provider"] = "elevenlabs"
    result["provider_cost_cents"] = 0
    return result


def generate_music_clip(input_: dict[str, Any]) -> dict[str, Any]:
    """Generate a short musical loop through the Free sound-effects endpoint.

    This is a max-30-second musical element/loop, not the paid full Music API.
    """
    prompt = input_.get("text")
    if not isinstance(prompt, str) or not prompt.strip() or len(prompt.strip()) > 1000:
        raise ProviderError("elevenlabs: music prompt must contain 1 to 1000 characters")
    duration = input_.get("durationSeconds", input_.get("duration_seconds", 10))
    if isinstance(duration, bool) or not isinstance(duration, (int, float)) or not 5 <= duration <= 30:
        raise ProviderError("elevenlabs: music-loop duration must be between 5 and 30 seconds")
    estimate = int(duration * 40 + 0.999999) + len(prompt.strip())
    result = _post_audio(
        f"{_BASE}/sound-generation",
        {
            "text": prompt.strip(),
            "duration_seconds": float(duration),
            "loop": True,
            "model_id": "eleven_text_to_sound_v2",
            "prompt_influence": 0.45,
        },
        "music-loop generation",
        timeout_s=120,
        estimated_credits=estimate,
    )
    result["model"] = "eleven_text_to_sound_v2 (music loop)"
    result["provider"] = "elevenlabs"
    result["provider_cost_cents"] = 0
    return result

