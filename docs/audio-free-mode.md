# Free-only Audio Studio

This branch adds an Audio Studio to the existing Next.js + FastAPI + PostgreSQL application. It reuses the existing jobs, credit reservation, asset and storage pipeline. It does not replace the database schema or rebuild the application.

## What is available

- **Speech:** Cartesia Sonic 3.6 is the primary provider. If its Free quota check fails or the request fails, the worker can try ElevenLabs only after its independent Free-account and quota checks pass.
- **Dialogue:** Uses the existing ElevenLabs text-to-dialogue endpoint, with a Free-tier quota preflight.
- **Sound effects:** Uses ElevenLabs' sound-generation endpoint. A duration is mandatory because the current official guidance prices specified-duration effects at 40 credits per second.
- **Music:** The UI produces 5–30 second musical elements/loops through the sound-generation endpoint. It does **not** call ElevenLabs' full Music API because that API is restricted to paid subscribers. This short-loop feature is not equivalent to full-song generation.

## Environment

Copy the current worker environment template to `worker/.env`, preserve the existing database, worker and storage settings, and set only the audio values you need:

```dotenv
AUDIO_FREE_ONLY=true

CARTESIA_API_KEY=
CARTESIA_ADMIN_API_KEY=
CARTESIA_FREE_TIER_CONFIRMED=true
CARTESIA_FREE_MONTHLY_CREDIT_LIMIT=20000
CARTESIA_VERSION=2026-08-14
CARTESIA_DEFAULT_VOICE_ID=

ELEVENLABS_API_KEY=
ELEVENLABS_FREE_TIER_CONFIRMED=true
ELEVENLABS_FREE_MONTHLY_CREDIT_LIMIT=10000
ELEVENLABS_FREE_FALLBACK_VOICE_ID=
```

Only set a `*_FREE_TIER_CONFIRMED=true` flag after checking that the matching provider account actually uses its Free plan. Leave the flag empty/false otherwise. Cartesia quota preflight needs an admin API key so the worker can read usage; if that check is unavailable, Cartesia generation fails closed.

Restart the FastAPI worker after changing `worker/.env`. Provider keys must stay in the worker environment and must never be exposed to the browser or committed to Git.

## Free-only guards

- Cartesia requests are blocked if free-only mode, Free-plan confirmation, API keys, or the account-wide monthly quota check are missing.
- ElevenLabs generation is blocked unless the account reports an active Free tier, a valid usage limit, and enough remaining monthly quota.
- Monthly caps cannot be configured above the published Free allowances in the code (20,000 Cartesia TTS credits and 10,000 ElevenLabs credits).
- Each generation POST is sent once. Generation POSTs are not automatically retried after a timeout because the provider may already have processed the request.
- Sound effects and music loops require an explicit duration and reserve a conservative estimate before sending the request.
- Audio jobs are created with zero application credits in this branch, while the existing jobs, assets and storage records remain in use.

These checks are fail-closed safeguards, not a substitute for reviewing billing settings on the provider account. Keep pay-as-you-go/overage disabled in provider dashboards. They also cannot prevent someone from using a provider key outside this application.

## Licensing limitations

The Free plans are intended for evaluation/personal use and do not automatically include commercial-use rights. Review the current provider terms before using outputs in a commercial product or client work. Do not treat an audio provider as commercially licensed just because its API is available on a Free plan.
