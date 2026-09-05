"""
Telegram excellence reports and department-level direct message builders.
"""
from __future__ import annotations

from html import escape
import logging
from typing import Any, Dict, List, Optional

from src.services.core.airtable_sync import AirtableSync
from src.services.core.client_journey.models import (
    JourneySignal,
    _humanize_stage,
    _normalize_copy,
    _render_airtable_card_line,
    _render_owner_html,
)

logger = logging.getLogger("ClientJourneyPlaybook")

def _render_signal_lines(
    signal: JourneySignal, airtable: Optional[AirtableSync]
) -> List[str]:
    lines = [
        f"• <b>{escape(signal.client_name)}</b>",
        f"  Bosqich: {escape(_humanize_stage(signal.stage))}",
        f"  Mas'ul: {_render_owner_html(signal, airtable)}",
        f"  Xavf: {escape(_normalize_copy(signal.risk))}",
        f"  Bugungi qadam: {escape(_normalize_copy(signal.owner_action))}",
        f"  Mijoz ko'radigan wow qadam: {escape(_normalize_copy(signal.wow_action))}",
    ]
    card_line = _render_airtable_card_line(signal, airtable)
    if card_line:
        lines.append(card_line)
    return lines


def render_excellence_report(
    sales_signals: List[JourneySignal],
    project_signals: List[JourneySignal],
    *,
    max_items_per_section: int = 4,
) -> str:
    try:
        airtable = AirtableSync()
    except Exception:
        logger.error("Exception handled in %s", __name__, exc_info=True)
        airtable = None

    total_signals = len(sales_signals) + len(project_signals)
    critical_count = sum(
        1 for signal in sales_signals + project_signals if signal.urgency == "critical"
    )

    score = 100
    if total_signals > 0:
        score = max(0, 100 - (critical_count * 20) - (total_signals * 2))

    if score >= 90:
        score_emoji = "💎"
    elif score >= 75:
        score_emoji = "⭐"
    elif score >= 50:
        score_emoji = "⚠️"
    else:
        score_emoji = "🚨"

    lines = [
        f"<b>{score_emoji} Oisha Wow-Service Audit</b>",
        f"<b>Servis sifati bahosi: {score}%</b>",
        "Talab: har bosqichda mijoz 'wow' sezsin, jimlik va noaniqlik qolmasin.",
        "",
    ]

    if sales_signals:
        lines.append(
            f"<b>Sotuv / Birinchi taassurot</b> - {len(sales_signals)} ta signal"
        )
        for signal in sales_signals[:max_items_per_section]:
            lines.extend(_render_signal_lines(signal, airtable))
        lines.append("")

    if project_signals:
        lines.append(
            f"<b>PM / Yetkazib berish sifati</b> - {len(project_signals)} ta signal"
        )
        for signal in project_signals[:max_items_per_section]:
            lines.extend(_render_signal_lines(signal, airtable))
        lines.append("")

    lines.append(
        "Standart: har bir signal bo'yicha 1) keyingi qadam, 2) mas'ul odam, 3) muddat, 4) mijozga yuborilgan yakuniy xabar bo'lishi shart."
    )
    return "\n".join(lines).strip()


def build_department_direct_messages(
    team_members: List[Dict[str, Any]],
    sales_signals: List[JourneySignal],
    project_signals: List[JourneySignal],
) -> List[Dict[str, Any]]:
    messages: List[Dict[str, Any]] = []
    sales_role_tokens = ("sales", "sotuv", "hunter", "closer", "manager")
    pm_role_tokens = ("pm", "project", "manager")

    def _belongs(member: Dict[str, Any], tokens: tuple[str, ...]) -> bool:
        role_blob = " ".join(
            str(member.get(key, "") or "").lower()
            for key in ("role", "detailed_role", "position")
        )
        return any(token in role_blob for token in tokens)

    sales_text = None
    if sales_signals:
        sales_lines = ["<b>Bugungi sotuv wow-service fokusi</b>"]
        for signal in sales_signals[:3]:
            sales_lines.append(
                f"• <b>{escape(signal.client_name)}</b>: {escape(_normalize_copy(signal.owner_action))}"
            )
        sales_lines.append("Talab: CRMda keyingi qadam, sabab va sana yozilsin.")
        sales_text = "\n".join(sales_lines)

    pm_text = None
    if project_signals:
        pm_lines = ["<b>Bugungi PM wow-service fokusi</b>"]
        for signal in project_signals[:3]:
            pm_lines.append(
                f"• <b>{escape(signal.client_name)}</b>: {escape(_normalize_copy(signal.owner_action))}"
            )
        pm_lines.append(
            "Talab: mijozga yakuniy xabar, mas'ul odam va muddat aniq yozilsin."
        )
        pm_text = "\n".join(pm_lines)

    for member in team_members:
        user_id = member.get("user_id")
        if not user_id:
            continue
        if sales_text and _belongs(member, sales_role_tokens):
            messages.append(
                {"user_id": user_id, "text": sales_text, "parse_mode": "HTML"}
            )
        elif pm_text and _belongs(member, pm_role_tokens):
            messages.append({"user_id": user_id, "text": pm_text, "parse_mode": "HTML"})

    return messages
