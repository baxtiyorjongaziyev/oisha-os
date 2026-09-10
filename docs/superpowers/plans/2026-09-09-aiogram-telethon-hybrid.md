# Aiogram / Telethon Hybrid Runtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move every bot-account (@jonairobot) Telegram flow to Aiogram 3.x while the userbot (personal account) stays 100% on Telethon, so each library is used for what it does best.

**Architecture:** `bot_runtime` already abstracts outbound sends (`TelethonBotRuntime` / `AiogramBotRuntime`). Ingress is still Telethon-only. This plan (a) makes outbound default to Aiogram behind `TELEGRAM_BOT_RUNTIME_BACKEND=aiogram`, then (b) wires the already-built `AiogramBotHead` + `AiogramTelethonCompatClient` so bot updates (commands, callbacks, guest queries) arrive through Aiogram polling/webhook. The Telethon userbot client (`client`) and all `client.add_event_handler(...)` registrations in `events.py` are untouched. A single feature flag (`TELEGRAM_BOT_INGRESS_MODE` already exists; add `aiogram` handling) flips ingress; rollback is one env var.

**Tech Stack:** Python 3.11, asyncio, aiogram 3.31, Telethon 1.x, FastAPI (webhook route), pytest + pytest-asyncio.

## Global Constraints

- Python 3.11 (Docker `python:3.11-slim-bookworm`). No 3.12+ syntax.
- `aiogram>=3.29.1` (installed 3.31.0). Do not bump.
- Userbot session (`USERBOT_SESSION_STRING`) and `TELEGRAM_MCP_SESSION_STRING` are NEVER passed to any Aiogram object. Aiogram only ever gets `BOT_TOKEN`.
- Never run a second Telethon userbot — `ALLOW_LOCAL_RUN=1` + a DEDICATED throwaway session for any local test.
- Tests must pass with `SKIP_LIVE=1 python -m pytest -q`.
- `bandit -r src/ -ll` must stay clean.
- Commit style: `feat(scope): …` / `fix(scope): …` / `refactor(scope): …`. End commit messages with `Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>`.
- Branch: current `claude/gemini-transcription-ai-analysis-738d3b` (or a fresh `feat/aiogram-hybrid`).
- Uzbek+English mixed comments are expected, keep the style.
- Coordinator-owned shared files (`settings.py`, `context.py`, `boot.py`) — edits here are intentional and scoped; keep diffs minimal.

## Domain / Vocabulary

- **bot head / bot-account** = `@jonairobot`, authenticated by `BOT_TOKEN`. Sends alerts, runs `/oisha_*` admin commands, handles inline callbacks, answers guest queries.
- **userbot** = personal Telegram account, `USERBOT_SESSION_STRING`, Telethon only. Listens to DMs/groups, auto-replies, scrapes members, MCP gateway.
- **ingress** = how bot updates are received: Telethon polling (`bot_client.start(bot_token=...)`), Aiogram polling (`AiogramBotHead._run_polling`), or Aiogram webhook (`aiogram_webhook_head`).
- **`bot_runtime`** = outbound send port. `app_ctx.bot_runtime`. Every alert path calls `bot_runtime.send_message(...)`.
- **compat client** = `AiogramTelethonCompatClient` — captures Telethon-style `@x.on(events.NewMessage(pattern=...))` decorators and dispatches them from one Aiogram router, so `AdminBot` handler code is reused unchanged.

## File Structure

| File | Responsibility | Action |
|---|---|---|
| `src/settings.py` | add `TELEGRAM_BOT_INGRESS_MODE` value `aiogram`; document | Modify |
| `src/services/core/telegram/bot_runtime.py` | outbound port; already fixed for topics+buttons | (done in prior commit — no change) |
| `src/services/core/telegram/aiogram_head.py` | Aiogram polling lifecycle for bot head | Modify (fill stubbed methods if incomplete) |
| `src/services/core/telegram/aiogram_telethon_compat.py` | Telethon-decorator → Aiogram-router bridge | Modify (pattern-match parity, StopPropagation) |
| `src/bootstrap/orchestration/telegram_session.py` | `init_bot_client_runtime()` — chooses backend + ingress | Modify |
| `src/bootstrap/orchestration/events.py` | register bot callbacks; branch telethon vs aiogram | Modify |
| `src/bootstrap/orchestration/boot.py` | start the right ingress head | Modify |
| `src/services/core/admin_bot/bot.py` | `AdminBot.start()` — accept compat client | Modify |
| `src/api/routes/telegram_webhook.py` | FastAPI POST route for Aiogram webhook updates | Create |
| `src/api_server.py` | mount the webhook router | Modify |
| `tests/test_bot_runtime.py` | outbound (already updated) | (no change) |
| `tests/test_aiogram_compat_client.py` | decorator capture + dispatch + pattern match + StopPropagation | Create |
| `tests/test_aiogram_head_lifecycle.py` | start/stop idempotency, allowed_updates, userbot-session guard | Create |
| `tests/test_bot_ingress_selection.py` | `init_bot_client_runtime()` returns correct head per env | Create |
| `tests/test_telegram_webhook_route.py` | webhook route feeds dispatcher, rejects bad secret | Create |
| `.env.example` | document `TELEGRAM_BOT_RUNTIME_BACKEND` + ingress `aiogram` + webhook secret | Modify |
| `docs/DEV_LOG.md` | note the migration + rollback switch | Modify |

---

## Task 1: Outbound backend switch — make Aiogram the send path

**Files:**
- Modify: `src/bootstrap/orchestration/telegram_session.py:136-154`
- Modify: `.env.example` (after line ~95, near `AMOCRM_CALL_*`)
- Test: `tests/test_bot_ingress_selection.py` (Create)

**Interfaces:**
- Consumes: `settings.TELEGRAM_BOT_RUNTIME_BACKEND` (str, default `"telethon"`), `settings.BOT_TOKEN` (SecretStr), `settings.API_ID` (int), `settings.API_HASH` (str), `build_outbound_bot_runtime(*, backend: str, bot_token: str, telethon_client) -> BotRuntimePort`.
- Produces: `init_bot_client_runtime() -> Tuple[bot_client, bot_token_str, bot_runtime, bot_ingress_mode]` unchanged signature. When `TELEGRAM_BOT_RUNTIME_BACKEND == "aiogram"`, `app_ctx.bot_runtime` is an `AiogramBotRuntime` wrapping `aiogram.Bot(token=...)`; `app_ctx.aiogram_bot` holds that `Bot`. `bot_ingress_mode` is one of `"polling" | "webhook" | "disabled" | "aiogram"`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_bot_ingress_selection.py
from types import SimpleNamespace
import pytest


@pytest.fixture
def _ctx(monkeypatch):
    from src.context import app_ctx
    monkeypatch.setattr(app_ctx, "bot_client", None, raising=False)
    monkeypatch.setattr(app_ctx, "bot_runtime", None, raising=False)
    monkeypatch.setattr(app_ctx, "aiogram_bot", None, raising=False)
    return app_ctx


def test_default_backend_is_telethon_runtime(monkeypatch, _ctx):
    from src.settings import settings
    monkeypatch.setattr(settings, "TELEGRAM_BOT_RUNTIME_BACKEND", "telethon", raising=False)
    monkeypatch.setattr(settings, "TELEGRAM_BOT_INGRESS_MODE", "polling", raising=False)
    from src.bootstrap.orchestration.telegram_session import init_bot_client_runtime
    from src.services.core.telegram.bot_runtime import TelethonBotRuntime
    _client, _token, runtime, ingress = init_bot_client_runtime()
    assert isinstance(runtime, TelethonBotRuntime)
    assert ingress == "polling"


def test_aiogram_backend_yields_aiogram_runtime(monkeypatch, _ctx):
    from src.settings import settings
    monkeypatch.setattr(settings, "TELEGRAM_BOT_RUNTIME_BACKEND", "aiogram", raising=False)
    monkeypatch.setattr(settings, "TELEGRAM_BOT_INGRESS_MODE", "aiogram", raising=False)
    from src.bootstrap.orchestration.telegram_session import init_bot_client_runtime
    from src.services.core.telegram.bot_runtime import AiogramBotRuntime
    _client, _token, runtime, ingress = init_bot_client_runtime()
    assert isinstance(runtime, AiogramBotRuntime)
    assert ingress == "aiogram"
    assert _ctx.aiogram_bot is not None


def test_aiogram_bot_never_receives_user_session(monkeypatch, _ctx):
    from src.settings import settings
    monkeypatch.setattr(settings, "TELEGRAM_BOT_RUNTIME_BACKEND", "aiogram", raising=False)
    monkeypatch.setattr(settings, "TELEGRAM_BOT_INGRESS_MODE", "aiogram", raising=False)
    from src.bootstrap.orchestration.telegram_session import init_bot_client_runtime
    init_bot_client_runtime()
    # aiogram.Bot exposes .token; assert it equals the bot token, not a session string
    assert _ctx.aiogram_bot.token == settings.BOT_TOKEN.get_secret_value()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `SKIP_LIVE=1 python -m pytest tests/test_bot_ingress_selection.py -v`
Expected: FAIL — `test_aiogram_backend_yields_aiogram_runtime` fails (`init_bot_client_runtime` currently only builds via `build_outbound_bot_runtime` which returns `AiogramBotRuntime(Bot(...))` but never sets `app_ctx.aiogram_bot`, and `bot_ingress_mode` never becomes `"aiogram"`).

- [ ] **Step 3: Implement the ingress selection**

Edit `src/bootstrap/orchestration/telegram_session.py`, replace the body of `init_bot_client_runtime()` (lines 136-154) with:

```python
def init_bot_client_runtime() -> Tuple[Any, str, Any, str]:
    BOT_TOKEN = settings.BOT_TOKEN.get_secret_value()
    _bot_session_string = os.environ.get("BOT_SESSION_STRING", "").strip()
    _bot_session = StringSession(_bot_session_string) if _bot_session_string else StringSession()
    # Telethon bot-token client stays available as an outbound fallback and for
    # any flow not yet migrated. It is a BOT token client, never a user session.
    app_ctx.bot_client = TelegramClient(_bot_session, settings.API_ID, settings.API_HASH)
    app_ctx.bot_token_str = BOT_TOKEN

    backend = str(getattr(settings, "TELEGRAM_BOT_RUNTIME_BACKEND", "telethon") or "telethon").strip().lower()
    ingress = str(getattr(settings, "TELEGRAM_BOT_INGRESS_MODE", "polling") or "polling").strip().lower()
    if ingress not in {"polling", "webhook", "disabled", "aiogram"}:
        raise RuntimeError("TELEGRAM_BOT_INGRESS_MODE must be polling, webhook, disabled, or aiogram")

    from src.services.core.telegram.bot_runtime import build_outbound_bot_runtime

    app_ctx.aiogram_bot = None
    app_ctx.aiogram_bot_head = None
    if backend == "aiogram":
        from aiogram import Bot
        from aiogram.client.default import DefaultBotProperties

        aiogram_bot = Bot(
            token=BOT_TOKEN,
            default=DefaultBotProperties(parse_mode="HTML"),
        )
        app_ctx.aiogram_bot = aiogram_bot
        from src.services.core.telegram.bot_runtime import AiogramBotRuntime

        app_ctx.bot_runtime = AiogramBotRuntime(aiogram_bot)
        # Aiogram owns ingress too, unless explicitly disabled.
        if ingress in {"polling", "aiogram"}:
            ingress = "aiogram"
    else:
        app_ctx.bot_runtime = build_outbound_bot_runtime(
            backend=backend or "telethon",
            bot_token=app_ctx.bot_token_str,
            telethon_client=app_ctx.bot_client,
        )

    return app_ctx.bot_client, app_ctx.bot_token_str, app_ctx.bot_runtime, ingress
```

- [ ] **Step 4: Run test to verify it passes**

Run: `SKIP_LIVE=1 python -m pytest tests/test_bot_ingress_selection.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Document env vars**

Edit `.env.example`, add near the other Telegram bot settings (search `TELEGRAM_BOT_INGRESS_MODE` — if absent add both):

```
# --- TELEGRAM BOT HEAD RUNTIME ---
# telethon (default, legacy) | aiogram (recommended target). Userbot always stays telethon.
TELEGRAM_BOT_RUNTIME_BACKEND=telethon
# polling | webhook | disabled | aiogram. With backend=aiogram this is forced to aiogram.
TELEGRAM_BOT_INGRESS_MODE=polling
# Shared secret path segment for the Aiogram webhook route (webhook/aiogram-webhook only).
TELEGRAM_WEBHOOK_SECRET=change-me-long-random
```

- [ ] **Step 6: Commit**

```bash
git add src/bootstrap/orchestration/telegram_session.py .env.example tests/test_bot_ingress_selection.py
git commit -m "feat(bot): select aiogram outbound+ingress via TELEGRAM_BOT_RUNTIME_BACKEND

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 2: Compat client parity — pattern match, groups, StopPropagation

**Files:**
- Modify: `src/services/core/telegram/aiogram_telethon_compat.py:188-236`
- Test: `tests/test_aiogram_compat_client.py` (Create)

**Interfaces:**
- Consumes: `AiogramTelethonCompatClient(*, bot, dispatcher)`; Telethon `events.NewMessage(pattern=...)`, `events.CallbackQuery()`.
- Produces:
  - `client.on(events.NewMessage(pattern=r"..."))(handler)` registers a message handler; on dispatch, `handler(event)` is called with `event.pattern_match` = the `re.Match` (so `event.pattern_match.group(1)` works exactly like Telethon).
  - Raising `telethon.events.StopPropagation` inside a handler stops later handlers for that update.
  - `client.on(events.CallbackQuery())(handler)` registers a callback handler; dispatch builds `AiogramLegacyCallbackEvent` with `.data` as `bytes`.
  - Regex matching uses `re.match` semantics (anchored at start), case-insensitive when the Telethon builder's pattern had `(?i)`, matching Telethon's `NewMessage(pattern=...)` behavior.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_aiogram_compat_client.py
import re
from types import SimpleNamespace

import pytest
from telethon import events

from src.services.core.telegram.aiogram_telethon_compat import (
    AiogramTelethonCompatClient,
)


class _FakeMessage:
    def __init__(self, text, chat_id=-100, user_id=5):
        self.text = text
        self.entities = []
        self.chat = SimpleNamespace(id=chat_id, type="supergroup")
        self.from_user = SimpleNamespace(id=user_id)
        self.reply_to_message = None
        self.answers = []

    async def answer(self, text, **kwargs):
        self.answers.append((text, kwargs))
        return _FakeMessage(text)


class _FakeDispatcher:
    def __init__(self):
        self._msg = None
        self._cb = None

    def message(self):
        def deco(fn):
            self._msg = fn
            return fn
        return deco

    def callback_query(self):
        def deco(fn):
            self._cb = fn
            return fn
        return deco


@pytest.mark.asyncio
async def test_pattern_match_passes_regex_groups():
    dp = _FakeDispatcher()
    client = AiogramTelethonCompatClient(bot=object(), dispatcher=dp)
    seen = {}

    @client.on(events.NewMessage(pattern=r"(?i)^/search(?:\s+(.+))?"))
    async def _h(event):
        seen["group1"] = event.pattern_match.group(1)

    client.attach()
    await dp._msg(_FakeMessage("/search laptop stand"))
    assert seen["group1"] == "laptop stand"


@pytest.mark.asyncio
async def test_non_matching_pattern_is_skipped():
    dp = _FakeDispatcher()
    client = AiogramTelethonCompatClient(bot=object(), dispatcher=dp)
    called = []

    @client.on(events.NewMessage(pattern=r"(?i)^/oisha_audit"))
    async def _h(event):
        called.append(True)

    client.attach()
    await dp._msg(_FakeMessage("just chatting"))
    assert called == []


@pytest.mark.asyncio
async def test_stop_propagation_halts_later_handlers():
    dp = _FakeDispatcher()
    client = AiogramTelethonCompatClient(bot=object(), dispatcher=dp)
    order = []

    @client.on(events.NewMessage(pattern=r"(?i)^/x"))
    async def _first(event):
        order.append("first")
        raise events.StopPropagation

    @client.on(events.NewMessage(pattern=r"(?i)^/x"))
    async def _second(event):
        order.append("second")

    client.attach()
    await dp._msg(_FakeMessage("/x"))
    assert order == ["first"]


@pytest.mark.asyncio
async def test_callback_event_data_is_bytes():
    dp = _FakeDispatcher()
    client = AiogramTelethonCompatClient(bot=object(), dispatcher=dp)
    got = {}

    @client.on(events.CallbackQuery())
    async def _cb(event):
        got["data"] = event.data

    client.attach()
    cb = SimpleNamespace(
        data="happrove:12",
        from_user=SimpleNamespace(id=7),
        message=_FakeMessage("card"),
        answer=lambda *a, **k: None,
    )

    async def _answer(*a, **k):
        return None
    cb.answer = _answer
    await dp._cb(cb)
    assert got["data"] == b"happrove:12"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `SKIP_LIVE=1 python -m pytest tests/test_aiogram_compat_client.py -v`
Expected: FAIL — `test_stop_propagation_halts_later_handlers` (current `_dispatch_message` does not catch `StopPropagation`) and possibly `test_pattern_match_passes_regex_groups` (matcher extraction is fragile: it does `getattr(pattern, "__self__", None)` then `.match`, which only works if Telethon compiled the pattern to a bound method — verify).

- [ ] **Step 3: Implement matcher + StopPropagation**

In `src/services/core/telegram/aiogram_telethon_compat.py`, replace the `decorator` inner function inside `on()` and the `attach()` dispatch functions:

```python
    def on(self, builder: Any) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        kind = getattr(builder, "__module__", "") + "." + getattr(
            type(builder), "__name__", ""
        )

        def decorator(handler: Callable[..., Any]) -> Callable[..., Any]:
            if "newmessage" in kind.lower():
                raw_pattern = getattr(builder, "pattern", None)
                matcher = _compile_matcher(raw_pattern)
                self._messages.append(_MessageRegistration(handler, matcher))
            elif "callbackquery" in kind.lower():
                self._callbacks.append(handler)
            elif "inlinequery" in kind.lower():
                logger.info(
                    "[BOT] Legacy inline-query handler awaits native Aiogram migration."
                )
            elif inspect.isclass(builder) and builder.__name__ == "Raw":
                logger.info("[BOT] Legacy raw guest handler replaced by Bot API ingress.")
            return handler

        return decorator

    def attach(self) -> None:
        if self._attached:
            return
        self._attached = True

        @self.dispatcher.message()
        async def _dispatch_message(message: Any) -> None:
            from telethon import events as _tl_events

            text = str(getattr(message, "text", "") or "")
            for registration in self._messages:
                match = registration.matcher(text) if registration.matcher else None
                if registration.matcher is not None and match is None:
                    continue
                event = AiogramLegacyMessageEvent(message, pattern_match=match)
                try:
                    await registration.handler(event)
                except _tl_events.StopPropagation:
                    break

        @self.dispatcher.callback_query()
        async def _dispatch_callback(callback: Any) -> None:
            from telethon import events as _tl_events

            event = AiogramLegacyCallbackEvent(callback)
            for handler in self._callbacks:
                try:
                    await handler(event)
                except _tl_events.StopPropagation:
                    break
```

Add this helper near the top of the module (after `_parse_mode`):

```python
def _compile_matcher(raw_pattern: Any) -> Optional[Callable[[str], Any]]:
    """Turn a Telethon NewMessage(pattern=...) value into a str -> re.Match|None fn."""
    import re

    if raw_pattern is None:
        return None
    # Telethon stores either a compiled pattern, a bound .match method, or a str.
    if hasattr(raw_pattern, "match") and callable(raw_pattern.match):
        return raw_pattern.match
    self_obj = getattr(raw_pattern, "__self__", None)
    if self_obj is not None and hasattr(self_obj, "match"):
        return self_obj.match
    if isinstance(raw_pattern, (str, bytes)):
        compiled = re.compile(raw_pattern if isinstance(raw_pattern, str) else raw_pattern.decode())
        return compiled.match
    if callable(raw_pattern):
        return raw_pattern
    return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `SKIP_LIVE=1 python -m pytest tests/test_aiogram_compat_client.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add src/services/core/telegram/aiogram_telethon_compat.py tests/test_aiogram_compat_client.py
git commit -m "feat(bot): compat client pattern-match + StopPropagation parity

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 3: Aiogram head lifecycle — start/stop, allowed_updates, session guard

**Files:**
- Modify: `src/services/core/telegram/aiogram_head.py` (fill any stubbed method bodies visible in the file — `_register_raw_update_middleware`, `running`, `start`, `_run_polling`, `stop`)
- Test: `tests/test_aiogram_head_lifecycle.py` (Create)

**Interfaces:**
- Consumes: `AiogramBotHead(*, bot, dispatcher, allowed_updates=None, raw_update_handler=None)`.
- Produces:
  - `.start() -> asyncio.Task` — idempotent: calling twice returns the same running task, does not start a second poller.
  - `.running() -> bool`.
  - `.stop()` — cancels the poll task, calls `bot.session.close()` if present, sets running False; safe to call when not started.
  - `_run_polling()` calls `dispatcher.start_polling(bot, allowed_updates=<list>, handle_signals=False)`.
  - Constructor raises `ValueError` if `bot` has a `.session` that looks like a Telethon `StringSession` (defensive: reject a user client).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_aiogram_head_lifecycle.py
import asyncio
from types import SimpleNamespace

import pytest

from src.services.core.telegram.aiogram_head import AiogramBotHead


class _FakeDispatcher:
    def __init__(self):
        self.calls = []
        self._stop = asyncio.Event()

    async def start_polling(self, bot, **kwargs):
        self.calls.append(kwargs)
        await self._stop.wait()

    def stop(self):
        self._stop.set()


class _FakeSession:
    def __init__(self):
        self.closed = False

    async def close(self):
        self.closed = True


def _fake_bot():
    return SimpleNamespace(token="123:abc", session=_FakeSession())


@pytest.mark.asyncio
async def test_start_is_idempotent():
    dp = _FakeDispatcher()
    head = AiogramBotHead(bot=_fake_bot(), dispatcher=dp, allowed_updates=["message"])
    t1 = head.start()
    t2 = head.start()
    assert t1 is t2
    assert head.running() is True
    await head.stop()
    assert head.running() is False


@pytest.mark.asyncio
async def test_polling_passes_allowed_updates_and_no_signal_handling():
    dp = _FakeDispatcher()
    head = AiogramBotHead(bot=_fake_bot(), dispatcher=dp, allowed_updates=["message", "callback_query"])
    head.start()
    await asyncio.sleep(0)  # let the task enter start_polling
    assert dp.calls and dp.calls[0].get("allowed_updates") == ["message", "callback_query"]
    assert dp.calls[0].get("handle_signals") is False
    await head.stop()


@pytest.mark.asyncio
async def test_stop_closes_bot_session():
    bot = _fake_bot()
    dp = _FakeDispatcher()
    head = AiogramBotHead(bot=bot, dispatcher=dp)
    head.start()
    await asyncio.sleep(0)
    await head.stop()
    assert bot.session.closed is True


def test_stop_before_start_is_noop():
    head = AiogramBotHead(bot=_fake_bot(), dispatcher=_FakeDispatcher())
    asyncio.run(head.stop())  # must not raise
    assert head.running() is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `SKIP_LIVE=1 python -m pytest tests/test_aiogram_head_lifecycle.py -v`
Expected: FAIL — methods are stubs (`pass` bodies from the file listing), so `start()` returns `None`, `running()` errors or returns wrong value.

- [ ] **Step 3: Implement the lifecycle**

Replace the method bodies in `src/services/core/telegram/aiogram_head.py`:

```python
    def _register_raw_update_middleware(self) -> None:
        if not self.raw_update_handler:
            return

        @self.dispatcher.update.outer_middleware()
        async def _raw_update_middleware(handler, event, data):
            try:
                await self.raw_update_handler(
                    event.model_dump(exclude_none=True)
                    if hasattr(event, "model_dump")
                    else dict(event)
                )
            except Exception:  # pragma: no cover - observability only
                logger.exception("[BOT] raw_update_handler failed")
            return await handler(event, data)

    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    def start(self) -> "asyncio.Task":
        if self.running():
            return self._task
        self._register_raw_update_middleware()
        self._task = asyncio.create_task(self._run_polling(), name="aiogram_bot_head")
        return self._task

    async def _run_polling(self) -> None:
        allowed = self.allowed_updates or ["message", "callback_query", "inline_query"]
        try:
            await self.dispatcher.start_polling(
                self.bot,
                allowed_updates=allowed,
                handle_signals=False,
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("[BOT] Aiogram polling crashed")

    async def stop(self) -> None:
        task, self._task = self._task, None
        if task is not None and not task.done():
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass
        session = getattr(self.bot, "session", None)
        close = getattr(session, "close", None)
        if callable(close):
            try:
                await close()
            except Exception:  # pragma: no cover
                logger.debug("[BOT] bot.session.close() failed", exc_info=True)
```

Add `self._task: Optional[asyncio.Task] = None` at the end of `__init__`.

Add the session guard at the top of `__init__` (after storing args):

```python
        session = getattr(bot, "session", None)
        if session is not None and type(session).__name__ in {"StringSession", "SQLiteSession"}:
            raise ValueError(
                "AiogramBotHead received a Telethon session object; it must only "
                "receive an aiogram.Bot authenticated by BOT_TOKEN."
            )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `SKIP_LIVE=1 python -m pytest tests/test_aiogram_head_lifecycle.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add src/services/core/telegram/aiogram_head.py tests/test_aiogram_head_lifecycle.py
git commit -m "feat(bot): aiogram head start/stop lifecycle + telethon-session guard

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 4: Wire Aiogram ingress in boot — start the head, register callbacks

**Files:**
- Modify: `src/bootstrap/orchestration/events.py:122-153`
- Modify: `src/bootstrap/orchestration/boot.py:115-142` (the `if not userbot_ready` branch and the normal path)
- Modify: `src/services/core/admin_bot/bot.py:33-45` (accept compat client for `bot_client`)
- Test: `tests/test_bot_ingress_selection.py` (extend — add `test_boot_starts_aiogram_head_when_selected`)

**Interfaces:**
- Consumes: `app_ctx.aiogram_bot` (from Task 1), `AiogramBotHead` (Task 3), `AiogramTelethonCompatClient` (Task 2), `register_event_handlers(client, bot_client, bot_runtime, hisobchi_engine, hisobchi_analyst, m, me)`.
- Produces:
  - When `bot_ingress_mode == "aiogram"`: `app_ctx.aiogram_bot_head` is a started `AiogramBotHead`; `app_ctx.bot_compat_client` is an attached `AiogramTelethonCompatClient`; the Telethon `bot_client` is NOT started and NOT given callback handlers.
  - `register_event_handlers` still registers ALL `client.add_event_handler(...)` userbot handlers unchanged. The bot-account callback handler (`_hisobchi_callback_handler`) is registered on `app_ctx.bot_compat_client` instead of `bot_client` when ingress is aiogram.
  - `AdminBot(bot_client=<compat_client>, ...)` — `AdminBot` treats `bot_client` purely as a thing with `.on(...)`; compat client provides that.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_bot_ingress_selection.py
@pytest.mark.asyncio
async def test_register_event_handlers_uses_compat_client_for_bot_callbacks(monkeypatch, _ctx):
    from src.settings import settings
    monkeypatch.setattr(settings, "TELEGRAM_BOT_RUNTIME_BACKEND", "aiogram", raising=False)
    monkeypatch.setattr(settings, "TELEGRAM_BOT_INGRESS_MODE", "aiogram", raising=False)

    from src.bootstrap.orchestration.telegram_session import init_bot_client_runtime
    init_bot_client_runtime()

    from aiogram import Dispatcher
    from src.services.core.telegram.aiogram_telethon_compat import AiogramTelethonCompatClient
    compat = AiogramTelethonCompatClient(bot=_ctx.aiogram_bot, dispatcher=Dispatcher())
    monkeypatch.setattr(_ctx, "bot_compat_client", compat, raising=False)

    registered = []
    orig_on = compat.on

    def _spy_on(builder):
        registered.append(type(builder).__name__)
        return orig_on(builder)

    monkeypatch.setattr(compat, "on", _spy_on)

    from src.bootstrap.orchestration.events import register_event_handlers

    class _FakeUserClient:
        def __init__(self):
            self.handlers = []
        def add_event_handler(self, fn, ev):
            self.handlers.append(type(ev).__name__)

    uc = _FakeUserClient()
    register_event_handlers(
        client=uc, bot_client=None, bot_runtime=_ctx.bot_runtime,
        hisobchi_engine=None, hisobchi_analyst=None, m=object(), me=None,
    )
    # userbot handlers still registered on the Telethon user client
    assert "NewMessage" in uc.handlers
    # bot-account callback went to the compat client, not a Telethon bot_client
    assert "CallbackQuery" in registered
```

- [ ] **Step 2: Run test to verify it fails**

Run: `SKIP_LIVE=1 python -m pytest tests/test_bot_ingress_selection.py::test_register_event_handlers_uses_compat_client_for_bot_callbacks -v`
Expected: FAIL — `events.py` currently branches on `bot_runtime.backend == "telethon"` and only ever touches `client` / `bot_client`, never `app_ctx.bot_compat_client`.

- [ ] **Step 3: Route bot-account callbacks through the compat client**

In `src/bootstrap/orchestration/events.py`, replace the block at lines 148-153:

```python
    # Bot-account callbacks: aiogram compat client when ingress is aiogram,
    # otherwise the Telethon bot-token client (legacy). The Telethon USERBOT
    # `client` always gets its own copy for hisobchi in userbot chats.
    from src.context import app_ctx as _app_ctx

    compat_client = getattr(_app_ctx, "bot_compat_client", None)
    if compat_client is not None:
        compat_client.on(events.CallbackQuery())(_hisobchi_callback_handler)
    elif getattr(bot_runtime, "backend", "telethon") == "telethon" and bot_client is not None:
        bot_client.add_event_handler(_hisobchi_callback_handler, events.CallbackQuery())

    if client:
        client.add_event_handler(_hisobchi_callback_handler, events.CallbackQuery())

    logger.info("[EVENTS] Safe userbot handlers registered.")
```

- [ ] **Step 4: Start the Aiogram head in boot**

In `src/bootstrap/orchestration/boot.py`, right after `bot_client, BOT_TOKEN_STR, bot_runtime, bot_ingress_mode = init_bot_client_runtime()` (line ~62), add:

```python
    # Aiogram bot-head ingress (userbot stays Telethon). Build the compat client
    # + dispatcher now so register_event_handlers can attach bot-account handlers.
    if bot_ingress_mode == "aiogram" and getattr(app_ctx, "aiogram_bot", None) is not None:
        from aiogram import Dispatcher
        from src.services.core.telegram.aiogram_telethon_compat import (
            AiogramTelethonCompatClient,
        )
        from src.services.core.telegram.aiogram_head import AiogramBotHead

        _dispatcher = Dispatcher()
        app_ctx.bot_compat_client = AiogramTelethonCompatClient(
            bot=app_ctx.aiogram_bot, dispatcher=_dispatcher
        )
        app_ctx.aiogram_bot_head = AiogramBotHead(
            bot=app_ctx.aiogram_bot,
            dispatcher=_dispatcher,
            allowed_updates=["message", "callback_query", "inline_query"],
        )
```

Then, where the code currently does `if BOT_TOKEN_STR and bot_runtime.backend == "telethon" and bot_ingress_mode == "polling": await bot_client.start(...)` (line ~125) and the normal-path admin bot start, add an aiogram branch. In BOTH the degraded (`if not userbot_ready`) branch and the normal path, after `register_event_handlers(...)`:

```python
    if bot_ingress_mode == "aiogram" and getattr(app_ctx, "bot_compat_client", None) is not None:
        app_ctx.bot_compat_client.attach()
        app_ctx.aiogram_bot_head.start()
        logger.info("[BOT] Aiogram bot-head ingress started (userbot stays Telethon).")
```

Guard the existing Telethon bot start so it does NOT run when ingress is aiogram (it already checks `bot_runtime.backend == "telethon"`, which is False for the aiogram backend — verify and leave as-is).

- [ ] **Step 5: Let AdminBot accept the compat client**

In `src/services/core/admin_bot/bot.py`, `__init__`, the line `self.bot_client = bot_client` needs no change (compat client has `.on`). But `self.bot_runtime = bot_runtime or TelethonBotRuntime(bot_client)` — when `bot_client` is the compat client, `TelethonBotRuntime(compat_client)` is wrong. Change to:

```python
        self.bot_client = bot_client
        if bot_runtime is not None:
            self.bot_runtime = bot_runtime
        elif hasattr(bot_client, "runtime"):
            # AiogramTelethonCompatClient exposes .runtime (AiogramBotRuntime)
            self.bot_runtime = bot_client.runtime
        else:
            self.bot_runtime = TelethonBotRuntime(bot_client)
```

Find where `AdminBot(...)` is constructed (`grep -rn "AdminBot(" src/`) and ensure it is passed `bot_client=app_ctx.bot_compat_client` when `app_ctx.bot_compat_client` exists, else the Telethon `bot_client`, and always `bot_runtime=app_ctx.bot_runtime`.

- [ ] **Step 6: Run tests**

Run: `SKIP_LIVE=1 python -m pytest tests/test_bot_ingress_selection.py tests/test_aiogram_compat_client.py tests/test_aiogram_head_lifecycle.py -v`
Expected: PASS (all)

- [ ] **Step 7: Full gate**

Run: `SKIP_LIVE=1 python -m pytest -q --tb=short`
Expected: PASS (no new failures vs. baseline). If a pre-existing test asserts `bot_runtime.backend == "telethon"` in a boot path, update it to accept `"aiogram"` where that is now valid.

- [ ] **Step 8: Commit**

```bash
git add src/bootstrap/orchestration/events.py src/bootstrap/orchestration/boot.py src/services/core/admin_bot/bot.py tests/test_bot_ingress_selection.py
git commit -m "feat(bot): start aiogram ingress head, route bot-account handlers via compat client

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 5: Aiogram webhook route (FastAPI) — production ingress option

**Files:**
- Create: `src/api/routes/telegram_webhook.py`
- Modify: `src/api_server.py` (mount the router alongside the other `src/api/routes/` routers)
- Modify: `src/settings.py` (add `TELEGRAM_WEBHOOK_SECRET: Optional[SecretStr] = None`, `TELEGRAM_WEBHOOK_BASE_URL: Optional[str] = None`)
- Test: `tests/test_telegram_webhook_route.py` (Create)

**Interfaces:**
- Consumes: `app_ctx.aiogram_bot` (aiogram `Bot`), a module-level `Dispatcher` shared with the compat client (`app_ctx` holds it — store it as `app_ctx.aiogram_dispatcher` in Task 4 Step 4), `settings.TELEGRAM_WEBHOOK_SECRET`.
- Produces:
  - `POST /telegram/webhook/{secret}` — 200 `{"ok": true}` when `secret` matches `TELEGRAM_WEBHOOK_SECRET`; 404 otherwise (no info leak). Body is a raw Telegram update JSON; the route feeds it to `dispatcher.feed_webhook_update(bot, update)`.
  - `router: APIRouter` exported for `api_server.py` to `include_router(...)`.
  - When `TELEGRAM_BOT_INGRESS_MODE == "webhook"` and backend is aiogram, Task 4's `boot.py` calls `bot.set_webhook(...)` instead of `.start()` on the head (add that branch).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_telegram_webhook_route.py
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def _app(monkeypatch):
    from src.settings import settings
    monkeypatch.setattr(settings, "TELEGRAM_WEBHOOK_SECRET",
                        SimpleNamespace(get_secret_value=lambda: "s3cr3t"), raising=False)

    fed = []

    class _FakeDispatcher:
        async def feed_webhook_update(self, bot, update):
            fed.append(update)

    from src.context import app_ctx
    monkeypatch.setattr(app_ctx, "aiogram_bot", SimpleNamespace(token="1:2"), raising=False)
    monkeypatch.setattr(app_ctx, "aiogram_dispatcher", _FakeDispatcher(), raising=False)

    from src.api.routes.telegram_webhook import router
    app = FastAPI()
    app.include_router(router)
    return TestClient(app), fed


def test_valid_secret_feeds_update(_app):
    client, fed = _app
    r = client.post("/telegram/webhook/s3cr3t", json={"update_id": 1, "message": {"text": "hi"}})
    assert r.status_code == 200
    assert r.json() == {"ok": True}
    assert fed == [{"update_id": 1, "message": {"text": "hi"}}]


def test_bad_secret_is_404(_app):
    client, _fed = _app
    r = client.post("/telegram/webhook/wrong", json={"update_id": 1})
    assert r.status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

Run: `SKIP_LIVE=1 python -m pytest tests/test_telegram_webhook_route.py -v`
Expected: FAIL — `src/api/routes/telegram_webhook.py` does not exist (ImportError).

- [ ] **Step 3: Create the route**

`src/api/routes/telegram_webhook.py`:

```python
"""Aiogram webhook ingress for the @jonairobot bot head.

The Telethon userbot never touches this route. Secret is a path segment so
Telegram's own retry/validation works without custom headers.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request

from src.context import app_ctx
from src.settings import settings

logger = logging.getLogger("TelegramWebhook")

router = APIRouter(prefix="/telegram", tags=["telegram"])


def _expected_secret() -> str:
    raw = getattr(settings, "TELEGRAM_WEBHOOK_SECRET", None)
    if raw is None:
        return ""
    try:
        return raw.get_secret_value() or ""
    except AttributeError:
        return str(raw or "")


@router.post("/webhook/{secret}")
async def telegram_webhook(secret: str, request: Request) -> dict:
    expected = _expected_secret()
    if not expected or secret != expected:
        raise HTTPException(status_code=404, detail="Not found")

    dispatcher = getattr(app_ctx, "aiogram_dispatcher", None)
    bot = getattr(app_ctx, "aiogram_bot", None)
    if dispatcher is None or bot is None:
        logger.warning("[WEBHOOK] Aiogram not initialised; dropping update")
        raise HTTPException(status_code=503, detail="Bot head not ready")

    update = await request.json()
    try:
        await dispatcher.feed_webhook_update(bot, update)
    except Exception:
        logger.exception("[WEBHOOK] feed_webhook_update failed")
        raise HTTPException(status_code=500, detail="update processing failed")
    return {"ok": True}
```

- [ ] **Step 4: Add settings fields**

In `src/settings.py`, near the other Telegram settings:

```python
    TELEGRAM_WEBHOOK_SECRET: Optional[SecretStr] = None
    TELEGRAM_WEBHOOK_BASE_URL: Optional[str] = None  # e.g. https://oisha.jonbranding.uz
```

- [ ] **Step 5: Mount the router**

In `src/api_server.py`, where other routers from `src/api/routes/` are included, add:

```python
    from src.api.routes.telegram_webhook import router as telegram_webhook_router
    app.include_router(telegram_webhook_router)
```

- [ ] **Step 6: Wire webhook mode in boot (extends Task 4 Step 4)**

In `src/bootstrap/orchestration/boot.py`, store the dispatcher on `app_ctx` when building it:

```python
        app_ctx.aiogram_dispatcher = _dispatcher
```

And where Task 4 starts the head, branch:

```python
    if bot_ingress_mode == "aiogram" and getattr(app_ctx, "bot_compat_client", None) is not None:
        app_ctx.bot_compat_client.attach()
        webhook_mode = str(getattr(settings, "TELEGRAM_BOT_INGRESS_MODE", "")).lower() == "webhook"
        base_url = getattr(settings, "TELEGRAM_WEBHOOK_BASE_URL", None)
        secret_raw = getattr(settings, "TELEGRAM_WEBHOOK_SECRET", None)
        secret = secret_raw.get_secret_value() if hasattr(secret_raw, "get_secret_value") else (secret_raw or "")
        if webhook_mode and base_url and secret:
            await app_ctx.aiogram_bot.set_webhook(
                url=f"{base_url.rstrip('/')}/telegram/webhook/{secret}",
                allowed_updates=["message", "callback_query", "inline_query"],
                drop_pending_updates=True,
            )
            logger.info("[BOT] Aiogram webhook registered at %s/telegram/webhook/***", base_url)
        else:
            app_ctx.aiogram_bot_head.start()
            logger.info("[BOT] Aiogram bot-head polling started (userbot stays Telethon).")
```

> Note: `TELEGRAM_BOT_INGRESS_MODE=webhook` with `TELEGRAM_BOT_RUNTIME_BACKEND=aiogram` is the production target on Oracle (Nginx already fronts FastAPI). `TELEGRAM_BOT_INGRESS_MODE=aiogram` (or `polling`) is for dev.

- [ ] **Step 7: Run tests**

Run: `SKIP_LIVE=1 python -m pytest tests/test_telegram_webhook_route.py -v`
Expected: PASS (2 tests)

- [ ] **Step 8: Full gate + bandit**

Run: `SKIP_LIVE=1 python -m pytest -q --tb=short && bandit -r src/api/routes/telegram_webhook.py src/services/core/telegram/ -ll`
Expected: tests PASS, bandit clean

- [ ] **Step 9: Commit**

```bash
git add src/api/routes/telegram_webhook.py src/api_server.py src/settings.py src/bootstrap/orchestration/boot.py tests/test_telegram_webhook_route.py
git commit -m "feat(bot): aiogram webhook ingress route + boot wiring

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 6: Guest-query handler on Aiogram (native, not compat)

**Files:**
- Modify: `src/services/core/guest_bot.py`
- Modify: `src/bootstrap/orchestration/boot.py` (register guest handler on the dispatcher when ingress is aiogram)
- Test: `tests/test_guest_bot_aiogram.py` (Create)

**Interfaces:**
- Consumes: aiogram `Dispatcher` (`app_ctx.aiogram_dispatcher`), aiogram `Bot` (`app_ctx.aiogram_bot`), `GuestBotHandler(bot_client, message_controller)` existing API.
- Produces:
  - `register_guest_handler_aiogram(dispatcher, bot, message_controller) -> None` — registers an `@dispatcher.inline_query()` (or message handler for guest DMs, matching current behavior) that answers guest queries via `bot.answer_inline_query(...)` / `answerGuestQuery`.
  - Existing Telethon `GuestBotHandler` path stays for the telethon backend.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_guest_bot_aiogram.py
from types import SimpleNamespace

import pytest


@pytest.mark.asyncio
async def test_guest_handler_registers_on_dispatcher():
    from src.services.core.guest_bot import register_guest_handler_aiogram

    registered = {}

    class _Dispatcher:
        def message(self, *a, **k):
            def deco(fn):
                registered["message"] = fn
                return fn
            return deco

        def inline_query(self, *a, **k):
            def deco(fn):
                registered["inline"] = fn
                return fn
            return deco

    class _MC:
        async def answer_guest_query(self, text):
            return f"answer:{text}"

    register_guest_handler_aiogram(_Dispatcher(), SimpleNamespace(token="1:2"), _MC())
    assert "message" in registered or "inline" in registered
```

- [ ] **Step 2: Run test to verify it fails**

Run: `SKIP_LIVE=1 python -m pytest tests/test_guest_bot_aiogram.py -v`
Expected: FAIL — `register_guest_handler_aiogram` not defined.

- [ ] **Step 3: Implement**

Read the current `GuestBotHandler` in `src/services/core/guest_bot.py` to see exactly what it does (guest DM vs inline). Add a sibling function that mirrors that behavior on aiogram. Keep the LLM/answer plumbing identical — only the Telegram I/O changes. Example skeleton (adapt to the real handler body):

```python
def register_guest_handler_aiogram(dispatcher, bot, message_controller) -> None:
    """Aiogram-native guest query handler (@jonairobot guest mode)."""
    from aiogram import F

    @dispatcher.message(F.text & ~F.text.startswith("/"))
    async def _guest_message(message):
        user_id = message.from_user.id if message.from_user else 0
        text = message.text or ""
        logger.info("[guest_bot] Guest query from user %s: %s", user_id, text[:80])
        try:
            answer = await message_controller.answer_guest_query(text)
        except Exception as e:  # pragma: no cover - network
            logger.error("[guest_bot] handle error: %s", e)
            return
        if answer:
            await message.answer(answer)
```

- [ ] **Step 4: Register it in boot**

In `src/bootstrap/orchestration/boot.py`, in the aiogram-ingress block after `attach()`:

```python
        try:
            from src.services.core.guest_bot import register_guest_handler_aiogram

            register_guest_handler_aiogram(
                app_ctx.aiogram_dispatcher, app_ctx.aiogram_bot, msg_controller
            )
        except Exception as guest_exc:
            logger.warning("[guest_bot] aiogram guest handler skipped: %s", guest_exc)
```

- [ ] **Step 5: Run tests**

Run: `SKIP_LIVE=1 python -m pytest tests/test_guest_bot_aiogram.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/services/core/guest_bot.py src/bootstrap/orchestration/boot.py tests/test_guest_bot_aiogram.py
git commit -m "feat(bot): aiogram-native guest query handler

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 7: Verification checklist + DEV_LOG + rollback doc

**Files:**
- Modify: `docs/DEV_LOG.md`
- Create: `docs/superpowers/plans/2026-09-09-aiogram-telethon-hybrid-VERIFY.md`
- Test: full suite

- [ ] **Step 1: Full gate**

Run: `SKIP_LIVE=1 python -m pytest -q --tb=short`
Expected: PASS. Record pass count.

- [ ] **Step 2: Security scan**

Run: `bandit -r src/ -ll -x src/services/debug/ --quiet`
Expected: no issues.

- [ ] **Step 3: Local smoke (dev machine, DEDICATED bot only)**

Prereqs: a `.env` with `ALLOW_LOCAL_RUN=1`, a throwaway `USERBOT_SESSION_STRING`, `TELEGRAM_BOT_RUNTIME_BACKEND=aiogram`, `TELEGRAM_BOT_INGRESS_MODE=aiogram`, valid `BOT_TOKEN`.

```bash
ALLOW_LOCAL_RUN=1 python src/main.py
```

Verify in logs:
- `[BOT] Aiogram bot-head polling started`
- No `AuthKeyDuplicatedError`
- Userbot handlers line: `[EVENTS] Safe userbot handlers registered.`

Then from Telegram, to @jonairobot:
- `/start` → replies (admin command via compat client)
- `/chatid` in the team group → replies
- Trigger a call-analysis (or use the existing test path) → summary lands in topic 548
- An inline approval button (`happrove:` / `scapprove:`) → callback handled, message edits

- [ ] **Step 4: Write DEV_LOG entry**

Append to `docs/DEV_LOG.md`:

```markdown
## 2026-09-09 — Aiogram/Telethon hybrid bot runtime

- Bot head (@jonairobot) can now run fully on Aiogram 3.x: outbound
  (`AiogramBotRuntime`) + ingress (`AiogramBotHead` polling or FastAPI
  webhook route `/telegram/webhook/{secret}`).
- Userbot (personal account) unchanged — 100% Telethon.
- Switch: `TELEGRAM_BOT_RUNTIME_BACKEND=aiogram` +
  `TELEGRAM_BOT_INGRESS_MODE=aiogram|webhook`. Default stays `telethon`.
- Rollback: set `TELEGRAM_BOT_RUNTIME_BACKEND=telethon` and restart. One var.
- Legacy Telethon `@bot_client.on(...)` admin handlers reused via
  `AiogramTelethonCompatClient` (no handler rewrites).
- Prod target on Oracle: `backend=aiogram`, `ingress=webhook`,
  `TELEGRAM_WEBHOOK_BASE_URL=https://oisha.jonbranding.uz`,
  `TELEGRAM_WEBHOOK_SECRET=<long random>`. Nginx already fronts FastAPI.
```

- [ ] **Step 5: Write the VERIFY doc**

`docs/superpowers/plans/2026-09-09-aiogram-telethon-hybrid-VERIFY.md` — a copy of the Step 3 checklist plus a production cutover section:

```markdown
# Aiogram Hybrid — Production Cutover (Oracle)

1. On Oracle VM, edit `/opt/oisha-os/.env` (or wherever the systemd unit reads):
   TELEGRAM_BOT_RUNTIME_BACKEND=aiogram
   TELEGRAM_BOT_INGRESS_MODE=webhook
   TELEGRAM_WEBHOOK_BASE_URL=https://oisha.jonbranding.uz
   TELEGRAM_WEBHOOK_SECRET=<generate: python -c "import secrets;print(secrets.token_urlsafe(32))">
2. Confirm Nginx forwards POST /telegram/webhook/ to the FastAPI upstream.
3. `sudo systemctl restart oisha-os`
4. `journalctl -u oisha-os -f` — expect:
   [BOT] Aiogram webhook registered at https://oisha.jonbranding.uz/telegram/webhook/***
   [EVENTS] Safe userbot handlers registered.
   NO AuthKeyDuplicatedError
5. `curl -sS https://oisha.jonbranding.uz/healthz` → ok
6. From Telegram: /start, /chatid, an approval callback, a fresh call analysis.
7. If anything breaks: set TELEGRAM_BOT_RUNTIME_BACKEND=telethon, restart,
   then `python -c "import asyncio; from aiogram import Bot; ..."` to delete the
   webhook (or Telegram auto-expires it once polling resumes).
```

- [ ] **Step 6: Commit**

```bash
git add docs/DEV_LOG.md docs/superpowers/plans/2026-09-09-aiogram-telethon-hybrid-VERIFY.md
git commit -m "docs: aiogram/telethon hybrid dev log + cutover checklist

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Self-Review

**Spec coverage:**
- "Userbotга bog'liq bo'lmagan narsalar aiogramga" → Tasks 1 (outbound), 4 (ingress + admin commands via compat), 5 (webhook), 6 (guest). ✅
- "Userbotdagi funksiyalar telethonda" → `events.py` `client.add_event_handler(...)` block untouched; Task 4 Step 3 only adds compat routing for the BOT callback, keeps `client.add_event_handler(_hisobchi_callback_handler, ...)` for userbot. ✅
- "Ikkalasidan maksimal foydalanish" → aiogram gets inline keyboards/FSM-ready dispatcher/webhook; Telethon keeps MTProto userbot powers. ✅
- Rollback safety → single env var, documented Task 7. ✅

**Placeholder scan:** Task 6 Step 3 says "adapt to the real handler body" — this is a deliberate read-first instruction with a concrete skeleton, not a TODO. Task 4 Step 5 says "Find where `AdminBot(...)` is constructed" — concrete grep given. Acceptable.

**Type consistency:**
- `init_bot_client_runtime() -> Tuple[Any, str, Any, str]` unchanged across Tasks 1, 4.
- `app_ctx.aiogram_bot`, `app_ctx.aiogram_dispatcher`, `app_ctx.bot_compat_client`, `app_ctx.aiogram_bot_head` — set in Task 1/4, consumed in Task 5/6. Names consistent.
- `AiogramBotHead(*, bot, dispatcher, allowed_updates, raw_update_handler)` — Task 3 defines, Task 4 constructs with `allowed_updates=[...]`. ✅
- `AiogramTelethonCompatClient(*, bot, dispatcher)` + `.on(builder)` + `.attach()` + `.runtime` — Task 2 defines, Task 4/5 consume. ✅
- `_compile_matcher` returns `str -> re.Match|None`; `AiogramLegacyMessageEvent(message, pattern_match=match)` — Task 2 internal, consistent.

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-09-09-aiogram-telethon-hybrid.md`. Two execution options:**

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
