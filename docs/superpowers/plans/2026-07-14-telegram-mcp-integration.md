# Oisha Telegram MCP Approval Gateway Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose the forked Telegram MCP tool set through Oisha while allowing reads automatically and requiring owner Telegram-button approval for every mutation.

**Architecture:** A private upstream `telegram-mcp` process binds to `127.0.0.1:8765/mcp`. A separate Oisha gateway binds to `127.0.0.1:8766/mcp`, mirrors upstream tool schemas, proxies trusted read tools, and persists all other calls as pending approvals. Oisha's existing admin bot executes an immutable stored call only after the configured owner taps an inline approval button.

**Tech Stack:** Python 3.12, MCP Python SDK, Telethon, aiosqlite, systemd, pytest, Bandit.

## Global Constraints

- Read/search/list/inspect operations may execute without approval.
- Sending, editing, deleting, forwarding, reacting, pinning, scheduling, contact changes, profile changes, and group/channel administration require owner approval.
- Classification is deny-by-default and must use both trusted annotations and a local allowlist.
- Approval IDs are random, single-use, owner-only, immutable, and expire after 15 minutes.
- The upstream service listens only on `127.0.0.1:8765`; the gateway listens only on `127.0.0.1:8766`.
- Use a dedicated `TELEGRAM_MCP_SESSION_STRING`; never reuse `USERBOT_SESSION_STRING`.
- No public unauthenticated MCP endpoint is shipped. Initial ChatGPT access uses Secure MCP Tunnel.
- Secrets and full message bodies are not written to audit logs.
- Before PR: `SKIP_LIVE=1 python -m pytest -q --tb=short` and `bandit -r src/ -ll`.

---

## File map

- `src/services/core/telegram_mcp/policy.py`: deny-by-default tool classification and risk labels.
- `src/services/core/telegram_mcp/models.py`: immutable approval records and statuses.
- `src/services/core/telegram_mcp/store.py`: SQLite persistence, expiry, atomic claim, and audit events.
- `src/services/core/telegram_mcp/upstream.py`: Streamable HTTP MCP client adapter.
- `src/services/core/telegram_mcp/gateway.py`: low-level MCP list/call proxy and pending response.
- `src/services/core/telegram_mcp/approval_ui.py`: Telegram card formatting and safe previews.
- `src/services/core/telegram_mcp/executor.py`: revalidation and exactly-once upstream execution.
- `scripts/run_telegram_mcp_gateway.py`: gateway process entrypoint.
- `src/services/core/admin_bot.py`: owner callback routing for approve/cancel.
- `src/settings.py`: feature flags, URLs, expiry, and dedicated session setting.
- `requirements.txt`: pinned fork dependency.
- `deploy/systemd/telegram-mcp-upstream.service`: private upstream service.
- `deploy/systemd/oisha-telegram-mcp-gateway.service`: private gateway service.
- `deploy/install_telegram_mcp.sh`: idempotent service installation.
- `tests/telegram_mcp/*`: policy, store, gateway, callback, and security tests.

---

### Task 1: Configuration and pinned dependency

**Files:** Modify `src/settings.py`, `requirements.txt`; create `tests/telegram_mcp/test_settings.py`.

**Produces:** `TELEGRAM_MCP_ENABLED`, `TELEGRAM_MCP_UPSTREAM_URL`, `TELEGRAM_MCP_APPROVAL_TTL_SECONDS`, `TELEGRAM_MCP_SESSION_STRING`.

- [ ] Write a failing test asserting disabled-by-default, `http://127.0.0.1:8765/mcp`, 900-second TTL, and absent dedicated session.
- [ ] Run `SKIP_LIVE=1 python -m pytest tests/telegram_mcp/test_settings.py -q`; expect missing settings failure.
- [ ] Add:
```python
TELEGRAM_MCP_ENABLED: bool = False
TELEGRAM_MCP_UPSTREAM_URL: str = "http://127.0.0.1:8765/mcp"
TELEGRAM_MCP_APPROVAL_TTL_SECONDS: int = 900
TELEGRAM_MCP_SESSION_STRING: Optional[SecretStr] = None
```
- [ ] Add `TELEGRAM_MCP_SESSION_STRING` to `optional_keys`.
- [ ] Add pinned dependency:
```text
telegram-mcp @ git+https://github.com/baxtiyorjongaziyev/telegram-mcp.git@3a258e22a3ac547b4c3e7a3b8f121bfc17f7f65a
```
- [ ] Run the focused test; expect PASS.
- [ ] Commit: `feat(telegram): add MCP gateway configuration`.

### Task 2: Deny-by-default mutation policy

**Files:** Create `src/services/core/telegram_mcp/__init__.py`, `policy.py`, and `tests/telegram_mcp/test_policy.py`.

**Produces:** `classify_tool(name: str, annotations: dict | None) -> ToolDecision`.

- [ ] Test that allowlisted tools with `readOnlyHint=True` run automatically, unknown/missing annotations require approval, and send/edit/delete/ban always require approval.
- [ ] Run focused test; expect missing module failure.
- [ ] Implement immutable `ToolDecision`, a reviewed read allowlist, destructive prefixes, and deny-by-default fallback:
```python
def classify_tool(name, annotations):
    annotated_read = bool((annotations or {}).get("readOnlyHint"))
    if annotated_read and name in READ_ALLOWLIST:
        return ToolDecision(True, "read", "trusted annotation and allowlist")
    risk = "destructive" if name.startswith(DESTRUCTIVE_PREFIXES) else "mutation"
    return ToolDecision(False, risk, "owner approval required")
```
- [ ] Run tests; expect PASS.
- [ ] Commit: `feat(telegram): add deny-by-default MCP policy`.

### Task 3: Persistent approval and audit store

**Files:** Create `models.py`, `store.py`, and `tests/telegram_mcp/test_store.py`.

**Produces:** `ApprovalStore.initialize/create/claim/cancel/finish`.

- [ ] Test owner-only, single-use atomic claims with two concurrent claim calls.
- [ ] Run focused test; expect missing store failure.
- [ ] Store canonical JSON with sorted keys and SHA-256 payload hash in `mcp_pending_operations`; store redacted state changes in `mcp_audit_events`.
- [ ] Claim using `BEGIN IMMEDIATE` and:
```sql
UPDATE mcp_pending_operations
SET status='executing', approved_by=?, approved_at=CURRENT_TIMESTAMP
WHERE id=? AND status='pending' AND expires_at>CURRENT_TIMESTAMP
```
- [ ] Add cancellation, expiry, tamper, and audit-redaction tests.
- [ ] Run focused tests; expect PASS.
- [ ] Commit: `feat(telegram): persist MCP approvals and audit events`.

### Task 4: Upstream adapter and gateway

**Files:** Create `upstream.py`, `gateway.py`, `scripts/run_telegram_mcp_gateway.py`, and `tests/telegram_mcp/test_gateway.py`.

**Produces:** `UpstreamClient.list_tools/call_tool` and `build_gateway(...)`.

- [ ] Test that `list_chats` proxies but `send_message` returns `pending_approval` without touching upstream.
- [ ] Run focused test; expect missing gateway failure.
- [ ] Implement one lifespan-owned `mcp.ClientSession` over Streamable HTTP; cache tool discovery and reconnect with capped backoff.
- [ ] Mirror upstream schemas in `list_tools`; classify every `call_tool`.
- [ ] For mutation, persist and notify, then return:
```python
{"status": "pending_approval", "operation_id": operation.id,
 "expires_at": operation.expires_at.isoformat(),
 "message": "Owner approval requested in Telegram."}
```
- [ ] Refuse non-loopback bind; serve only `127.0.0.1:8766/mcp`.
- [ ] Run focused tests; expect PASS.
- [ ] Commit: `feat(telegram): add approval-gated MCP gateway`.

### Task 5: Owner approval UI and execution

**Files:** Create `approval_ui.py`, `executor.py`; modify `src/services/core/admin_bot.py`; create `test_approval_flow.py`.

**Produces:** callback data `mcp:approve:<id>`, `mcp:cancel:<id>`; exactly-once executor.

- [ ] Test non-owner denial, owner success, duplicate refusal, expiry, cancellation, and upstream failure.
- [ ] Run focused test; expect missing executor failure.
- [ ] Cards show tool, risk, target, count, and at most 200 characters of safe preview. Destructive cards start with `⚠️ O‘CHIRISH/BLOKLASH AMALI`.
- [ ] Executor verifies `OWNER_ID`, atomically claims, recomputes hash, reclassifies, executes once, and never auto-retries mutation.
- [ ] Add callback branches near the start of AdminBot's existing `events.CallbackQuery()` handler:
```python
if data.startswith("mcp:approve:"):
    outcome = await self.telegram_mcp_executor.approve(
        data.removeprefix("mcp:approve:"), event.sender_id)
    await event.answer(outcome.user_message, alert=outcome.status in {"denied", "failed"})
    return
if data.startswith("mcp:cancel:"):
    outcome = await self.telegram_mcp_executor.cancel(
        data.removeprefix("mcp:cancel:"), event.sender_id)
    await event.answer(outcome.user_message, alert=False)
    return
```
- [ ] Make executor injection optional but fail closed.
- [ ] Run focused tests; expect PASS.
- [ ] Commit: `feat(telegram): require owner approval for MCP mutations`.

### Task 6: Private systemd services

**Files:** Create both units, installer, and `test_deploy_security.py`.

- [ ] Test loopback-only binds, dedicated session, no `0.0.0.0`, and gateway dependency on upstream.
- [ ] Run test; expect missing files failure.
- [ ] Upstream sets `MCP_TRANSPORT=http`, `MCP_HOST=127.0.0.1`, `MCP_PORT=8765`; gateway uses 8766 and hardened systemd settings.
- [ ] Installer refuses missing session or equality with `USERBOT_SESSION_STRING`, never prints secrets, then installs/enables units idempotently.
- [ ] Run test; expect PASS.
- [ ] Commit: `feat(deploy): add private Telegram MCP services`.

### Task 7: End-to-end verification and guide

**Files:** Create `test_integration.py`, `docs/telegram-mcp-chatgpt.md`; modify `AGENTS.md`.

- [ ] Cover automatic read, pending send, approved send, approved delete, cancel, expiry, duplicate/non-owner approval, unknown tool, timeout, and audit failure.
- [ ] Run `SKIP_LIVE=1 python -m pytest tests/telegram_mcp -q`; expect all PASS.
- [ ] Document secret names, separate-session generation, service checks, Secure MCP Tunnel to `http://127.0.0.1:8766/mcp`, rollback, and no Nginx exposure.
- [ ] Update AGENTS operational notes and remove temporary lock.
- [ ] Run:
```bash
SKIP_LIVE=1 python -m pytest -q --tb=short
bandit -r src/ -ll
```
- [ ] Commit: `test(telegram): verify MCP approval gateway end to end`.

### Task 8: PR and staged deploy

- [ ] Run `git diff main...HEAD --check`; expect clean.
- [ ] Open draft PR `feat(telegram): add approval-gated MCP gateway` with tests, risks, dedicated-session rule, and rollback.
- [ ] Configure `TELEGRAM_MCP_SESSION_STRING` and verify it differs from `USERBOT_SESSION_STRING` without printing values.
- [ ] Install services and verify ports 8765/8766 listen only on loopback.
- [ ] Smoke-test `list_chats` without approval.
- [ ] Smoke-test approved send to Saved Messages and deletion of only that test message.
- [ ] Verify Oisha readiness and absence of `AuthKeyDuplicatedError`; on error stop only the MCP upstream and revoke only its new Telegram device session.
- [ ] Attach redacted evidence and mark PR ready.
