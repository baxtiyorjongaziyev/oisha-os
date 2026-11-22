# Oisha Agency MCP — read-only business gateway

Status: **deployed in production** at `https://oisha.jonbranding.uz/api/agency-mcp`
(verified 2026-11-21). This endpoint is separate from personal Telegram Connect
MCP and the legacy stdio MCP server.

## What it does

An authenticated AI client can list the datasets its principal is allowed to
see and read them through the existing Oisha production services. The gateway
exposes exactly two tools:

- `list_business_sources` — sources allowed by the caller's scopes.
- `read_business_source` — one whitelisted dataset, bounded response.

There is no SQL, arbitrary URL fetch, write, delete, message-send, or payment
operation. Request bodies are capped at 16 KB, results at 128 KB, and callers
are limited to 60 requests per minute per principal.

## Production status matrix (2026-11-21)

Verified through `POST /api/agency-mcp` on the production host.

| Source | Status | Evidence / limitation |
| --- | --- | --- |
| sales_report | Works | AmoCRM, November 2026: 201 new leads, 29 won, 50.13 mln won. ~25 s cold response. |
| pipeline | Works | AmoCRM + finance overview. ~13 s cold response. |
| leads | Works | Oisha CRM leads, capped by `limit`. |
| tasks | Works, owner scope only | Requires `system:read`; intentionally **not** granted to the AI token. Verified with owner secret. |
| marketing | Partial | Meta spend cache is stale (last row 2026-10-16, 117 rows). `status:"partial"`, `spend:null`; CRM attribution has 49 leads. |
| finance | Works, empty data | Hisobchi Google Sheets `Pul oqimi` sheet has 0 rows. Returns real zeros with `source_status:"fresh"`. |
| finance_transactions | Works, empty data | Same sheet; `transactions: []`. |
| sales_quality | Works | 200 analyzed calls in the 30-day window, average score 53.4. |
| conversion | Works after this PR | Production before the fix returned `source_unavailable`; route called removed engine methods. Fixed to `team_summary` / `conversion_trend` / `fetch_volumes`. |
| projects | Works, empty data | `projects` table exists, 0 rows. |
| team | Works, owner scope only | Requires `users:manage:limited`; intentionally **not** granted to the AI token. Verified with owner secret: 1 employee. |

Known external blockers:

- Meta Ads sync is stopped because `META_AD_ACCOUNT_ID` is missing in `.env`
  and the existing page token has no `ads_read` permission. `marketing`
  therefore cannot return current spend until the owner supplies an ad account
  ID and a token with `ads_read`.
- Finance numbers stay zero until the `Hisobchi AI` Google Sheet is populated.
  The gateway reports the real source status, it does not invent values.
- Raw MoiZvonki call statistics (answer rate, duration per raw call) are not
  exposed by the gateway. Only scored `call_analyses` data is available via
  `sales_quality` and `conversion`.

## Endpoint and auth

```
POST https://oisha.jonbranding.uz/api/agency-mcp
Authorization: Bearer <service-token>
Content-Type: application/json
```

JSON-RPC methods: `initialize`, `ping`, `tools/list`, `tools/call`.
This is a stateless, POST-only MCP endpoint using JSON responses.

The production AI token is stored on the server at
`/home/deploy/oisha-os/.secrets/agency-mcp-token` (mode 600) and configured
through `OISHA_SERVICE_TOKENS_JSON` in `.env` (mode 600). Never commit the
token, paste it into a chat, or put it in a URL.

Current AI principal scopes:

```
mcp:read, dashboard:read, lead:read:all, marketing:read,
call:read:all, finance:read
```

`tasks` and `team` are deliberately excluded: they need `system:read` and
`users:manage:limited`, which are broader than an analytics agent needs.

### Rotate the token

1. Generate a new random token locally, never in a chat.
2. Add it to `OISHA_SERVICE_TOKENS_JSON` in `.env` next to the old entry.
3. Restart `oisha`, verify `initialize` with the new token.
4. Remove the old entry, restart again, verify the old token returns 401.
5. Update the client configuration and the `.secrets/agency-mcp-token` file.

`.env` and the secret file must stay mode 600. Back up `.env` before editing.

## Client connections

### Claude (works today)

Claude custom connectors support a fixed `Authorization` request header, so
the bearer token works without OAuth.

1. Open **Customize → Connectors → Add custom connector**.
2. Name: `Oisha Business`.
3. URL: `https://oisha.jonbranding.uz/api/agency-mcp`.
4. Authentication: **No sign in**.
5. Under **Request headers**, add:
   - Name: `Authorization`
   - Value: `Bearer <token>`
6. Add the connector, then enable it per conversation.

Team/Enterprise owners add the connector under **Organization settings →
Connectors** first, then members connect individually.

### Codex (works today)

Use an environment variable so the token is not written into `config.toml`:

```toml
[mcp_servers.oisha]
url = "https://oisha.jonbranding.uz/api/agency-mcp"
bearer_token_env_var = "OISHA_MCP_TOKEN"
tool_timeout_sec = 120
```

Set `OISHA_MCP_TOKEN` in the shell that starts Codex. `tool_timeout_sec` is
raised because `sales_report` and `pipeline` can take 10–30 seconds on a cold
cache.

### ChatGPT (blocked without OAuth)

ChatGPT custom MCP connections require OAuth 2.1 and do not accept custom API
keys or bearer tokens. Full custom MCP is available on Business and
Enterprise/Edu; Pro can connect read/fetch servers; Plus has no supported
direct custom MCP path.

This gateway is bearer-only and does **not** implement an OAuth authorization
server. Connecting it to ChatGPT requires one of:

1. Implementing OAuth 2.1 resource-server metadata, protected-resource
   metadata, and an authorization server (recommended for company-wide use).
2. Putting an OAuth-capable MCP gateway in front of this endpoint.

Do not upgrade a ChatGPT plan before that work is done.

## Security verification

| Check | Result |
| --- | --- |
| No token | `401 {"detail":"Unauthorized"}` |
| Wrong token | `401 {"detail":"Unauthorized"}` |
| Valid token, `initialize` | `200`, protocol `2025-06-18` |
| Valid token, `tools/list` | Exactly two read-only tools |
| Source outside token scopes | `permission_denied`, no data leak |
| Write/delete/send tools | None exposed |
| Response size | Capped at 128 KB |
| Rate limit | 60 requests/minute/principal |
| Request size | Capped at 16 KB |
| Nginx | Strips `X-Oisha-Authenticated-User`; `/api/*` proxied to `127.0.0.1:8080` |

## Tests

Focused contract and security tests:

```bash
python -m pytest tests/test_agency_mcp.py tests/test_conversion_routes.py \
  tests/test_metasell_conversion.py tests/test_pr475_review_fixes.py -q
```

`tests/test_conversion_routes.py` covers the fixed conversion routes: overview,
trend, volume, seller card, missing DB, and revenue sync wiring.

## Operational notes

- The API and Telegram userbot run in one `oisha` systemd process. Any `.env`
  change requires `sudo systemctl restart oisha`.
- `OISHA_SERVICE_TOKENS_JSON` must be single-quoted JSON inside `.env` so
  systemd `EnvironmentFile` parses it correctly.
- `sales_report` and `pipeline` call AmoCRM live; expect 10–30 seconds on a
  cold cache. Client timeouts below 60 seconds may fail.
- Source data is returned as-is. Empty tables and stale caches are reported as
  empty/stale, never filled with synthetic values.

## Next steps

1. Merge and deploy the conversion route fix, then re-verify `conversion`.
2. Add `META_AD_ACCOUNT_ID` and a token with `ads_read`; run the Meta sync and
   confirm 30-day spend.
3. Populate the `Hisobchi AI` Google Sheet so finance returns real numbers.
4. Decide whether ChatGPT access is required. If yes, implement OAuth 2.1
   before promising ChatGPT connectivity.
5. Rotate the AI token on a schedule and after any client device change.
