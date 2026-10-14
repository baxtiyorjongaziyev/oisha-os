---
name: capi-platform
description: Build and verify Oisha internal CAPI intake, console and JonBranding website producer without claiming unverified Meta activation.
---

# CAPI platform

Verified local workflow, 2026-10-14: `docs/capi-platform.md` is the contract.
Reuse existing CRM sender/status mapping. Website uses a dedicated server bearer;
the exact intake path must bypass central session middleware while its route
authenticates that bearer. Include central middleware in intake tests. Never
put the ingest credential in the browser or expose matching payloads in the panel.

Persist intake before acknowledgement. Keep event ID and original timestamp on
retry, atomically lease delivery, and isolate dataset/test/live targets. Hash
phone/email before storage. Consent is explicit. Positive finite Purchase value
and known currency are mandatory. Queue acceptance and Meta acceptance differ:
only `events_received=1` marks sent; it does not prove matching or attribution.

Run isolated SQLite + mocked Meta tests, authorization tests, Ruff and focused
Bandit. Verify website `npm run verify` and build for producer changes. Browser
inspection of an unavailable-data view proves rendering only. Full repo pytest
and Bandit gates remain mandatory before PR. Preserve unrelated dirty files.
Record local/committed/pushed/deployed independently. Production activation and
external test sends require owner authorization; credentials/security prompts
remain with the owner. Never start local production userbot/session.
