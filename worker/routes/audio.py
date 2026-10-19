"""Idempotent start endpoints for free-tier speech and dialogue jobs."""
import re

from fastapi import APIRouter, BackgroundTasks, HTTPException

import db
from providers import cartesia as cartesia_provider
from providers import elevenlabs as elevenlabs_provider
from providers.http_helpers import ProviderError
from routes.generate import StartJob
from workflows import audio as audio_workflow

router = APIRouter()

_AUDIO_JOB_TYPES = {
    "voice_generator",
    "dialogue_generator",
}
_TEXT_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
MAX_SINGLE_TEXT_LENGTH = 5000


def _claim_audio_job(job_id: str) -> tuple[dict, bool]:
    """Atomically claim pending -> processing so duplicate starts run once."""
    with db.connect() as conn:
        job = conn.execute(
            """UPDATE jobs SET status = 'processing'
               WHERE id = %s AND status = 'pending'
               RETURNING *""",
            (job_id,),
        ).fetchone()
        if job:
            return job, True
        existing = conn.execute("SELECT * FROM jobs WHERE id = %s", (job_id,)).fetchone()
    if not existing:
        raise HTTPException(404, "job not found")
    if existing["type"] not in _AUDIO_JOB_TYPES:
        raise HTTPException(400, f"not an audio job: {existing['type']}")
    return existing, False


def _validate_job(job: dict) -> None:
    input_ = job.get("input") or {}
    try:
        if job["type"] == "voice_generator":
            text = input_.get("text")
            if not isinstance(text, str) or not text.strip() or len(text.strip()) > MAX_SINGLE_TEXT_LENGTH:
                raise ProviderError("audio: text must contain 1 to 5000 characters")

            # Missing provider retains backward-compatible ElevenLabs behavior.
            # Current TTS UIs submit a provider explicitly.
            selected_provider = input_.get("provider") or "elevenlabs"
            if selected_provider not in {"cartesia", "elevenlabs"}:
                raise ProviderError("audio: unsupported speech provider")
            voice_id = input_.get("voiceId") or input_.get("voice_id")
            if voice_id is not None and (
                not isinstance(voice_id, str) or not _TEXT_ID_RE.fullmatch(voice_id)
            ):
                raise ProviderError("audio: invalid voice ID")

            if selected_provider == "elevenlabs":
                _text, normalized_voice, _model = elevenlabs_provider.validate_single_input(input_)
                voice_ids = {normalized_voice} if voice_id else set()
                elevenlabs_provider.validate_voice_ids(voice_ids)
            elif voice_id and not isinstance(voice_id, str):
                raise ProviderError("cartesia: invalid voice ID")

        elif job["type"] == "dialogue_generator":
            turns = elevenlabs_provider.normalize_dialogue_inputs(input_.get("inputs"))
            voice_ids = {turn["voice_id"] for turn in turns}
            language_code = input_.get("languageCode") or input_.get("language_code")
            if language_code and (
                not isinstance(language_code, str)
                or len(language_code) != 2
                or not language_code.isalpha()
            ):
                raise ProviderError("elevenlabs: language code must be a two-letter ISO code")
            seed = input_.get("seed")
            if seed is not None and (
                isinstance(seed, bool)
                or not isinstance(seed, int)
                or not 0 <= seed <= 4_294_967_295
            ):
                raise ProviderError("elevenlabs: seed must be between 0 and 4294967295")
            elevenlabs_provider.validate_voice_ids(voice_ids)

        else:
            raise HTTPException(400, f"not an audio job: {job['type']}")
    except ProviderError as err:
        raise HTTPException(422, "Invalid audio generation input.") from err


@router.post("/audio/generate")
def generate_audio(payload: StartJob, background: BackgroundTasks):
    """Claim an audio job once and run it in FastAPI's existing background task."""
    with db.connect() as conn:
        job = conn.execute("SELECT * FROM jobs WHERE id = %s", (payload.job_id,)).fetchone()
    if not job:
        raise HTTPException(404, "job not found")
    if job["type"] not in _AUDIO_JOB_TYPES:
        raise HTTPException(400, f"not an audio job: {job['type']}")
    if job["status"] != "pending":
        # A retry after a lost HTTP response receives the same accepted result;
        # it never schedules a second provider generation.
        return {"ok": True, "already_started": True}

    input_ = job.get("input") or {}
    if job["type"] == "voice_generator":
        selected_provider = input_.get("provider") or "elevenlabs"
        provider_ready = (
            cartesia_provider.is_configured() or elevenlabs_provider.is_configured()
            if selected_provider == "cartesia"
            else elevenlabs_provider.is_configured()
        )
    else:
        provider_ready = elevenlabs_provider.is_configured()
    if not provider_ready:
        raise HTTPException(
            503,
            "Audio API is disabled. Confirm the provider's Free tier and free-only settings in worker/.env.",
        )

    _validate_job(job)
    claimed_job, claimed = _claim_audio_job(payload.job_id)
    if claimed:
        background.add_task(audio_workflow.run, claimed_job)
    return {"ok": True, "already_started": not claimed}
