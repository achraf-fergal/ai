"""Small shared helpers for audio provider adapters."""
import os


class ProviderError(RuntimeError):
    """A provider request failed or was blocked by the free-tier guard."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


def require_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ProviderError(f"missing {name}")
    return value
