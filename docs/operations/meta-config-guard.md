# Meta configuration presence guard

Startup (API lifespan and Instagram scheduler), each backfill cycle, `/healthz`
and `/readyz` inspect effective local runtime configuration. No Graph API call,
credential modification, disk write, or outbound message is performed.

Required keys: `META_PAGE_ACCESS_TOKEN`, `META_INSTAGRAM_USER_ID` (or
`META_INSTAGRAM_ACCOUNT_ID`), `META_APP_SECRET`, `META_VERIFY_TOKEN` (or
`INSTAGRAM_VERIFY_TOKEN`). Blank/whitespace and empty SecretStr values are missing.
App ID, Page ID and Graph version are not required by the comment reply path;
Graph version has an existing default. Disabling backfill does not disable the
webhook, so configuration checks remain active.

Health exposes only `checks.meta_config.configured` and canonical `missing_keys`.
Missing configuration adds `instagram_not_configured`; liveness/readiness are
degraded (HTTP 200 if otherwise healthy), avoiding restart loops. Other blocking
failures retain HTTP 503. One ERROR log per continuous outage per process gives
the missing key names and recovery steps. A successful check rearms the alert;
multiple workers/restarts can each log once. No Telegram alert is sent.

Operator action: inspect the service environment source, restore missing keys via
the approved secret workflow, restart, then confirm `missing_keys: []`. Never
paste values into logs. This patch does not authorize that operation.

Scope: runtime presence only, not credential validity, token rotation, permissions
or delivery. Changes to an on-disk .env while a process retains cached settings
are detected after restart, not before. Values/hashes are never exposed.

Offline verification: `python -m pytest -q tests/test_meta_config_guard.py
tests/test_production_readiness.py tests/test_instagram_graph_client.py
tests/test_instagram_integration.py` with `SKIP_LIVE=1`.
