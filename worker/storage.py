"""Local storage for generated and uploaded audio files."""
import uuid
from pathlib import Path

from config import STORAGE_DIR

_AUDIO_EXTENSIONS = {"mp3", "wav", "ogg", "webm", "mp4", "m4a"}


def save_file(data: bytes, ext: str) -> str:
    """Write an audio file with a generated name and return its public path."""
    extension = ext.lstrip(".").lower()
    if extension not in _AUDIO_EXTENSIONS:
        raise ValueError("unsupported audio file extension")
    if not data:
        raise ValueError("cannot store an empty audio file")
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    name = f"{uuid.uuid4()}.{extension}"
    (STORAGE_DIR / name).write_bytes(data)
    return f"/storage/{name}"


def resolve(storage_path: str) -> Path:
    """Resolve one worker storage path without allowing directory traversal."""
    name = storage_path.removeprefix("/storage/")
    if not name or "/" in name or "\\" in name or ".." in name:
        raise ValueError("invalid storage path")
    return STORAGE_DIR / name


def delete_file(storage_path: str) -> None:
    """Delete one stored audio file, ignoring malformed paths."""
    try:
        resolve(storage_path).unlink(missing_ok=True)
    except ValueError:
        return
