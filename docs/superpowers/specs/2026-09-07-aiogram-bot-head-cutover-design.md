# Aiogram bot-head cutover — restore + finish migration

Date: 2026-09-07
Owner: Baxtiyorjon Gaziyev
Status: draft — awaiting owner review

## Problem

Oracle production runs `TELEGRAM_BOT_RUNTIME_BACKEND=aiogram` +
`TELEGRAM_ADMIN_AIOGRAM_DISPATCHER_ENABLED=true` (set in
`.github/workflows/oracle-deploy.yml:202,204` and `src/settings.py:69,73`).

But commit `5f682b41` (2026-09-06, "fix(proactive): fix Oracle VM projects topic
routing") split `src/bootstrap/runtime.py` into `src/bootstrap/orchestration/*`
and **silently dropped the entire Aiogram bot-head wiring**:

- `maybe_build_admin_aiogram_dispatcher(...)` — gone
- `AiogramTelethonCompatClient` bridge + `admin_bot.bot_client = legacy_bot_compat` — gone
- `AiogramBotHead(...).start()` polling lifecycle — gone
- `register_hisobchi_aiogram_callbacks` / `register_salescoach_aiogram_callbacks` — gone
- `events.py:148` `_hisobchi_callback_handler` now registers only `if backend == "telethon"`
- graceful `aiogram_bot_head.stop()` on drain — gone

**Live effect since 2026-09-06:** `@jonairobot` (bot-token head) has **no update
receiver** on the Oracle main process. Outbound `bot_runtime.send_message` still
works (send-only `AiogramBotRuntime`). Inbound is dead:

- no admin commands (`/start`, `/oisha_stats`, `/report`, …)
- no Hisobchi inline approval buttons (`happrove:` etc.)
- no Airtable transaction approval buttons (`at_app:` / `at_rej:`)
- no SalesCoach approval (`scapprove:` / `screject:`)

The brain note "Production cutover guard" (2026-07-27) is stale: the flip already
happened, and the pre-split `boot.py` (commit `914ec007`) already carried the
full wiring. This is a regression to recover, not a fresh cutover.

## Goal

1. Restore the Aiogram bot-head wiring in `src/bootstrap/orchestration/` so
   `@jonairobot` receives updates again on the Oracle main process.
2. Verify every AdminBot command + every approval callback works through the
   Aiogram path — migrate the few that the Telethon→Aiogram compat bridge cannot
   carry.
3. Tests (targeted Telegram suite + full pytest), Bandit.
4. Owner-approved Oracle VM deploy + live smoke (every admin command + Hisobchi
   approval callback).
5. `brain_log`.

Non-goal: the Telethon **userbot** stays exactly as is. Oracle session ownership
unchanged. Only the bot-token head moves.

## Key finding — migration is mostly a bridge, not a rewrite

`src/services/core/telegram/aiogram_telethon_compat.py` already contains
`AiogramTelethonCompatClient`. It captures Telethon-style
`@bot_client.on(events.NewMessage(pattern=r"..."))` and
`@bot_client.on(events.CallbackQuery())` decorators and re-dispatches them from
one Aiogram router via `_MessageRegistration(handler, matcher)` +
`AiogramLegacyMessageEvent` / `AiogramLegacyCallbackEvent` shims.

So when `admin_bot.bot_client = legacy_bot_compat` and `.attach()` is called,
**all ~20 unmigrated AdminBot command handlers run under Aiogram unchanged**:
`/start`, `/oisha_audit`, `/oisha_rivoj`, `/oisha_takliflar`, `/junk_audit`,
`/oisha_plan`, `/oisha_fact`, `/logs`, `/set_distribution`, `/add_manager`,
`/managers`, `/night_shift`, `/juma_send`, `/sync_stats`, `/sync_contacts_tg`,
`/set_position`, `/topic_info`, `/search`, `/client`, and the full inline-button
callback tree in `handlers_callbacks.py` (`dashboard`, `weekly_report`, `kpi`,
`deadlines`, `settings`, `vps_status`, `logs`, `social_spy:`, `set_dist_mode:`,
`get_id`, `send_draft:`, `reject_draft:`, `accept_lead:`, `claim_lead:`,
`improve:`, `mcp:approve:` / `mcp:cancel:`).

The native `dispatcher/builder.py` handlers (`/oisha_stats`, `/report`,
`/sales_today`, …, `/coach`, `/sparring`) also register on the same dispatcher.
Ordering: native dispatcher `@dp.message(F.text.regexp(...))` handlers are
registered before `legacy_bot_compat.attach()` installs its catch-all
`@dispatcher.message()`, so specific commands win; the compat catch-all only
handles what the native handlers did not.

### What the compat bridge cannot carry (needs native Aiogram)

| Telethon surface | Why it breaks | Plan |
|---|---|---|
| `handlers_search.py` `@bot_client.on(events.InlineQuery())` | compat `on()` logs "awaits native Aiogram migration" and drops it | native `@dp.inline_query()` handler calling the same `_perform_global_lookup` / `_handle_inline_db_query` logic |
| `handlers_search.py` `_handle_inline_db_query` uses `event.builder.article(...)` | Telethon-only builder API | rebuild results with `aiogram.types.InlineQueryResultArticle` |
| bare `@bot_client.on(events.NewMessage())` (no pattern) phone-search catch-all in `handlers_search.py:91` | compat matcher is `None` → fires on **every** message, competing with the native catch-all and AI ingress | gate it: register as native `@dp.message(F.text.regexp(<uz phone regex>))` so it only fires on phone-shaped text |

Everything else: bridge as-is.

## Design

### Module: `src/bootstrap/orchestration/bot_head.py` (new)

One function, `init_aiogram_bot_head(...)`, that reproduces the pre-split logic
from `runtime.py` (commit `914ec007` lines 289–358, 494–518, 725–752) in the
new package shape. Inputs: `bot_runtime`, `bot_ingress_mode`, `admin_bot`,
`access_manager`, `msg_controller`, `db`, `hisobchi_engine`, `api_module`,
`app_ctx`. Returns the `AiogramBotHead` instance (or `None`).

Responsibilities:
1. Build `admin_aiogram_dispatcher` via `maybe_build_admin_aiogram_dispatcher`
   with the five `_get_*` snapshot providers wired to `msg_controller.crm`.
2. If `backend == "aiogram"`:
   - construct `AiogramTelethonCompatClient(bot=bot_runtime.bot, dispatcher=...)`
   - set `admin_bot.bot_client = legacy_bot_compat`
   - register native inline-query + phone-search handlers on the dispatcher
     (the three rows above)
   - `register_hisobchi_aiogram_callbacks(dispatcher, engine=hisobchi_engine)`
   - `register_salescoach_aiogram_callbacks(dispatcher, context=app_ctx)`
   - `legacy_bot_compat.attach()`
   - build `AiogramBotHead(bot=..., dispatcher=..., allowed_updates=BOT_API_10_ALLOWED_UPDATES, raw_update_handler=api_module.process_telegram_ai_update)`
   - `.start()`, store on `app_ctx.aiogram_bot_head`,
     `api_module.set_telegram_ai_ingress_status(mode="aiogram", active=True)`
3. Call `admin_bot.start()` (registers the Telethon-decorated handlers onto the
   compat client, which the dispatcher now owns).

### `bootstrap/orchestration/boot.py` changes

- **Userbot-not-ready branch** (`boot.py:121-139`): after the telethon-only
  `bot_client.start()` path, add: if `backend == "aiogram"` and
  `bot_ingress_mode == "polling"`, call `init_aiogram_bot_head(...)` (without
  `hisobchi_engine` — that branch has none; pass `None`, and
  `register_hisobchi_aiogram_callbacks` is skipped when engine is `None`).
- **Happy path**: after `register_event_handlers(...)` at `boot.py:166` and after
  `hisobchi_engine` is built (`boot.py:145`), call `init_aiogram_bot_head(...)`
  with the real `hisobchi_engine`.
- **Guard against double-registration**: `admin_bot.start()` must be called
  exactly once. Today `boot.py` only calls it in the not-ready branch. The happy
  path never starts admin handlers at all (another regression). `init_aiogram_bot_head`
  owns the single `admin_bot.start()` call for the aiogram path; keep the
  existing not-ready telethon `admin_bot.start()` for `backend == "telethon"`.

### `bootstrap/orchestration/events.py` change

`_hisobchi_callback_handler` registration at `events.py:148`: the userbot
(`client`) side must stay for `backend == "telethon"`. For `backend == "aiogram"`
the userbot no longer needs the bot-head callbacks (those move to the
dispatcher), but the **userbot still needs its own** `scapprove:` / `happrove:`
handling for callbacks that arrive on the user account (finance group buttons
sent by the userbot). Keep `client.add_event_handler(_hisobchi_callback_handler,
events.CallbackQuery())` for **both** backends; only the `bot_client`
registration is telethon-only. Confirm against pre-split `runtime.py:881-891`
(there it was telethon-only for both — but pre-split, finance-group buttons were
sent through `bot_runtime` which is aiogram, so their callbacks land on the
dispatcher via `register_hisobchi_aiogram_callbacks`). Decision: match pre-split
exactly — both registrations telethon-only; aiogram path covered by
`register_hisobchi_aiogram_callbacks` + `register_salescoach_aiogram_callbacks`
in `bot_head.py`.

### `bootstrap/orchestration/drain.py` change

`graceful_drain` gets an `aiogram_bot_head` param; if not `None`,
`await aiogram_bot_head.stop()` before closing the bot client. `boot.py` passes
`app_ctx.aiogram_bot_head`.

## Files touched

| File | Change |
|---|---|
| `src/bootstrap/orchestration/bot_head.py` | new — `init_aiogram_bot_head` |
| `src/bootstrap/orchestration/boot.py` | call `init_aiogram_bot_head` in both branches; pass head to drain |
| `src/bootstrap/orchestration/drain.py` | accept + stop `aiogram_bot_head` |
| `src/bootstrap/orchestration/events.py` | (verify only — likely no change) |
| `src/services/core/dispatcher/inline_search.py` | new — native inline-query + phone-search handlers |
| `src/services/core/dispatcher/builder.py` | call `register_inline_search_handlers(dp, ...)` |
| `tests/test_bootstrap_aiogram_bot_head.py` | new |
| `tests/test_admin_aiogram_dispatcher.py` | extend: inline query, phone search, compat bridge covers unmigrated commands |

## Testing

- Targeted: `pytest tests/test_admin_aiogram_dispatcher.py tests/test_aiogram_head.py
  tests/test_aiogram_telethon_compat.py tests/test_bot_runtime.py
  tests/test_bootstrap_aiogram_bot_head.py tests/test_oracle_only_runtime.py -q`
- Full: `pytest -q`
- `bandit -r src/ -ll`

New tests assert:
- `init_aiogram_bot_head` with a fake `bot_runtime.backend == "aiogram"` builds a
  dispatcher, attaches the compat client, starts a head, registers hisobchi +
  salescoach callbacks, calls `admin_bot.start()` once.
- with `backend == "telethon"`: no head, no compat client, `admin_bot.start()`
  still called by the existing path (not by `bot_head.py`).
- inline-query handler returns `InlineQueryResultArticle` list for a name query
  and a contact result for a phone query.
- phone-search native handler only matches phone-shaped text.
- compat bridge: a `/junk_audit` style Telethon-decorated handler is reachable
  through `dispatcher.message` after `attach()`.

## Deploy + smoke (owner-gated, this session)

After code + tests green, ask owner once more, then:
1. Push branch, open PR, wait for CI green (CI, CodeQL, gitleaks, Oracle Deploy).
2. Merge → Oracle Production Deploy workflow redeploys VM.
3. Live smoke on `@jonairobot` (owner runs, or via telegram-mcp if authorized):
   `/start` (role buttons render), `/oisha_stats`, `/report`, `/sales_today`,
   `/command_center`, `/search +998…`, `/client <name>`, `/junk_audit`,
   `/set_mode shadow`, `/auto_status`.
4. Hisobchi approval: trigger a finance card entry, tap ✅ / ✏️ / ⏭ inline —
   confirm the card edits and the ledger writes.
5. Airtable approval: `at_app:` on a pending Tranzaksiya — confirm Airtable
   `Holat=Tasdiqlangan` + P&L sync.
6. `readyz` / `/api/system/health` 200; `set_telegram_ai_ingress_status` shows
   `mode="aiogram" active=True`.
7. `brain_log(action, detail)` — runtime truth from Oracle logs, per brain rule.

## Rollback

If live smoke fails: set Oracle `.env`
`TELEGRAM_BOT_RUNTIME_BACKEND=telethon` +
`TELEGRAM_ADMIN_AIOGRAM_DISPATCHER_ENABLED=false` and redeploy — the restored
`bot_head.py` no-ops on telethon and the existing telethon not-ready path starts
`admin_bot`. (Note: happy-path telethon bot head start is itself currently
missing — a follow-up, out of scope here unless smoke forces the rollback.)
