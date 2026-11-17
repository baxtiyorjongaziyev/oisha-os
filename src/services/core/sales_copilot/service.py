"""Copilot cycles: assess chats (stage + rules) and build internal messages.

Pure orchestration over already-collected transcripts so it can be dry-run and
tested without Telegram. ``send`` callbacks only ever target the sales group.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Awaitable, Callable, Dict, List, Optional

from src.services.core.card_watch import config
from src.services.core.sales_copilot import report, rules, signals, stage
from src.services.core.sales_copilot.transcript import Transcript

logger = logging.getLogger("SalesCopilot")

Sender = Callable[[str, Optional[int]], Awaitable[bool]]
ContextFn = Callable[[Transcript], Optional[Dict[str, Any]]]


async def assess(
    transcripts: List[Transcript],
    incomes: List[Dict[str, Any]],
    state: Dict[str, Any],
    now: datetime,
    router: Any = None,
    use_llm: bool = True,
    context_fn: Optional[ContextFn] = None,
) -> tuple[List[report.Assessed], List[rules.Alert]]:
    """Stage every chat (LLM only when it has new messages) and collect alerts."""
    cards = config.load_cards()
    assessed: List[report.Assessed] = []
    alerts: List[rules.Alert] = []
    chats = state.setdefault("chats", {})
    for t in transcripts:
        if not t.messages:
            continue
        sig = signals.compute(t, now, cards)
        entry = chats.setdefault(t.uid, {})
        cached = entry.get("stage")
        stamp = t.last_at.isoformat() if t.last_at else ""
        if cached and entry.get("classified_for") == stamp and cached.get("stage") != "ghost":
            result = stage.StageResult(**cached)
            if stage.check_paid(t, sig, incomes):
                result = stage.StageResult("paid", sig.card_message[:200], 0.95, source="airtable")
        else:
            crm = context_fn(t) if context_fn else None
            result = await stage.classify(t, sig, now, incomes, router=router, use_llm=use_llm, crm=crm)
            entry["stage"] = result.to_dict()
            entry["classified_for"] = stamp
        assessed.append(report.Assessed(t, result, t.last_at))
        alerts.extend(rules.evaluate(t, sig, state, now, paid=result.stage == "paid", draft=result.draft))
    return assessed, alerts


def dedupe(transcripts: List[Transcript]) -> List[Transcript]:
    """Same group seen from several accounts: keep the one attributed to a manager."""
    best: Dict[str, Transcript] = {}
    for t in transcripts:
        cur = best.get(t.uid)
        if cur is None or (cur.manager_key == "owner" and t.manager_key != "owner"):
            best[t.uid] = t
    return list(best.values())


async def send_alerts(alerts: List[rules.Alert], send: Sender, now: datetime) -> int:
    managers = {m.key: m for m in config.load_managers()}
    grouped: Dict[str, List[rules.Alert]] = {}
    for a in alerts:
        if a.manager_key in managers:  # sales managers only (no owner/Hasanboy)
            grouped.setdefault(a.manager_key, []).append(a)
    sent = 0
    for key, items in grouped.items():
        mgr = managers[key]
        if await send(report.format_alerts(mgr.name, items, now), mgr.topic_id):
            sent += len(items)
    return sent


async def send_daily(assessed: List[report.Assessed], send: Sender) -> int:
    """Per-manager top-5 to own topic + owner funnel to topic 118."""
    managers = config.load_managers()
    sent = 0
    for m in managers:
        top = report.top_for_manager(assessed, m.key)
        if await send(report.format_top(m.name, top), m.topic_id):
            sent += 1
    table = report.funnel(assessed, [m.key for m in managers])
    names = {m.key: m.name for m in managers}
    if await send(report.format_funnel(table, names), config.OWNER_TOPIC_ID):
        sent += 1
    return sent
