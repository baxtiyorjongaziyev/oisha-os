# Oisha two-head Telegram runtime

## Runtime ownership

- Oracle VM owns the Telethon user-account head and persistent schedulers.
- Google Cloud Run owns only the `@jonairobot` Aiogram webhook head.
- `USERBOT_SESSION_STRING`, `API_ID`, and `API_HASH` must never be supplied to
  the Cloud Run service.
- Oracle sets `TELEGRAM_BOT_INGRESS_MODE=disabled`; Cloud Run sets it to
  `webhook`. Only one process may receive Bot API updates.

## Required Secret Manager entries

- `BOT_TOKEN`
- `TELEGRAM_WEBHOOK_SECRET`
- `TURSO_DATABASE_URL`
- `TURSO_AUTH_TOKEN`

The deploy script references secret names and never reads secret values into
command-line arguments or repository files.

## Cost and rollout guard

Deployment is blocked unless `OISHA_ALLOW_GCP=1` is explicitly set after owner
approval. The service uses zero minimum instances, one maximum instance, one
request at a time, 512 MiB RAM, and request-based Cloud Run execution.

After deployment, verify `/healthz` returns:

- `status: ok`
- `head: aiogram_bot_token`
- `ingress: webhook`
- `userbot_enabled: false`
- `webhook_registered: true`

Rollback: set Oracle `TELEGRAM_BOT_INGRESS_MODE=polling` only after the Cloud
Run service is disabled and Telegram's webhook is deleted. Never run both
receivers simultaneously.
