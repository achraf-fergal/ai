"""Offline tests for Cartesia TTS and free-only quota gates."""
import os
import unittest
from unittest.mock import patch

import httpx

from providers import cartesia
from providers.http_helpers import ProviderError


class CartesiaProviderTests(unittest.TestCase):
    def setUp(self):
        self.old_state = (
            cartesia._LAST_USAGE_SNAPSHOT,
            cartesia._PENDING_LOCAL_CREDITS,
            cartesia._PENDING_MONTH,
        )
        cartesia._LAST_USAGE_SNAPSHOT = None
        cartesia._PENDING_LOCAL_CREDITS = 0
        cartesia._PENDING_MONTH = None

    def tearDown(self):
        (
            cartesia._LAST_USAGE_SNAPSHOT,
            cartesia._PENDING_LOCAL_CREDITS,
            cartesia._PENDING_MONTH,
        ) = self.old_state

    def test_tts_uses_official_bytes_endpoint_and_normalizes_wav(self):
        response = httpx.Response(
            200,
            content=b"wav-bytes",
            headers={"content-type": "audio/wav", "request-id": "cartesia-req-1"},
            request=httpx.Request("POST", "https://api.cartesia.ai/tts/bytes"),
        )
        with patch.dict(os.environ, {
            "AUDIO_FREE_ONLY": "true",
            "CARTESIA_FREE_TIER_CONFIRMED": "true",
            "CARTESIA_API_KEY": "test-key",
            "CARTESIA_ADMIN_API_KEY": "test-admin-key",
        }), patch.object(cartesia, "_assert_free_budget") as quota_check, patch.object(
            cartesia._CLIENT, "post", return_value=response
        ) as post:
            result = cartesia.generate({
                "text": "Hello world",
                "voice_id": "voice_123",
                "model_id": "sonic-3.6",
            })

        quota_check.assert_called_once_with(len("Hello world"))
        self.assertEqual(post.call_args.args[0], "https://api.cartesia.ai/tts/bytes")
        payload = post.call_args.kwargs["json"]
        self.assertEqual(payload["model_id"], "sonic-3.6")
        self.assertEqual(payload["transcript"], "Hello world")
        self.assertEqual(payload["voice"], "voice_123")
        self.assertEqual(payload["output_format"]["container"], "wav")
        self.assertEqual(result["audio_bytes"], b"wav-bytes")
        self.assertEqual(result["mime_type"], "audio/wav")
        self.assertEqual(result["provider"], "cartesia")
        self.assertEqual(result["provider_request_id"], "cartesia-req-1")

    def test_generation_is_blocked_when_free_only_switch_is_false(self):
        with patch.dict(os.environ, {
            "AUDIO_FREE_ONLY": "false",
            "CARTESIA_FREE_TIER_CONFIRMED": "true",
            "CARTESIA_API_KEY": "test-key",
            "CARTESIA_ADMIN_API_KEY": "test-admin-key",
        }), patch.object(cartesia._CLIENT, "post") as post:
            self.assertFalse(cartesia.is_configured())
            with self.assertRaises(ProviderError):
                cartesia.generate({"text": "Hello", "voice_id": "voice_123"})
        post.assert_not_called()

    def test_generation_fails_closed_when_admin_quota_key_is_missing(self):
        with patch.dict(os.environ, {
            "AUDIO_FREE_ONLY": "true",
            "CARTESIA_FREE_TIER_CONFIRMED": "true",
            "CARTESIA_API_KEY": "test-key",
        }, clear=True), patch.object(cartesia._CLIENT, "post") as post:
            with self.assertRaises(ProviderError):
                cartesia._assert_free_budget(10)
        post.assert_not_called()

    def test_monthly_cap_blocks_before_post(self):
        with patch.dict(os.environ, {
            "AUDIO_FREE_ONLY": "true",
            "CARTESIA_FREE_TIER_CONFIRMED": "true",
            "CARTESIA_API_KEY": "test-key",
            "CARTESIA_ADMIN_API_KEY": "test-admin-key",
            "CARTESIA_FREE_MONTHLY_CREDIT_LIMIT": "20000",
        }), patch.object(cartesia, "_current_month_usage", return_value=20_000), patch.object(
            cartesia._CLIENT, "post"
        ) as post:
            with self.assertRaises(ProviderError):
                cartesia._assert_free_budget(1)
        post.assert_not_called()


if __name__ == "__main__":
    unittest.main()
