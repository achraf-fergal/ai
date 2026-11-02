"""Regression tests ensuring empty audio is never marked as a saved asset."""
import io
import wave
import unittest

from providers.cartesia import _normalize_wav_header
from workflows.common import validate_audio_payload


def make_wav(pcm: bytes, *, sample_rate: int = 22050) -> bytes:
    output = io.BytesIO()
    with wave.open(output, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(sample_rate)
        audio.writeframes(pcm)
    return output.getvalue()


class AudioPayloadValidationTests(unittest.TestCase):
    def test_accepts_non_silent_pcm_wav(self):
        pcm = b"".join((value).to_bytes(2, "little", signed=True) for value in (100, -100, 250, -250) * 500)
        validate_audio_payload(make_wav(pcm), "audio/wav")


    def test_repairs_cartesia_streaming_wav_size_placeholders(self):
        pcm = b"".join((value).to_bytes(2, "little", signed=True) for value in (100, -100, 250, -250) * 500)
        streaming_wav = bytearray(make_wav(pcm))
        streaming_wav[4:8] = (0xFFFFFFFF).to_bytes(4, "little")
        streaming_wav[40:44] = (0xFFFFFFFF).to_bytes(4, "little")

        repaired = _normalize_wav_header(bytes(streaming_wav))
        validate_audio_payload(repaired, "audio/wav")

        with wave.open(io.BytesIO(repaired), "rb") as audio:
            self.assertEqual(audio.getnframes(), len(pcm) // 2)
            self.assertAlmostEqual(audio.getnframes() / audio.getframerate(), len(pcm) / 44100, places=3)

    def test_rejects_wav_with_no_frames(self):
        with self.assertRaisesRegex(ValueError, "no audio frames"):
            validate_audio_payload(make_wav(b""), "audio/wav")

    def test_rejects_wav_containing_only_silence(self):
        with self.assertRaisesRegex(ValueError, "silent WAV"):
            validate_audio_payload(make_wav(b"\x00\x00" * 500), "audio/wav")

    def test_rejects_truncated_wav(self):
        wav_data = make_wav(b"\x01\x00" * 1000)
        with self.assertRaises(ValueError):
            validate_audio_payload(wav_data[:-100], "audio/wav")

    def test_rejects_html_or_json_masquerading_as_mp3(self):
        with self.assertRaisesRegex(ValueError, "invalid or empty MP3"):
            validate_audio_payload(b'{"error":"not audio"}' * 30, "audio/mpeg")


if __name__ == "__main__":
    unittest.main()
