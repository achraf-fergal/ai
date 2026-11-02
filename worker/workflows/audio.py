"""Audio generation workflows with conservative free-tier provider routing."""
import logging
import io
import wave

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

    if not cartesia.is_configured():
        raise ProviderError("Cartesia Free is not configured")

    return cartesia.generate(
        {
            "text": text,
            "voice_id": voice_id or None,
            "model_id": input_.get("model") or input_.get("model_id") or None,
            "language": input_.get("language"),
        }
    )


def _generate_cartesia_dialogue(input_: dict) -> dict:
    """Generate each Cartesia dialogue turn, then join the compatible WAV clips."""
    turns = input_.get("inputs") or []
    language = input_.get("languageCode") or input_.get("language_code")
    clips: list[bytes] = []
    wav_format: tuple[int, int, int, str, str] | None = None

    for turn in turns:
        result = cartesia.generate(
            {
                "text": turn["text"],
                "voice_id": turn["voice_id"],
                "model_id": cartesia.DEFAULT_MODEL,
                "language": language,
                "emotion": turn.get("emotion"),
            }
        )
        with wave.open(io.BytesIO(result["audio_bytes"]), "rb") as clip:
            if clip.getcomptype() != "NONE":
                raise ProviderError("Cartesia returned a compressed WAV clip")
            current_format = (
                clip.getnchannels(),
                clip.getsampwidth(),
                clip.getframerate(),
                clip.getcomptype(),
                clip.getcompname(),
            )
            if wav_format is not None and current_format != wav_format:
                raise ProviderError("Cartesia dialogue clips used incompatible WAV formats")
            frame_count = clip.getnframes()
            if frame_count < 1:
                raise ProviderError("Cartesia returned a dialogue turn with no audio frames")
            frames = clip.readframes(frame_count)
            expected_bytes = frame_count * clip.getnchannels() * clip.getsampwidth()
            if len(frames) != expected_bytes:
                raise ProviderError("Cartesia returned a truncated dialogue WAV clip")
            if not any(frames):
                raise ProviderError("Cartesia returned a silent dialogue WAV clip")
            wav_format = current_format
            clips.append(frames)

    if not wav_format or not clips:
        raise ProviderError("Cartesia returned no dialogue audio")

    channels, sample_width, sample_rate, compression, compression_name = wav_format
    frame_width = channels * sample_width
    pause = b"\x00" * (int(sample_rate * 0.25) * frame_width)
    combined = bytearray()
    for index, clip_frames in enumerate(clips):
        combined.extend(clip_frames)
        if index + 1 < len(clips):
            combined.extend(pause)

    output = io.BytesIO()
    with wave.open(output, "wb") as dialogue:
        dialogue.setnchannels(channels)
        dialogue.setsampwidth(sample_width)
        dialogue.setframerate(sample_rate)
        dialogue.setcomptype(compression, compression_name)
        dialogue.writeframes(bytes(combined))

    return {
        "audio_bytes": output.getvalue(),
        "mime_type": "audio/wav",
        "model": f"{cartesia.DEFAULT_MODEL} (Cartesia dialogue)",
        "provider": "cartesia",
        "provider_cost_cents": 0,
    }


def run(job: dict) -> None:
    """Generate, store and complete an already-claimed audio job once."""
    input_ = job.get("input") or {}
    storage_path: str | None = None
    try:
        if job["type"] == "voice_generator":
            result = _generate_speech(input_)
        elif job["type"] == "dialogue_generator":
            if (input_.get("provider") or "elevenlabs") == "cartesia":
                result = _generate_cartesia_dialogue(input_)
            else:
                result = elevenlabs.generate_dialogue(input_)
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
                    0,  # Free-only audio mode does not debit app credits.
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
