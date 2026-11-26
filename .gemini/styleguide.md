# Oisha-OS review guide

Focus on real bugs, security issues and data loss. Skip pure style nits.

Project rules to enforce:
- Python 3.12 asyncio. No blocking calls (requests, time.sleep) inside async code without `asyncio.to_thread`.
- DB writes to the main Turso/SQLite DB go through `database_pool.py`; never open raw connections. Dedicated isolated local SQLite stores may write directly when that isolation is intended.
- Never bypass quiet hours (23:00-07:00 Tashkent) or owner-approval gates in `agent_policy.py` / `auto_reply_gate.py` for CRM or Telegram actions.
- Never log or persist secrets, tokens, session strings or API keys.
- AmoCRM mutations must be fail-safe: do not close or delete a lead unless every prior transfer step succeeded.
- `src/services/debug/` must never be imported by production code.
- Uzbek text: only inside double quotes; ASCII apostrophe inside a word is forbidden (use U+02BB / U+02BC).
- LLM calls go through `free_ai_router`.
- TypeScript workspaces: pnpm only; root `apps/` and `salescoach-ai/` stay separate.
