# Oisha multi-agent Telegram gateway

Oisha is the only Telegram boundary for AI agents. Agents must never receive,
copy, or start either Telegram session.

## Two Telegram heads

- Telethon userbot: reads Telegram history and performs owner-approved
  user-account actions.
- Aiogram `@jonairobot`: commands, callbacks, approval prompts, notifications,
  and operational alerts.

The MCP upstream remains a single Oracle-owned process on `127.0.0.1:8765`.
Every AI client connects through the approval-gated bridge. Starting another
Telethon process with `USERBOT_SESSION_STRING` is forbidden.

## Agent bridge

```text
python scripts/run_telegram_mcp_agent.py --agent codex
python scripts/run_telegram_mcp_agent.py --agent claude
python scripts/run_telegram_mcp_agent.py --agent antigravity
```

Default allowed IDs are `codex`, `claude`, and `antigravity`. A future agent
must first be added explicitly:

```env
TELEGRAM_MCP_AGENT_IDS=codex,claude,antigravity,gemini
```

The ID is fixed when the bridge starts and is written to the durable approval
audit as `requester`. Agents cannot select another identity per tool call.

## Safety contract

- Reviewed read-only tools execute automatically.
- Every mutation is deny-by-default and requires owner approval.
- The upstream URL must resolve to loopback.
- Ports `8765` and `8766` must never be exposed through Nginx.
- The production userbot session remains Oracle-owned.
- Aiogram remains independent, so it can alert the owner if the userbot is
  unavailable.

## Adding another AI client

Give the client an SSH stdio command that runs the agent bridge on Oracle with
its allowlisted ID. Do not provide Telegram secrets to the client. Validate:

1. `list_chats` succeeds without approval.
2. A send request returns `pending_approval`.
3. `@jonairobot` displays the correct requester.
4. Approval executes exactly once.
5. Audit storage records the same requester.
