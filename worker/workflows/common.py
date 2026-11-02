"""Database and storage helpers shared by audio workflows."""
import io
import logging
import wave

import storage

log = logging.getLogger("workflows.audio")

_AUDIO_MIME_EXT = {
    "audio/mpeg": "mp3",
    "audio/mp3": "mp3",
    "audio/wav": "wav",
    "audio/wave": "wav",
    "audio/x-wav": "wav",
    "audio/ogg": "ogg",
    "audio/webm": "webm",
    "audio/mp4": "mp4",
}


def _has_mpeg_audio_frame(data: bytes) -> bool:
    """Return true when an MP3 stream contains at least one valid MPEG frame."""
    if len(data) < 256:
        return False

    offset = 0
    if data.startswith(b"ID3"):
        if len(data) < 10:
            return False
        tag_size = (
            ((data[6] & 0x7F) << 21)
            | ((data[7] & 0x7F) << 14)
            | ((data[8] & 0x7F) << 7)
            | (data[9] & 0x7F)
        )
        offset = 10 + tag_size + (10 if data[5] & 0x10 else 0)

    scan_end = min(len(data) - 3, offset + 65_536)
    for index in range(offset, scan_end):
        header = int.from_bytes(data[index:index + 4], "big")
        if (header & 0xFFE00000) != 0xFFE00000:
            continue
        version = (header >> 19) & 0b11
        layer = (header >> 17) & 0b11
        bitrate_index = (header >> 12) & 0b1111
        sample_rate_index = (header >> 10) & 0b11
        if (
            version != 0b01
            and layer != 0
            and bitrate_index not in (0, 0b1111)
            and sample_rate_index != 0b11
        ):
            return True
    return False


def validate_audio_payload(data: bytes, mime_type: str) -> None:
    """Reject empty, malformed, or silent audio before it becomes a saved asset."""
    if not isinstance(data, bytes) or not data:
        raise ValueError("audio provider returned an empty audio file")

    mime = mime_type.split(";", 1)[0].strip().lower()
    if mime in {"audio/wav", "audio/wave", "audio/x-wav"}:
        try:
            with wave.open(io.BytesIO(data), "rb") as audio:
                channels = audio.getnchannels()
                sample_width = audio.getsampwidth()
                sample_rate = audio.getframerate()
                frame_count = audio.getnframes()
                if (
                    audio.getcomptype() != "NONE"
                    or channels < 1
                    or sample_width not in (1, 2, 3, 4)
                    or sample_rate < 1
                    or frame_count < 1
                ):
                    raise ValueError("audio provider returned a WAV file with no audio frames")
                expected_bytes = frame_count * channels * sample_width
                pcm = audio.readframes(frame_count)
                if len(pcm) != expected_bytes:
                    raise ValueError("audio provider returned a truncated WAV file")
                silence_frame = b"\x80" if sample_width == 1 else b"\x00"
                silence = silence_frame * len(pcm)
                if pcm == silence:
                    raise ValueError("audio provider returned a silent WAV file")
        except (wave.Error, EOFError, OSError) as err:
            raise ValueError("audio provider returned an invalid WAV file") from err
        return

    if mime in {"audio/mpeg", "audio/mp3"}:
        if not _has_mpeg_audio_frame(data):
            raise ValueError("audio provider returned an invalid or empty MP3 file")
        return

    if mime == "audio/ogg":
        if len(data) < 128 or not data.startswith(b"OggS"):
            raise ValueError("audio provider returned an invalid or empty OGG file")
        return

    if mime == "audio/webm":
        if len(data) < 128 or not data.startswith(bytes((0x1A, 0x45, 0xDF, 0xA3))):
            raise ValueError("audio provider returned an invalid or empty WebM file")
        return

    if mime == "audio/mp4":
        header = data[:64]
        if len(data) < 256 or b"ftyp" not in header or b"mdat" not in data:
            raise ValueError("audio provider returned an invalid or empty MP4 audio file")
        return

    raise ValueError(f"unsupported audio MIME type: {mime}")


def _client_failure_message(err: Exception) -> str:
    """Map provider errors to actionable, non-sensitive user messages."""
    message = str(err).lower()
    if any(marker in message for marker in ("empty audio", "silent wav", "invalid wav", "invalid or empty mp3", "truncated wav", "no audio frames", "invalid or empty ogg", "invalid or empty webm", "invalid or empty mp4")):
        return "The provider returned an empty, silent, or invalid audio file. No audio asset was saved; try again or select another provider."
    if "user_read" in message and any(
        marker in message for marker in ("missing_permissions", "missing permission", "lacks permission")
    ):
        return (
            "ElevenLabs API key is missing the user_read permission required to verify its Free quota. "
            "Enable user_read for the key, update ELEVENLABS_API_KEY in worker/.env, then restart the worker."
        )
    if "active free tier" in message:
        return (
            "The selected ElevenLabs account is not on an active Free plan. Choose another configured "
            "provider or use a key for an active Free account."
        )
    if any(marker in message for marker in ("free monthly", "free quota", "free-tier", "paid overage", "overage")):
        return (
            "The selected provider's Free quota is exhausted or could not be verified. Choose another "
            "configured provider or try again when its quota is available."
        )
    if any(marker in message for marker in ("quota", "insufficient credits", "billing limit", "no credits remaining")):
        return "The audio provider has reached its quota or billing limit. Check its usage or try another configured provider."
    if "429" in message or "rate limit" in message:
        return "The audio provider rate limit was reached. Wait a moment, then try again."
    if any(marker in message for marker in ("401", "403", "invalid api key", "unauthorized", "permission_denied")):
        return "The audio provider key is invalid or lacks access. Update the worker configuration."
    if "cartesia free is not configured" in message:
        return "Cartesia is not configured. Choose ElevenLabs or add the Cartesia keys to worker/.env and restart the worker."
    if any(marker in message for marker in ("not configured", "missing ", "no provider")):
        return "The selected audio provider is not configured. Choose another configured provider or update worker/.env."
    if any(marker in message for marker in ("timeout", "timed out", "connection", "temporarily unavailable", "service unavailable")):
        return "The audio provider is temporarily unavailable. Please try again in a few minutes."
    return "Audio generation failed because of a provider error. Check the audio provider configuration and try again."


def store_audio_output(data: bytes, mime_type: str) -> tuple[str, str]:
    """Save bytes only when the provider returns a known audio MIME type."""
    mime = mime_type.split(";", 1)[0].strip().lower()
    extension = _AUDIO_MIME_EXT.get(mime)
    if not extension or not mime.startswith("audio/"):
        raise ValueError(f"unsupported audio MIME type: {mime}")
    validate_audio_payload(data, mime)
    return storage.save_file(data, extension), extension


def insert_asset(conn, job: dict, type_: str, storage_path: str) -> str:
    """Create the generated audio asset and return its database ID."""
    if type_ != "audio":
        raise ValueError("Audio workflows can only create audio assets")
    row = conn.execute(
        """INSERT INTO assets (project_id, user_id, type, generation_id, storage_path)
           VALUES (%s, %s, 'audio', %s, %s) RETURNING id""",
        (job["project_id"], job["user_id"], job["id"], storage_path),
    ).fetchone()
    return str(row["id"])


def complete_job(
    conn,
    job: dict,
    result_asset_id: str,
    credits_charged: int,
    model_used: str | None = None,
    provider_cost_cents: int | None = None,
) -> None:
    """Complete an audio job and record its application credit spend."""
    updated = conn.execute(
        """UPDATE jobs
           SET status = 'complete', result_asset_id = %s, credits_charged = %s,
               model_used = %s, provider_cost_cents = %s
           WHERE id = %s AND status = 'processing'""",
        (result_asset_id, credits_charged, model_used, provider_cost_cents, job["id"]),
    )
    if updated.rowcount != 1:
        raise RuntimeError(f"job {job['id']} is not processing; completion rejected")
    if credits_charged > 0:
        conn.execute(
            """INSERT INTO credit_ledger (user_id, delta, reason, ref_job_id)
               VALUES (%s, %s, 'spend', %s)""",
            (job["user_id"], -credits_charged, job["id"]),
        )
def fail_job(conn, job: dict, err: Exception) -> None:
    """Fail a job while keeping provider diagnostics in server logs only."""
    log.error("audio job %s (%s) failed: %s", job["id"], job.get("type"), err)
    conn.execute(
        "UPDATE jobs SET status = 'failed', error_message = %s WHERE id = %s AND status = 'processing'",
        (_client_failure_message(err), job["id"]),
    )


def consume_audio_reservation(conn, job_id: str) -> None:
    """Atomically consume a reserved audio credit hold."""
    result = conn.execute(
        """UPDATE audio_credit_reservations
           SET status = 'consumed', updated_at = now()
           WHERE job_id = %s AND status = 'reserved'
           RETURNING job_id""",
        (job_id,),
    )
    if result.rowcount != 1:
        raise RuntimeError(f"audio credit reservation for job {job_id} is not active")


def release_audio_reservation(conn, job_id: str) -> None:
    """Release the reserved credit hold after a failed audio job."""
    conn.execute(
        """UPDATE audio_credit_reservations
           SET status = 'released', updated_at = now()
           WHERE job_id = %s AND status = 'reserved'""",
        (job_id,),
    )
