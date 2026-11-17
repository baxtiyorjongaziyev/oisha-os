"""Hourly "card sent -> payment" watcher (off by default: ``CARD_WATCH_ENABLED=1``).

Scans managers' dedicated Telegram sessions (+ the in-process prod client for the
owner's "X | Jon Branding" groups, read-only), matches Airtable ``Tranzaksiyalar``
income and reminds the manager in their sales-group topic. Respects quiet hours,
Sunday block and ``agent_policy`` kill-switches.
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any, List, Optional

from src.services.core.card_watch import config
from src.services.core.card_watch.detector import CardSend
from src.time_utils import get_local_now, is_quiet_hours, is_sunday

logger = logging.getLogger("CardWatch")

INTERVAL_SECONDS = 60 * 60
REPORT_HOUR = int(os.getenv("CARD_WATCH_REPORT_HOUR", "18"))


async def _policy_allows(db: Any) -> bool:
    """Hard quiet-hours/Sunday gate + agent_policy kill-switches."""
    now = get_local_now()
    if is_quiet_hours(now) or is_sunday(now):
        return False
    if db is None:
        return True
    try:
        from src.services.core.agent_policy import AgentPolicyEngine

        task = SimpleNamespace(kind="card_payment_reminder", requested_by="system", payload={"target": "internal"})
        decision = await AgentPolicyEngine(db).evaluate_action(task)
        return bool(decision.allowed)
    except Exception as exc:
        logger.warning("[CARD_WATCH] policy check failed (%s); skipping send", type(exc).__name__)
        return False


def _post(text: str, topic_id: Optional[int]) -> bool:
    import requests

    from src.settings import settings

    token = settings.BOT_TOKEN.get_secret_value()
    if topic_id is None:
        chat: Any = str(settings.OWNER_ID or "")
        payload = {"chat_id": chat, "text": text, "parse_mode": "HTML"}
    else:
        payload = {"chat_id": config.SALES_GROUP_ID, "message_thread_id": topic_id,
                   "text": text, "parse_mode": "HTML"}
    if not token or not payload["chat_id"]:
        return False
    try:
        r = requests.post(f"https://api.telegram.org/bot{token}/sendMessage", json=payload, timeout=20)
        return r.status_code == 200
    except requests.RequestException:
        return False


_ALERTED: dict = {}


async def alert_revoked_sessions(managers: List[Any], post: Any = None) -> List[str]:
    """Warn owner topic (118) once per status change when a session is revoked/invalid."""
    from src.services.core.card_watch.scanner import SESSION_STATUS

    post = post or _post
    alerted: List[str] = []
    for mgr in managers:
        status = SESSION_STATUS.get(mgr.key)
        if status not in {"revoked", "invalid"}:
            _ALERTED.pop(mgr.key, None)
            continue
        if _ALERTED.get(mgr.key) == status:
            continue
        text = (f"⚠️ Karta kuzatuvi: <b>{mgr.name}</b> sessiyasi "
                f"{'bekor qilingan' if status == 'revoked' else 'yaroqsiz'} — qayta ulash kerak.\n"
                f"Serverda: <code>python scripts/card_watch_login.py --manager {mgr.key}</code>")
        if await asyncio.to_thread(post, text, config.OWNER_TOPIC_ID):
            _ALERTED[mgr.key] = status
            alerted.append(mgr.key)
    return alerted


async def collect_sends(owner_client: Any = None) -> List[CardSend]:
    from src.services.core.card_watch.scanner import scan_client, scan_manager
    from src.settings import settings

    cards = config.load_cards()
    lookback = config.lookback_days()
    managers = config.load_managers()
    sends: List[CardSend] = []
    api_id = int(getattr(settings, "API_ID", 0) or 0)
    api_hash = str(getattr(settings, "API_HASH", "") or "")
    for mgr in managers:
        sends.extend(await scan_manager(mgr, api_id, api_hash, cards, lookback))
    await alert_revoked_sessions(managers)
    if owner_client is not None and os.getenv("CARD_WATCH_OWNER_GROUPS", "1") == "1":
        since = datetime.now(timezone.utc) - timedelta(days=lookback)
        usernames = {m.username.lower(): m.key for m in managers if m.username}
        try:
            sends.extend(await scan_client(owner_client, "owner", cards, since,
                                           owner_mode=True, username_map=usernames))
        except Exception as exc:
            logger.error("[CARD_WATCH] owner group scan failed: %s", type(exc).__name__)
    return sends


async def run_once(owner_client: Any = None, db: Any = None) -> dict:
    from src.services.core.card_watch.service import (
        fetch_income_records,
        run_cycle,
        send_daily_reports,
    )

    if not await _policy_allows(db):
        return {"skipped": "policy"}
    sends = await collect_sends(owner_client)
    incomes = []
    if sends:
        incomes = await asyncio.to_thread(fetch_income_records, config.lookback_days() + 7)

    async def _send(text: str, topic: Optional[int]) -> bool:
        return await asyncio.to_thread(_post, text, topic)

    result = await run_cycle(sends, incomes, _send)
    now = get_local_now()
    if now.hour >= REPORT_HOUR:
        result["reports"] = await send_daily_reports(_send, now.date().isoformat())
    return result


async def card_payment_watch_loop(bot_runtime: Any = None) -> None:
    if not config.is_enabled():
        logger.info("[CARD_WATCH] disabled (CARD_WATCH_ENABLED!=1)")
        return
    from src.context import app_ctx

    db = getattr(bot_runtime, "db", None) or getattr(bot_runtime, "db_instance", None)
    await asyncio.sleep(120)  # let the prod client finish connecting
    while True:
        try:
            result = await run_once(getattr(app_ctx, "client", None), db)
            logger.info("[CARD_WATCH] cycle: %s", result)
        except Exception as exc:
            logger.error("[CARD_WATCH] cycle error: %s", exc, exc_info=True)
        await asyncio.sleep(INTERVAL_SECONDS)
