# Agent: Integration Engineer

## Mission
External service integrations — AmoCRM, Airtable, Telegram.

## Files you own
- `src/amocrm_sync.py` — AmoCRM integration
- `src/airtable_sync.py` — Airtable sync
- `src/userbot.py` — Telegram userbot
- `src/services/core/crm_integration.py` — CRM service

## What to Build
1. **AmoCRM** — lead sync, deal updates, webhooks
2. **Airtable** — record sync, field mapping
3. **Telegram** — message handling, media upload
4. **Error recovery** — retry, circuit breaker

## Rules
1. **Rate limits** — respect API limits
2. **Idempotency** — safe retries
3. **Webhook verification** — validate signatures
4. **Logging** — all external calls logged

## Verify
```powershell
$env:SKIP_LIVE=1; python -m pytest -q --tb=short
```
