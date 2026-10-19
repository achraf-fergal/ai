"""Regression tests for the Cartesia-first speech provider routing."""
import unittest
from unittest.mock import patch

from providers.http_helpers import ProviderError
from workflows import audio


class SpeechProviderRoutingTests(unittest.TestCase):
    def test_cartesia_is_primary_and_success_does_not_call_elevenlabs(self):
        generated = {
            "audio_bytes": b"wav data",
            "mime_type": "audio/wav",
            "model": "sonic-3.6",
            "provider": "cartesia",
            "provider_cost_cents": 0,
        }
        with patch.object(audio.cartesia, "is_configured", return_value=True), patch.object(
            audio.cartesia, "generate", return_value=generated
        ) as primary, patch.object(audio.elevenlabs, "generate") as fallback:
            result = audio._generate_speech({
                "provider": "cartesia",
                "text": "Hello",
                "voiceId": "cartesia_voice",
                "model": "sonic-3.6",
            })

        self.assertEqual(result, generated)
        primary.assert_called_once_with({
            "text": "Hello",
            "voice_id": "cartesia_voice",
            "model_id": "sonic-3.6",
            "language": None,
        })
        fallback.assert_not_called()

    def test_cartesia_failure_uses_only_guarded_elevenlabs_fallback(self):
        fallback_audio = {
            "audio_bytes": b"mp3 data",
            "mime_type": "audio/mpeg",
            "model": "eleven_multilingual_v2",
            "provider_cost_cents": 0,
        }
        with patch.object(audio.cartesia, "is_configured", return_value=True), patch.object(
            audio.cartesia, "generate", side_effect=ProviderError("Cartesia Free quota unavailable")
        ), patch.object(audio.elevenlabs, "is_configured", return_value=True), patch.object(
            audio.elevenlabs, "generate", return_value=dict(fallback_audio)
        ) as fallback, patch.dict("os.environ", {"ELEVENLABS_FREE_FALLBACK_VOICE_ID": "free_voice"}):
            result = audio._generate_speech({
                "provider": "cartesia",
                "text": "Hello from the portfolio",
                "voiceId": "cartesia_voice",
                "model": "sonic-3.6",
            })

        fallback.assert_called_once_with({
            "text": "Hello from the portfolio",
            "voice_id": "free_voice",
            "model_id": audio.elevenlabs.DEFAULT_MODEL,
        })
        self.assertEqual(result["fallback_provider"], "elevenlabs")
        self.assertIn("(free fallback)", result["model"])

    def test_cartesia_failure_does_not_fall_back_when_elevenlabs_is_not_enabled(self):
        with patch.object(audio.cartesia, "is_configured", return_value=True), patch.object(
            audio.cartesia, "generate", side_effect=ProviderError("quota preflight failed")
        ), patch.object(audio.elevenlabs, "is_configured", return_value=False), patch.object(
            audio.elevenlabs, "generate"
        ) as fallback:
            with self.assertRaises(ProviderError):
                audio._generate_speech({
                    "provider": "cartesia",
                    "text": "Hello",
                    "voiceId": "cartesia_voice",
                    "model": "sonic-3.6",
                })
        fallback.assert_not_called()

    def test_cartesia_unconfigured_fails_closed_without_elevenlabs(self):
        with patch.object(audio.cartesia, "is_configured", return_value=False), patch.object(
            audio.elevenlabs, "is_configured", return_value=False), patch.object(
            audio.elevenlabs, "generate"
        ) as fallback:
            with self.assertRaises(ProviderError):
                audio._generate_speech({
                    "provider": "cartesia",
                    "text": "Hello",
                    "voiceId": "cartesia_voice",
                    "model": "sonic-3.6",
                })
        fallback.assert_not_called()


if __name__ == "__main__":
    unittest.main()
