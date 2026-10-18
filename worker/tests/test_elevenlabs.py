"""Offline tests for ElevenLabs voice and dialogue generation."""
import os
import unittest
from unittest.mock import Mock, patch

import httpx

from providers import elevenlabs
from providers.http_helpers import ProviderError
from workflows import audio


class ElevenLabsProviderTests(unittest.TestCase):
    def test_dialogue_keeps_turn_voice_pairing_and_emotion_tag(self):
        turns = elevenlabs.normalize_dialogue_inputs([
            {"text": "Hello", "voice_id": "voice_A", "emotion": "cheerfully"},
            {"text": "Hi", "voice_id": "voice_B", "emotion": ""},
        ])
        self.assertEqual(turns, [
            {"text": "[cheerfully] Hello", "voice_id": "voice_A"},
            {"text": "Hi", "voice_id": "voice_B"},
        ])

    def test_dialogue_rejects_invalid_bounds_and_emotion_markup(self):
        with self.assertRaises(ProviderError):
            elevenlabs.normalize_dialogue_inputs([{ "text": "one", "voice_id": "a" }])
        with self.assertRaises(ProviderError):
            elevenlabs.normalize_dialogue_inputs([
                {"text": "one", "voice_id": "a", "emotion": "[angry]"},
                {"text": "two", "voice_id": "b"},
            ])
        with self.assertRaises(ProviderError):
            elevenlabs.normalize_dialogue_inputs([
                {"text": "x" * 1000, "voice_id": "a"},
                {"text": "y" * 1001, "voice_id": "b"},
            ])

    def test_dialogue_posts_expected_official_payload_and_returns_audio_bytes(self):
        response = httpx.Response(
            200,
            content=b"audio bytes",
            headers={"content-type": "audio/mpeg", "request-id": "req-123"},
            request=httpx.Request("POST", "https://api.elevenlabs.io/v1/text-to-dialogue"),
        )
        with patch.dict(os.environ, {"ELEVENLABS_API_KEY": "secret-test"}), patch.object(
            elevenlabs, "_reserve_free_credits"
        ), patch.object(
            elevenlabs._CLIENT, "post", return_value=response
        ) as post:
            result = elevenlabs.generate_dialogue({
                "inputs": [
                    {"text": "Hello", "voice_id": "voice_A", "emotion": "warmly"},
                    {"text": "Hi", "voice_id": "voice_B"},
                ],
                "language_code": "en",
                "seed": 123,
            })
        payload = post.call_args.kwargs["json"]
        self.assertEqual(payload["model_id"], "eleven_v3")
        self.assertEqual(payload["inputs"][0], {"text": "[warmly] Hello", "voice_id": "voice_A"})
        self.assertEqual(payload["inputs"][1], {"text": "Hi", "voice_id": "voice_B"})
        self.assertEqual(payload["language_code"], "en")
        self.assertEqual(payload["seed"], 123)
        self.assertEqual(result["audio_bytes"], b"audio bytes")
        self.assertEqual(result["provider_request_id"], "req-123")

    def test_single_generation_uses_allowlisted_model_and_audio_bytes(self):
        response = httpx.Response(
            200, content=b"mp3", headers={"content-type": "audio/mpeg"},
            request=httpx.Request("POST", "https://api.elevenlabs.io/v1/text-to-speech/voice_1"),
        )
        with patch.dict(os.environ, {"ELEVENLABS_API_KEY": "secret-test"}), patch.object(
            elevenlabs, "_reserve_free_credits"
        ), patch.object(
            elevenlabs._CLIENT, "post", return_value=response
        ) as post:
            result = elevenlabs.generate({"text": "Hello", "voice_id": "voice_1", "model": "eleven_flash_v2_5"})
        self.assertEqual(post.call_args.kwargs["json"]["model_id"], "eleven_flash_v2_5")
        self.assertEqual(result["extension"], "mp3")

    def test_read_timeout_is_not_retried(self):
        with patch.dict(os.environ, {"ELEVENLABS_API_KEY": "secret-test"}), patch.object(
            elevenlabs, "_reserve_free_credits"
        ), patch.object(
            elevenlabs._CLIENT, "post", side_effect=httpx.ReadTimeout("lost response")
        ) as post:
            with self.assertRaises(ProviderError):
                elevenlabs.generate({"text": "Hello", "voice_id": "voice_1"})
        post.assert_called_once()


class ElevenLabsFreeQuotaTests(unittest.TestCase):
    def setUp(self):
        self.old_state = (
            elevenlabs._FREE_USAGE_LAST_SERVER_COUNT,
            elevenlabs._FREE_USAGE_RESERVED,
            elevenlabs._FREE_USAGE_RESERVED_CHARACTERS,
            elevenlabs._FREE_USAGE_RESERVED_OTHER,
        )
        elevenlabs._FREE_USAGE_LAST_SERVER_COUNT = None
        elevenlabs._FREE_USAGE_RESERVED = 0
        elevenlabs._FREE_USAGE_RESERVED_CHARACTERS = 0
        elevenlabs._FREE_USAGE_RESERVED_OTHER = 0

    def tearDown(self):
        (
            elevenlabs._FREE_USAGE_LAST_SERVER_COUNT,
            elevenlabs._FREE_USAGE_RESERVED,
            elevenlabs._FREE_USAGE_RESERVED_CHARACTERS,
            elevenlabs._FREE_USAGE_RESERVED_OTHER,
        ) = self.old_state

    def _subscription_response(self, **overrides):
        data = {
            "tier": "free",
            "status": "active",
            "current_overage": {"amount": "0", "currency": "usd"},
            "max_credit_limit_extension": 0,
            "can_extend_character_limit": False,
            "has_open_invoices": False,
            "character_count": 10,
            "character_limit": 10000,
        }
        data.update(overrides)
        return httpx.Response(
            200,
            json=data,
            request=httpx.Request("GET", "https://api.elevenlabs.io/v1/user/subscription"),
        )

    def _environment(self):
        return {
            "AUDIO_FREE_ONLY": "true",
            "ELEVENLABS_FREE_TIER_CONFIRMED": "true",
            "ELEVENLABS_API_KEY": "secret-test",
            "ELEVENLABS_FREE_MONTHLY_CREDIT_LIMIT": "10000",
        }

    def test_paid_tier_is_rejected(self):
        with patch.dict(os.environ, self._environment()), patch.object(
            elevenlabs._CLIENT, "get", return_value=self._subscription_response(tier="starter")
        ):
            with self.assertRaises(ProviderError):
                elevenlabs._reserve_free_credits(10)

    def test_usage_based_overage_is_rejected(self):
        with patch.dict(os.environ, self._environment()), patch.object(
            elevenlabs._CLIENT, "get",
            return_value=self._subscription_response(
                max_credit_limit_extension=10000,
                can_extend_character_limit=True,
            ),
        ):
            with self.assertRaises(ProviderError):
                elevenlabs._reserve_free_credits(10)

    def test_free_quota_exhaustion_is_rejected(self):
        with patch.dict(os.environ, self._environment()), patch.object(
            elevenlabs._CLIENT, "get",
            return_value=self._subscription_response(character_count=9999, character_limit=10000),
        ):
            with self.assertRaises(ProviderError):
                elevenlabs._reserve_free_credits(2)

    def test_valid_free_tier_reserves_quota(self):
        with patch.dict(os.environ, self._environment()), patch.object(
            elevenlabs._CLIENT, "get", return_value=self._subscription_response()
        ):
            elevenlabs._reserve_free_credits(25)
        self.assertEqual(elevenlabs._FREE_USAGE_RESERVED, 25)


class AudioWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.job = {"id": "job-1", "user_id": "user-1", "project_id": "project-1", "type": "voice_generator", "input": {"text": "Hello", "creditCost": 4}}
        self.conn = Mock()
        self.conn.__enter__ = Mock(return_value=self.conn)
        self.conn.__exit__ = Mock(return_value=False)
        self.conn.transaction.return_value.__enter__ = Mock(return_value=None)
        self.conn.transaction.return_value.__exit__ = Mock(return_value=False)

    def test_success_stores_asset_completes_and_consumes_reservation_once(self):
        result = {"audio_bytes": b"audio", "mime_type": "audio/mpeg", "model": "eleven_multilingual_v2", "provider_request_id": "req-1"}
        with patch.object(audio.elevenlabs, "generate", return_value=result) as generate, \
             patch.object(audio, "store_audio_output", return_value=("/storage/a.mp3", "mp3")), \
             patch.object(audio, "consume_audio_reservation") as consume, \
             patch.object(audio, "insert_asset", return_value="asset-1") as insert_asset, \
             patch.object(audio, "complete_job") as complete, \
             patch.object(audio, "fail_job") as fail, \
             patch.object(audio, "release_audio_reservation") as release, \
             patch.object(audio.db, "connect", return_value=self.conn):
            audio.run(self.job)
        generate.assert_called_once()
        consume.assert_called_once_with(self.conn, "job-1")
        insert_asset.assert_called_once_with(self.conn, self.job, "audio", "/storage/a.mp3")
        complete.assert_called_once()
        self.assertEqual(complete.call_args.args[3], 0)  # Free-only mode must not debit app credits.
        fail.assert_not_called()
        release.assert_not_called()

    def test_provider_failure_fails_job_and_releases_reservation(self):
        with patch.object(audio.elevenlabs, "generate", side_effect=ProviderError("provider failed")), \
             patch.object(audio, "fail_job") as fail, \
             patch.object(audio, "release_audio_reservation") as release, \
             patch.object(audio.db, "connect", return_value=self.conn):
            audio.run(self.job)
        fail.assert_called_once()
        release.assert_called_once_with(self.conn, "job-1")

    def test_storage_failure_does_not_call_provider_again(self):
        result = {"audio_bytes": b"audio", "mime_type": "audio/mpeg", "model": "eleven_multilingual_v2"}
        with patch.object(audio.elevenlabs, "generate", return_value=result) as generate, \
             patch.object(audio, "store_audio_output", side_effect=OSError("disk full")), \
             patch.object(audio, "fail_job") as fail, \
             patch.object(audio, "release_audio_reservation") as release, \
             patch.object(audio.db, "connect", return_value=self.conn):
            audio.run(self.job)
        generate.assert_called_once()
        fail.assert_called_once()
        release.assert_called_once_with(self.conn, "job-1")


if __name__ == "__main__":
    unittest.main()
