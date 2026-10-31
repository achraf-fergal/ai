"""Audio provider registry and explicit free-tier configuration checks."""
import os

from providers import cartesia, elevenlabs

PROVIDERS = {
    "cartesia": cartesia,
    "elevenlabs": elevenlabs,
}

PROVIDER_ENV_KEYS = {
    "cartesia": [["CARTESIA_API_KEY", "CARTESIA_ADMIN_API_KEY", "AUDIO_FREE_ONLY", "CARTESIA_FREE_TIER_CONFIRMED"]],
    "elevenlabs": [["ELEVENLABS_API_KEY", "AUDIO_FREE_ONLY", "ELEVENLABS_FREE_TIER_CONFIRMED"]],
}


def _env_enabled(key: str) -> bool:
    value = os.environ.get(key, "")
    if key == "AUDIO_FREE_ONLY" or key.endswith("_FREE_TIER_CONFIRMED"):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def is_provider_configured(name: str) -> bool:
    return any(all(_env_enabled(key) for key in group) for group in PROVIDER_ENV_KEYS[name])


def is_any_provider_configured() -> bool:
    """Report whether at least one guarded audio provider is configured."""
    return any(is_provider_configured(name) for name in PROVIDER_ENV_KEYS)
