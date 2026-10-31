# Free-only Audio Studio

The application is focused on speech and multi-speaker dialogue. It uses the shared audio job, reservation, asset and storage pipeline. Music and sound effects remain deferred in the user interface. The fresh-install schema contains audio tables; older migration files and existing database tables are retained for compatibility without exposing their former services.

## What is available

- **Speech:** Choose Cartesia Sonic 3.6 or ElevenLabs. The worker uses only the selected provider; if its Free quota check or request fails, generation stops.
- **Dialogue:** Uses the existing ElevenLabs text-to-dialogue endpoint, with a Free-tier quota preflight.

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
```

Only set a `*_FREE_TIER_CONFIRMED=true` flag after checking that the matching provider account actually uses its Free plan. Leave the flag empty/false otherwise. Cartesia quota preflight needs an admin API key so the worker can read usage; if that check is unavailable, Cartesia generation fails closed.

Restart the FastAPI worker after changing `worker/.env`. Provider keys must stay in the worker environment and must never be exposed to the browser or committed to Git.

## Free-only guards

- Cartesia requests are blocked if free-only mode, Free-plan confirmation, API keys, or the account-wide monthly quota check are missing.
- ElevenLabs generation is blocked unless the account reports an active Free tier, a valid usage limit, and enough remaining monthly quota.
- The selected provider is used exclusively. Provider failures never switch the request to the other provider.
- Monthly caps cannot be configured above the published Free allowances in the code (20,000 Cartesia TTS credits and 10,000 ElevenLabs credits).
- Each generation POST is sent once. Generation POSTs are not automatically retried after a timeout because the provider may already have processed the request.
- Audio jobs are created with zero application credits in this branch, while the existing jobs, assets and storage records remain in use.

These checks are fail-closed safeguards, not a substitute for reviewing billing settings on the provider account. Keep pay-as-you-go/overage disabled in provider dashboards. They also cannot prevent someone from using a provider key outside this application.

## Offline regression tests

Run these from the `worker` folder on Windows after installing the existing worker requirements:

If your terminal is already in the repository root, use:

```powershell
cd worker
.\\.venv\\Scripts\\python.exe -m unittest tests.test_cartesia tests.test_elevenlabs
```

These tests mock provider HTTP calls and should not consume API credits. The full Next.js production build should also be run from `web` after the repository's normal local environment variables are configured.

## Licensing limitations

The Free plans are intended for evaluation/personal use and do not automatically include commercial-use rights. Review the current provider terms before using outputs in a commercial product or client work. Do not treat an audio provider as commercially licensed just because its API is available on a Free plan.
