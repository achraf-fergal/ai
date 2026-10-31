"""Audio uploads and deletion of expired audio assets."""
from fastapi import APIRouter, File, HTTPException, UploadFile

import storage

router = APIRouter()

ALLOWED_TYPES = {
    "audio/mpeg": "mp3",
    "audio/mp3": "mp3",
    "audio/wav": "wav",
    "audio/x-wav": "wav",
    "audio/wave": "wav",
    "audio/webm": "webm",
    "audio/ogg": "ogg",
    "audio/x-m4a": "m4a",
    "audio/mp4": "m4a",
}
MAX_AUDIO_SIZE = 20 * 1024 * 1024


@router.post("/storage/upload")
async def upload(file: UploadFile = File(...)):
    extension = ALLOWED_TYPES.get(file.content_type or "")
    if not extension:
        raise HTTPException(400, "unsupported audio type (MP3, WAV, WebM, OGG or M4A)")
    data = await file.read()
    if not data:
        raise HTTPException(400, "empty file")
    if len(data) > MAX_AUDIO_SIZE:
        raise HTTPException(400, "file too large (20 MB max)")
    return {"path": storage.save_file(data, extension)}


@router.delete("/storage/{name}")
def delete(name: str):
    """Delete a stored file after its database asset has expired."""
    storage.delete_file(f"/storage/{name}")
    return {"ok": True}
