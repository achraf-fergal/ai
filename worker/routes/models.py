"""Expose safe, configured provider and model choices to the Audio Studio."""
from fastapi import APIRouter, HTTPException

from catalog import list_feature_models
from providers import cartesia, elevenlabs, upscale

router = APIRouter()


def _safe_voices(provider) -> list[dict]:
    """A failing voice-catalog request must not take down the whole model list."""
    try:
        return provider.list_voices()
    except Exception:
        return []


def _audio_provider_catalog() -> dict:
    cartesia_ready = cartesia.is_configured()
    elevenlabs_ready = elevenlabs.is_configured()
    cartesia_voices = _safe_voices(cartesia) if cartesia_ready else []
    elevenlabs_voices = _safe_voices(elevenlabs) if elevenlabs_ready else []
    return {
        "cartesia": {
            "configured": cartesia_ready and bool(cartesia_voices),
            "voices": cartesia_voices,
        },
        "elevenlabs": {
            "configured": elevenlabs_ready and bool(elevenlabs_voices),
            "voices": elevenlabs_voices,
        },
    }


@router.get("/models")
def list_models() -> dict:
    """List configured models; audio APIs are visible only in explicit Free mode."""
    audio_catalog = _audio_provider_catalog()
    # Keep the legacy audio array compatible with the existing Voice Generator.
    return {
        "image": list_feature_models("print_render", include_costs=True),
        "background_remover": list_feature_models("background_remover", include_costs=True),
        "video": (
            list_feature_models("animate", include_costs=True)
            + list_feature_models("video_to_video", include_costs=True)
            + list_feature_models("video_relight", include_costs=True)
        ),
        "upscale": upscale.list_models(),
        "audio": audio_catalog["elevenlabs"]["voices"],
        "audioProviders": audio_catalog,
        "threed": list_feature_models("3d_generator", include_costs=True),
    }


@router.get("/models/{feature}")
def list_feature(feature: str) -> list[dict]:
    """List one feature's models."""
    if feature not in {
        "print_render",
        "mood_swap",
        "exterior_to_interior",
        "plan_to_render",
        "image_extender",
        "multi_angle",
        "variations",
        "background_remover",
        "text_to_image",
        "animate",
        "video_to_video",
        "video_relight",
        "lip_sync",
        "upscale",
        "audio",
        "3d_generator",
    }:
        raise HTTPException(400, "unknown feature")
    if feature == "upscale":
        return upscale.list_models()
    if feature == "audio":
        return _audio_provider_catalog()["elevenlabs"]["voices"]
    return list_feature_models(feature, include_costs=True)
