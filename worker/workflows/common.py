"""Database and storage helpers shared by audio workflows."""
import logging

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


def _client_failure_message(err: Exception) -> str:
    """Map provider errors to actionable, non-sensitive user messages."""
    message = str(err).lower()
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
    if not data:
        raise ValueError("audio provider returned an empty file")
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
