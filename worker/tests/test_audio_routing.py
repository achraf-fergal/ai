"""Regression tests for explicitly selected speech provider routing."""
import unittest
from unittest.mock import patch

from providers.http_helpers import ProviderError
from workflows import audio


class SpeechProviderRoutingTests(unittest.TestCase):
    def test_selected_cartesia_is_used_without_calling_elevenlabs(self):
        generated = {
            "audio_bytes": b"wav data",
            "mime_type": "audio/wav",
            "model": "sonic-3.6",
            "provider": "cartesia",
            "provider_cost_cents": 0,
        }
        with patch.object(audio.cartesia, "is_configured", return_value=True), patch.object(
            audio.cartesia, "generate", return_value=generated
        ) as selected, patch.object(audio.elevenlabs, "generate") as other_provider:
            result = audio._generate_speech({
                "provider": "cartesia",
                "text": "Hello",
                "voiceId": "cartesia_voice",
                "model": "sonic-3.6",
            })

        self.assertEqual(result, generated)
        selected.assert_called_once_with({
            "text": "Hello",
            "voice_id": "cartesia_voice",
            "model_id": "sonic-3.6",
            "language": None,
        })
        other_provider.assert_not_called()

    def test_cartesia_failure_does_not_switch_to_elevenlabs(self):
        with patch.object(audio.cartesia, "is_configured", return_value=True), patch.object(
            audio.cartesia, "generate", side_effect=ProviderError("Cartesia Free quota unavailable")
        ), patch.object(audio.elevenlabs, "generate") as other_provider:
            with self.assertRaises(ProviderError):
                audio._generate_speech({
                    "provider": "cartesia",
                    "text": "Hello",
                    "voiceId": "cartesia_voice",
                    "model": "sonic-3.6",
                })
        other_provider.assert_not_called()

    def test_cartesia_unconfigured_does_not_use_configured_elevenlabs(self):
        with patch.object(audio.cartesia, "is_configured", return_value=False), patch.object(
            audio.elevenlabs, "is_configured", return_value=True), patch.object(
            audio.elevenlabs, "generate"
        ) as other_provider:
            with self.assertRaises(ProviderError):
                audio._generate_speech({
                    "provider": "cartesia",
                    "text": "Hello",
                    "voiceId": "cartesia_voice",
                    "model": "sonic-3.6",
                })
        other_provider.assert_not_called()


if __name__ == "__main__":
    unittest.main()
