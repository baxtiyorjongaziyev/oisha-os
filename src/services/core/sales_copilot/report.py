"""Report formatting: per-manager top-5 with drafts, owner funnel, alerts.

All output is internal (sales group topics). Drafts are shown for the manager
to copy; nothing here sends to a client.
"""
from __future__ import annotations

import html
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Iterable, List, Optional

from src.services.core.sales_copilot.rules import Alert
from src.services.core.sales_copilot.stage import STAGES, StageResult
from src.services.core.sales_copilot.transcript import Transcript

STAGE_LABELS = {
    "greeting": "Salom",
    "discovery": "Ehtiyoj",
    "offer": "Taklif",
    "objection": "Eʼtiroz",
    "card_sent": "Karta",
    "paid": "Toʻladi",
    "ghost": "Jim",
}
# Closeness to payment (paid excluded from top-5: it is already closed).
STAGE_WEIGHT = {"card_sent": 5.0, "offer": 4.0, "objection": 3.0, "discovery": 2.0, "greeting": 1.0, "ghost": 0.5}
TOP_N = 5


@dataclass
class Assessed:
    transcript: Transcript
    stage: StageResult
    last_at: Optional[datetime] = None


def closeness(a: Assessed) -> float:
    return STAGE_WEIGHT.get(a.stage.stage, 0.0) * (0.5 + a.stage.confidence / 2)


def top_for_manager(items: Iterable[Assessed], manager_key: str, n: int = TOP_N) -> List[Assessed]:
    mine = [a for a in items if a.transcript.manager_key == manager_key and a.stage.stage in STAGE_WEIGHT]
    mine.sort(key=lambda a: (closeness(a), a.last_at.timestamp() if a.last_at else 0.0), reverse=True)
    return mine[:n]


def format_top(manager_name: str, items: List[Assessed]) -> str:
    lines = [f"🎯 <b>{html.escape(manager_name)}</b> — toʻlovga eng yaqin {len(items)} ta mijoz"]
    if not items:
        lines.append("Bugun faol mijoz topilmadi.")
    for i, a in enumerate(items, 1):
        st = a.stage
        client = html.escape(a.transcript.client_name or a.transcript.chat_title or "?")
        lines.append(f"\n<b>{i}. {client}</b> — {STAGE_LABELS.get(st.stage, st.stage)} ({st.confidence:.0%})")
        if st.quote:
            lines.append(f"   💬 «{html.escape(st.quote[:160])}»")
        if st.blocker:
            lines.append(f"   ⛔ {html.escape(st.blocker[:160])}")
        if st.next_step:
            lines.append(f"   ➡️ {html.escape(st.next_step[:160])}")
        if st.draft:
            lines.append(f"   ✍️ Qoralama: <code>{html.escape(st.draft[:500])}</code>")
    lines.append("\nQoralamalar faqat sizga — mijozga oʻzingiz yuborasiz.")
    return "\n".join(lines)


def funnel(items: Iterable[Assessed], manager_keys: List[str]) -> Dict[str, Dict[str, int]]:
    table: Dict[str, Dict[str, int]] = {k: {s: 0 for s in STAGES} for k in manager_keys}
    for a in items:
        key = a.transcript.manager_key
        if key in table:
            table[key][a.stage.stage] += 1
    return table


def format_funnel(table: Dict[str, Dict[str, int]], names: Dict[str, str]) -> str:
    head = " | ".join(STAGE_LABELS[s] for s in STAGES)
    lines = ["📈 <b>Sotuv voronkasi</b> (bosqich × menejer)", f"<pre>Menejer | {head}"]
    totals = {s: 0 for s in STAGES}
    for key, row in table.items():
        lines.append(f"{names.get(key, key)} | " + " | ".join(str(row[s]) for s in STAGES))
        for s in STAGES:
            totals[s] += row[s]
    lines.append("Jami | " + " | ".join(str(totals[s]) for s in STAGES) + "</pre>")
    return "\n".join(lines)


ALERT_TEXT = {
    "reply": "⏱ <b>{client}</b> {mins} daqiqadan beri javob kutmoqda.",
    "price_followup": "🔁 <b>{client}</b>ga narx {hours} soat oldin yuborilgan, javob yoʻq. Follow-up qiling.",
    "card_reminder": "💳 <b>{client}</b>ga karta {hours} soat oldin yuborilgan, toʻlov yoʻq. Eslatib qoʻying.",
}


def format_alerts(manager_name: str, alerts: List[Alert], now: datetime) -> str:
    lines = [f"🔔 <b>{html.escape(manager_name)}</b>:"]
    for a in alerts:
        age = now - a.since
        lines.append(ALERT_TEXT[a.kind].format(
            client=html.escape(a.client), mins=int(age.total_seconds() // 60),
            hours=int(age.total_seconds() // 3600),
        ))
        if a.draft:
            lines.append(f"   ✍️ <code>{html.escape(a.draft[:400])}</code>")
    return "\n".join(lines)
