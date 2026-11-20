---
name: telegram-connect-ops
description: Diagnose and verify Oisha Connect login, QR, 2FA, and disconnect on Hetzner without exposing secrets or running a local Telegram session.
---

# Oisha Connect operations

## Scope

Use for `/api/connect/app`, browser Telegram login, QR/2FA completion, and disconnect verification. Owner authenticates and scans QR; the agent has no personal Telegram account.

## Verified deployment context

Verified 2026-11-19: Hetzner `2.29.198.0`, checkout `/home/deploy/oisha-os`, systemd `oisha.service`, local API `127.0.0.1:8080`. Recheck these before later operations. Production sessions must never run locally.

## Diagnosis

1. Check deployed SHA and tracked worktree changes before deploying. Search other refs when an implementation is absent in the current checkout; Connect initially landed in PR #1099.
2. Inspect sanitized HTTP path/status counts. Never print login state tokens, passwords, cookies, encryption keys, or session strings from logs.
3. Browser login requires a strong `JWT_SECRET`. QR session storage separately requires the Fernet `TG_CONNECT_SESSION_KEY`; generation instructions are in `.env.example`. Only configure secrets with owner authorization, directly on the server, without printing values. Preserve valid existing keys. The deploy workflow rebuilds `.env`; retain these exact keys in its private preservation filter to avoid losing browser login or encrypted-session access on later deploys.
4. An approved login followed by poll HTTP 503 can mean the signing key is missing. `handle_telegram_poll` currently consumes the state before validating that key, so the next poll may say expired. After fixing configuration, owner must open a fresh login page.
5. For apparently stalled QR/2FA completion, read only the owner's account `status`, `connected_at`, `revoked_at` and audit `action`, `created_at`. Do not select or decrypt session fields. A persisted `connected` row means owner should refresh the page before attempting another QR login.
6. Session persistence must complete before success is reported. Dialog discovery is optional follow-up work and must not block the connection result. Test with a stalled dialog response.

## Verification

After a restart, recheck `/readyz` after startup settles: require `status=ready`, database `ok`, userbot `authorized`, and inspect other checks. Initial `active` or `ready:true` alone can coexist with degraded startup checks. Check actual Connect HTML, not only HTTP 200.

Automated regression checks: `SKIP_LIVE=1 python -m pytest tests/test_tg_connect.py tests/test_tg_connect_mcp.py tests/test_handlers_connect.py -q` and `node --test tests/test_connect_completion.cjs`; run repository pre-flight before PR.

Real acceptance remains separate: owner scans QR / enters 2FA, verifies frontend connected state and Telegram Settings → Devices → Oisha Connect, then presses Uzish and verifies the device disappears. Never claim this passed from synthetic tests or a button click alone.
