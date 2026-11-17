"""Sales copilot loop (off by default: ``SALES_COPILOT_ENABLED=1``).

* every 5 min: cheap reply-wait check from each dialog's last message
* hourly: full transcripts -> stage (free_ai_router, cached per new message)
  -> price/card follow-up suggestions
* daily (``SALES_COPILOT_REPORT_HOUR``, default 18): per-manager top-5 + owner funnel

Reuses card_watch manager sessions and the in-process owner client (read-only).
Messages go only to the sales group topics (shadow); clients never get anything.
Respects quiet hours, Sunday and ``agent_policy`` via the card_watch gate.
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, List, Optional

from src.services.core.card_watch import config
from src.time_utils import get_local_now

logger = logging.getLogger("SalesCopilot")

FAST_INTERVAL = 5 * 60
FULL_EVERY = 12  # fast ticks per full cycle (= 1 hour)
LOOKBACK_DAYS = 7


def is_enabled() -> bool:
    return os.getenv("SALES_COPILOT_ENABLED", "0") == "1"


def report_hour() -> int:
    try:
        return int(os.getenv("SALES_COPILOT_REPORT_HOUR", "18"))
    except ValueError:
        return 18


def _api() -> tuple[int, str]:
    from src.settings import settings

    return int(getattr(settings, "API_ID", 0) or 0), str(getattr(settings, "API_HASH", "") or "")


async def collect_all(owner_client: Any = None, lookback_days: int = LOOKBACK_DAYS) -> List[Any]:
    from src.services.core.sales_copilot.transcript import collect_transcripts, with_manager_client

    since = datetime.now(timezone.utc) - timedelta(days=lookback_days)
    api_id, api_hash = _api()
    managers = config.load_managers()
    out: List[Any] = []
    for m in managers:
        async def work(client: Any, key: str = m.key) -> List[Any]:
            return await collect_transcripts(client, key, since)

        out.extend(await with_manager_client(m, api_id, api_hash, work, []))
    if owner_client is not None and os.getenv("CARD_WATCH_OWNER_GROUPS", "1") == "1":
        usernames = {m.username.lower(): m.key for m in managers if m.username}
        try:
            out.extend(await collect_transcripts(owner_client, "owner", since, owner_mode=True,
                                                 username_map=usernames))
        except Exception as exc:
            logger.error("[SALES_COPILOT] owner scan failed: %s", type(exc).__name__)
    return out


async def fast_check(owner_client: Any = None) -> List[Any]:
    """Reply-wait alerts from dialog last messages (manager private chats only)."""
    from src.services.core.card_watch.scanner import _client_name, _is_scannable
    from src.services.core.sales_copilot import rules
    from src.services.core.sales_copilot.transcript import with_manager_client

    now = datetime.now(timezone.utc)
    state = rules.load_state()
    api_id, api_hash = _api()
    alerts: List[Any] = []
    for m in config.load_managers():
        async def work(client: Any, key: str = m.key) -> List[Any]:
            found = []
            async for d in client.iter_dialogs(limit=100):
                if not _is_scannable(d, False) or d.message is None:
                    continue
                uid = f"g:{int(d.id)}" if int(d.id) < 0 else f"{key}:{int(d.id)}"
                a = rules.reply_alert_from_last(uid, key, _client_name(d), bool(d.message.out),
                                                d.message.date, state, now)
                if a:
                    found.append(a)
            return found

        alerts.extend(await with_manager_client(m, api_id, api_hash, work, []))
    rules.save_state(state)
    return alerts


async def full_cycle(owner_client: Any, send: Any, daily: bool) -> dict:
    from src.services.core.card_watch.service import fetch_income_records
    from src.services.core.sales_copilot import context, rules, service

    now = datetime.now(timezone.utc)
    transcripts = service.dedupe(await collect_all(owner_client))
    incomes: List[Any] = []
    try:
        from src.services.core.card_watch.matcher import income_rows

        incomes = income_rows(await asyncio.to_thread(fetch_income_records, LOOKBACK_DAYS + 30))
    except Exception as exc:
        logger.warning("[SALES_COPILOT] Airtable income unavailable: %s", type(exc).__name__)
    state = rules.load_state()
    assessed, alerts = await service.assess(
        transcripts, incomes, state, now,
        context_fn=lambda t: context.find_context(t.client_name or t.chat_title),
    )
    result = {"chats": len(assessed), "alerts": await service.send_alerts(alerts, send, now)}
    if daily:
        result["reports"] = await service.send_daily(assessed, send)
        state.setdefault("_meta", {})["report_date"] = get_local_now().date().isoformat()
    rules.save_state(state)
    return result


async def sales_copilot_loop(bot_runtime: Any = None) -> None:
    if not is_enabled():
        logger.info("[SALES_COPILOT] disabled (SALES_COPILOT_ENABLED!=1)")
        return
    from src.context import app_ctx
    from src.schedulers.card_payment_watch_scheduler import _policy_allows, _post
    from src.services.core.sales_copilot import rules, service

    db = getattr(bot_runtime, "db", None) or getattr(bot_runtime, "db_instance", None)

    async def send(text: str, topic: Optional[int]) -> bool:
        if topic is None:  # never fall back to DMs: topics only
            return False
        return await asyncio.to_thread(_post, text, topic)

    await asyncio.sleep(180)
    tick = 0
    while True:
        try:
            if await _policy_allows(db):
                owner_client = getattr(app_ctx, "client", None)
                if tick % FULL_EVERY == 0:
                    local = get_local_now()
                    meta = rules.load_state().get("_meta", {})
                    daily = local.hour >= report_hour() and meta.get("report_date") != local.date().isoformat()
                    logger.info("[SALES_COPILOT] full: %s", await full_cycle(owner_client, send, daily))
                else:
                    alerts = await fast_check(owner_client)
                    if alerts:
                        await service.send_alerts(alerts, send, datetime.now(timezone.utc))
        except Exception as exc:
            logger.error("[SALES_COPILOT] cycle error: %s", exc, exc_info=True)
        tick += 1
        await asyncio.sleep(FAST_INTERVAL)
