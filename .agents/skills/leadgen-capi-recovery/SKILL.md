---
name: leadgen-capi-recovery
description: Diagnose and verify Meta Lead CAPI dispatch and retry independently of CRM, Sheets and Telegram delivery.
---

# Leadgen CAPI recovery

Use for Lead Ads CAPI dispatch/retry changes. Read AGENTS.md and code standards,
preserve dirty work and locks, and keep ALLOW_LOCAL_RUN=0 and SKIP_LIVE=1.
Do not start a userbot or read .env/session files.

## Durable dispatch contract

- Save CAPI intent in the existing delivery DB transaction with the CRM checkpoint.
- Run Graph requests outside the routing lock, with tracked tasks and bounded concurrency.
- Keep intent through cancellation, restart, send failure or a fresh pending duplicate claim.
- Remove intent only after a sent result or a duplicate confirmed as sent in capi_events.
- Run recovery even when CRM, Sheets and Telegram delivery are all complete.
- Preserve retry backoff when importing failed/stale legacy claims.
- Disabled CAPI sends nothing; retain existing queued intent. Do not silently backfill
  historical successful CRM deliveries that have no CAPI intent or failed claim.
- Store IDs and retry state in the outbox; do not persist phone/email, credentials or payloads.
- Source classification, repeat-contact and creative tags describe separate properties.

## Verification

Use synthetic fixtures and mocked Graph requests. Exercise failed-then-successful
send, no-dispatch restart, cancellation after claim, fresh pending vs sent duplicates,
disabled configuration, legacy claims, retry backoff and bounded parallel dispatch.
Check that router channels finish while CAPI waits and the checkpoint survives.
Run tests/test_meta_capi.py and every tests/*leadgen*.py, then full pytest and Bandit
as required by AGENTS.md. Local tests do not prove live Meta delivery.
Keep this skill identical in .claude/skills and .agents/skills; after skill edits,
run `python scripts/sync_agent_skills.py --check` and tests/test_agent_skills_sync.py.

Verified 2026-10-12 by tests/test_leadgen_capi_recovery.py and focused suites.
Implementation: src/services/core/instagram/leadgen_capi.py and leadgen_capi_outbox.py.
Merge and production deployment remain owner approval boundaries.
