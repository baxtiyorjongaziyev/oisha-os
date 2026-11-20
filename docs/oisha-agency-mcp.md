# Oisha Agency MCP — read-only business gateway

Status: **proposed in a PR**, not deployed. This endpoint is separate from
personal Telegram Connect MCP and the legacy stdio MCP server.

## What it does

An authenticated AI client can list the datasets its principal is allowed to
see and read them, using the existing Oisha production-backed services.

| Source | Backend | Required Oisha permissions |
| --- | --- | --- |
| sales_report | AmoCRM period reporter | mcp:read, dashboard:read |
| pipeline | Dashboard overview | mcp:read, dashboard:read, finance:read |
| leads | Oisha CRM leads | mcp:read, lead:read:all |
| tasks | CRM/FrogAgent tasks | mcp:read, system:read |
| marketing | Meta/AmoCRM attribution **local cache** | mcp:read, marketing:read |
| finance | Configured real finance source | mcp:read, finance:read |
| finance_transactions | Configured finance source | mcp:read, finance:read |
| sales_quality | Call analytics | mcp:read, call:read:all |
| conversion | MetaSell conversion | mcp:read, finance:read |
| projects | Oisha ERP project summary | mcp:read, finance:read |
| team | Oisha ERP HR summary | mcp:read, users:manage:limited |

**Important limits:**
- Not an unlimited database export. The tool cannot run arbitrary SQL, fetch
  arbitrary URLs, write CRM data, send messages, or retrieve credentials.
- A dataset will be unavailable when Oisha's underlying integration is offline
  or not configured. Real-time Meta Insights and full MoiZvonki historical
  call-detail exports are **not** implemented by this gateway.
- Individual client Telegram history remains behind the separate consent and
  approval-based Oisha Connect MCP.
- The route returns bounded responses (128 KB) and caps row-oriented data;
  use provider-native exports for large historical analyses.
- For company-wide use, do not provide everyone with an OWNER key. Create
  narrow scopes per connected agent.

## Endpoint and auth

POST https://oisha.jonbranding.uz/api/agency-mcp

JSON-RPC methods: initialize, ping, tools/list, tools/call.

This is a stateless, POST-only MCP endpoint using JSON responses.
Use **HTTPS and an Authorization: Bearer token**. Never place an API token in
the endpoint URL or share it inside a ChatGPT conversation.

Oisha already supports scoped service tokens with
OISHA_SERVICE_TOKENS_JSON. Generate a long random token using a secret manager
and store it in the deployment environment, not the Git repository.

Example **shape only** (replace placeholder locally, don't commit credentials):

    OISHA_SERVICE_TOKENS_JSON={
      "<random-service-token>": {
        "subject": "readonly-analytics-agent",
        "scopes": [
          "mcp:read", "dashboard:read", "lead:read:all",
          "system:read", "marketing:read", "finance:read",
          "call:read:all", "users:manage:limited"
        ]
      }
    }

Send JSON-RPC:

    {"jsonrpc":"2.0","id":1,"method":"initialize"}
    {"jsonrpc":"2.0","id":2,"method":"tools/list"}
    {"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"list_business_sources","arguments":{}}}
    {"jsonrpc":"2.0","id":4,"method":"tools/call","params":{"name":"read_business_source","arguments":{"source":"sales_report","period":"monthly"}}}
    {"jsonrpc":"2.0","id":5,"method":"tools/call","params":{"name":"read_business_source","arguments":{"source":"marketing","start_date":"2026-10-20","end_date":"2026-11-20"}}}

## Before deployment

1. Review the PR and run its Python contract/security tests and existing API
   security regression suite; do not deploy on failed checks.
2. Enable HTTPS, a dedicated scoped service token, rate limiting, and service
   logs without bearer tokens or customer payloads.
3. Verify every source with **real** credentials and production-like data.
   Do not represent unavailable sources or placeholders as live facts.
4. For ChatGPT Business/Enterprise custom MCP plugins, verify the current
   platform's OAuth and MCP protocol requirements. This bearer-only endpoint
   does **not** implement an OAuth authorization server.
5. Test the upstream backend and proxy response on a staging environment.
6. Deploy with an owner-approved change and audit the resulting access.

## ChatGPT subscription note (November 2026)

OpenAI's current custom-MCP documentation states that **Plus does not offer
direct custom MCP connections**. Pro has limited read/fetch options; full
custom MCP with write support is a Business/Enterprise/Edu feature.
The Oisha gateway can still be used by compatible external MCP clients.
Do not upgrade plans before the backend, authentication, and staging tests
work.
