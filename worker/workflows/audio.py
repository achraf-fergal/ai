"""Audio generation workflows with conservative free-tier provider routing."""
import logging
import os

import db
import storage
from providers import cartesia, elevenlabs
from providers.http_helpers import ProviderError
from workflows.common import (
    complete_job,
    consume_audio_reservation,
    fail_job,
    insert_asset,
    release_audio_reservation,
    store_audio_output,
)

log = logging.getLogger("workflows.audio")


def _generate_speech(input_: dict) -> dict:
    text = input_.get("text", "")
    requested_provider = input_.get("provider") or "elevenlabs"  # backward-compatible legacy UI
    voice_id = input_.get("voiceId") or input_.get("voice_id")

    if requested_provider == "elevenlabs":
        return elevenlabs.generate(
            {
                "text": text,
                "voice_id": voice_id or None,
                "model_id": input_.get("model") or input_.get("model_id") or None,
            }
        )

    if requested_provider != "cartesia":
        raise ProviderError("unsupported speech provider")

    if cartesia.is_configured():
        try:
            return cartesia.generate(
                {
                    "text": text,
                    "voice_id": voice_id or None,
                    "model_id": input_.get("model") or input_.get("model_id") or None,
                    "language": input_.get("language"),
                }
            )
        except Exception as primary_error:
            # The Cartesia provider itself reserves Free credits before POST and
            # never retries a generation. The backup has its own separate quota guard.
            if not elevenlabs.is_configured():
                raise
            log.warning(
                "Cartesia Free generation was unavailable; trying ElevenLabs Free fallback (%s)",
                type(primary_error).__name__,
            )
    elif not elevenlabs.is_configured():
        raise ProviderError("Cartesia Free is not configured and ElevenLabs Free fallback is unavailable")

    fallback_voice = (
        input_.get("fallbackVoiceId")
        or os.environ.get("ELEVENLABS_FREE_FALLBACK_VOICE_ID")
        or elevenlabs.DEFAULT_VOICE
    )
    result = elevenlabs.generate(
        {
            "text": text,
            "voice_id": fallback_voice,
            "model_id": input_.get("fallbackModel") or elevenlabs.DEFAULT_MODEL,
        }
    )
    result["model"] = f"{result.get('model', elevenlabs.DEFAULT_MODEL)} (free fallback)"
    result["fallback_provider"] = "elevenlabs"
    return result


def run(job: dict) -> None:
    """Generate, store and complete an already-claimed audio job once."""
    input_ = job.get("input") or {}
    storage_path: str | None = None
    try:
        if job["type"] == "voice_generator":
            result = _generate_speech(input_)
        elif job["type"] == "dialogue_generator":
            # Cartesia currently handles one transcript per TTS request; keep
            # structured multi-speaker dialogue on the guarded ElevenLabs API.
            result = elevenlabs.generate_dialogue(input_)
        elif job["type"] == "sound_effect_generator":
            result = elevenlabs.generate_sound_effect(input_)
        elif job["type"] == "music_generator":
            # Free-tier API supports short musical elements/loops through the
            # sound-generation endpoint, not full-length tracks via Music API.
            result = elevenlabs.generate_music_clip(input_)
        else:
            raise ValueError("unsupported audio job type")

        storage_path, _extension = store_audio_output(
            result["audio_bytes"], result["mime_type"]
        )

        with db.connect() as conn:
            with conn.transaction():
                consume_audio_reservation(conn, job["id"])
                asset_id = insert_asset(conn, job, "audio", storage_path)
                complete_job(
                    conn,
                    job,
                    asset_id,
                    0,  # Local Free-only mode never debits application credits.
                    model_used=result.get("model"),
                    provider_cost_cents=int(result.get("provider_cost_cents") or 0),
                )
                if result.get("provider_request_id"):
                    conn.execute(
                        "UPDATE jobs SET provider_request_id = %s WHERE id = %s AND status = 'complete'",
                        (result["provider_request_id"], job["id"]),
                    )
    except Exception as err:
        if storage_path:
            storage.delete_file(storage_path)
        log.exception("audio job %s failed", job.get("id"))
        try:
            with db.connect() as conn:
                with conn.transaction():
                    fail_job(conn, job, err)
                    release_audio_reservation(conn, job["id"])
        except Exception:
            log.exception("could not finalize failed audio job %s", job.get("id"))
