# Oisha Telegram MCP integration design

**Date:** 2026-07-14  
**Status:** Approved concept; implementation pending written-spec review  
**Repositories:** `baxtiyorjongaziyev/oisha-os`, `baxtiyorjongaziyev/telegram-mcp`

## Goal

Add the Telegram MCP feature set to Oisha while preserving the production userbot, preventing unapproved mutations, and keeping Telegram credentials and MCP endpoints private.

## User policy

- Read, search, list, inspect, download metadata, and analyze operations may run without a separate approval.
- Every operation that changes Telegram state requires the owner's explicit approval.
- This includes sending, editing, deleting, forwarding, reacting, pinning, scheduling, managing contacts, changing profiles, and administering groups/channels.
- Approval is collected through Oisha's owner-only Telegram chat using **Approve** and **Cancel** inline buttons.
- No write operation may execute merely because an AI client calls a tool or says the user approved it.

## Considered approaches

### 1. Expose the upstream server directly

Run `telegram-mcp` with all tools and connect ChatGPT to it.

Rejected because its HTTP endpoint is unauthenticated and a model/client could invoke write tools without an Oisha-controlled approval gate.

### 2. Copy selected upstream tools into Oisha

Port tools one by one and add approval checks to each.

Rejected as the primary approach because it duplicates 80+ tools, increases maintenance cost, and makes upstream updates difficult.

### 3. Oisha approval gateway in front of a private upstream server — selected

Run the forked `telegram-mcp` server only on Oracle localhost. Oisha exposes a gateway that mirrors its tools. Read-only calls are proxied immediately; mutating calls become pending operations and execute only after the owner taps **Approve** in Telegram.

This retains the full upstream tool surface while centralizing policy, authentication, audit, and approvals in Oisha.

## Architecture

1. **Private Telegram MCP service**
   - Source: `baxtiyorjongaziyev/telegram-mcp`, installed from a pinned Git commit.
   - Transport: Streamable HTTP.
   - Bind: `127.0.0.1:8765/mcp`; never exposed directly by Nginx.
   - Credentials: dedicated `TELEGRAM_MCP_SESSION_STRING`, not the production `USERBOT_SESSION_STRING`.
   - One long-lived process owns the MCP Telegram session to avoid duplicated auth keys and parallel connection churn.

2. **Oisha MCP gateway**
   - Public/client-facing MCP endpoint owned by Oisha.
   - Discovers upstream tools and preserves schemas, descriptions, and MCP annotations.
   - Proxies tools marked `readOnlyHint=true`.
   - Intercepts every other tool and stores a pending operation instead of executing it.
   - Initial ChatGPT connection uses Secure MCP Tunnel. A public server URL remains disabled until standards-compliant OAuth is implemented.

3. **Approval service**
   - Stores a canonical payload: requester, tool name, validated arguments, target summary, risk summary, creation time, expiry, and status.
   - Sends an owner-only Telegram approval card with **Approve** and **Cancel** buttons.
   - Uses a random, single-use operation ID; button callbacks do not contain raw tool arguments.
   - Revalidates policy and arguments immediately before execution.
   - Executes exactly once after approval.
   - Default expiry: 15 minutes.
   - Duplicate clicks, expired requests, changed payloads, and non-owner callbacks fail closed.

4. **Audit log**
   - Records request, approval/cancellation, execution result, actor Telegram ID, timestamps, tool name, and redacted arguments.
   - Secrets, session strings, message bodies beyond a short safe preview, and downloaded file contents are never logged.
   - Failed and denied attempts are retained for security review.

## Data flow

### Read operation

ChatGPT → Oisha gateway → policy classifies read-only → private Telegram MCP → Telegram → structured result → ChatGPT.

### Mutating operation

ChatGPT → Oisha gateway → policy classifies mutation → pending operation stored → approval card sent to owner → owner taps **Approve** → operation revalidated → private Telegram MCP executes → result written to audit log → owner receives result notification.

The initial MCP call returns a structured `pending_approval` response with the operation ID and expiry. It never reports success before execution.

## Policy rules

- Classification is deny-by-default. A tool is automatic only when its trusted annotation and Oisha allowlist both classify it as read-only.
- Missing, malformed, or contradictory annotations are treated as mutation.
- File-system tools remain disabled unless explicit server roots are configured.
- Destructive actions such as deletion show a stronger warning and exact target preview.
- Bulk actions show count and scope. Approval applies only to the immutable stored payload.
- New tools appearing after an upstream update default to approval-required until reviewed.
- Rate limits apply per requester, tool, and target to prevent approval spam.

## Session and credential safety

- Never reuse or copy the active production userbot session file.
- Generate a separate Telegram session for the MCP service from the same account if needed; Telegram then sees it as a separate authorized device.
- Store API ID, API hash, session string, tunnel credentials, and approval secrets only in production secrets.
- Do not commit `.env`, session files, tokens, or generated QR/login artifacts.
- The private MCP port listens only on localhost and is blocked externally.

## Failure handling

- If the upstream service is unavailable, return a clear unavailable status; do not fall back to direct uncontrolled writes.
- If approval delivery fails, keep the operation pending until expiry and do not execute.
- If execution fails after approval, mark it failed and notify the owner; never retry destructive operations automatically.
- On restart, pending operations remain non-executable until their state is loaded and expiry rechecked.
- Loss of the audit database fails closed for mutations.

## Testing

- Unit tests for tool classification, immutable payload hashing, expiry, owner verification, single-use approval, redaction, and deny-by-default behavior.
- Contract tests against a fake upstream MCP server for tool discovery and proxying.
- Integration tests for read calls, approved send, approved delete, cancellation, expiry, duplicate callback, and upstream failure.
- Security checks ensure the upstream port is localhost-only and public routes cannot bypass the gateway.
- Pre-flight required by `AGENTS.md`: `SKIP_LIVE=1 python -m pytest -q --tb=short` and `bandit -r src/ -ll`.

## Rollout

1. Deploy the private upstream service with read tools only and validate session stability.
2. Enable Oisha gateway read operations through Secure MCP Tunnel.
3. Enable approval-gated send/edit/reaction operations.
4. Enable approval-gated delete and administrative operations.
5. Monitor audit logs and Telegram session health before broadening tool availability.
6. Public HTTPS MCP access is a later phase and requires OAuth; no unauthenticated public endpoint will be shipped.

## Success criteria

- ChatGPT can discover and use the upstream Telegram tool set through Oisha.
- Read-only operations complete without approval.
- No Telegram mutation executes without an owner Telegram button approval.
- Send and delete workflows are proven end-to-end.
- Existing Oisha production Telegram functionality and userbot session remain healthy.
- All relevant tests and security checks pass.
