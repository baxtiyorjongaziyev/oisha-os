"""
Telegram reports, proposal cards, and weekly summaries formatting mixin.
"""
from __future__ import annotations

import html
import logging
from typing import Any, Dict, List, Optional

from src.services.core.diagnosis.models import (
    SEVERITY_CRITICAL,
    SEVERITY_EMOJI,
    SEVERITY_HIGH,
    SEVERITY_LOW,
    SEVERITY_MEDIUM,
    ImprovementProposal,
)

logger = logging.getLogger("OishaSelfDiagnosis")


class ReportingMixin:
    """Formats diagnosis proposals and system health into structured Telegram messages."""

    def _field(proposal: Any, name: str, default: Any = "") -> Any:
        if isinstance(proposal, dict):
            return proposal.get(name, default)
        return getattr(proposal, name, default)

    @classmethod
    def format_telegram_report(cls, proposals: List[ImprovementProposal]) -> str:
        """Compact, HTML-safe daily digest for the owner."""
        if not proposals:
            return (
                "🧬 <b>OISHA RIVOJLANISH AUDITI</b>\n\n"
                "✅ Hozircha yangi muammo yoki imkoniyat topilmadi."
            )

        by_severity: Dict[str, List[ImprovementProposal]] = {}
        for proposal in proposals:
            severity = str(cls._field(proposal, "severity", SEVERITY_MEDIUM))
            by_severity.setdefault(severity, []).append(proposal)

        lines = [
            "🧬 <b>OISHA RIVOJLANISH AUDITI</b>",
            f"📊 <b>{len(proposals)}</b> ta dalilli taklif topildi.",
            "",
        ]
        shown = 0
        severity_labels = {
            SEVERITY_CRITICAL: "KRITIK",
            SEVERITY_HIGH: "YUQORI",
            SEVERITY_MEDIUM: "O'RTA",
            SEVERITY_LOW: "PAST",
        }
        for severity in (
            SEVERITY_CRITICAL,
            SEVERITY_HIGH,
            SEVERITY_MEDIUM,
            SEVERITY_LOW,
        ):
            items = by_severity.get(severity, [])
            if not items or shown >= 8:
                continue
            lines.append(
                f"{SEVERITY_EMOJI[severity]} <b>{severity_labels[severity]}</b> "
                f"({len(items)})"
            )
            for proposal in items[: 8 - shown]:
                proposal_id = html.escape(str(cls._field(proposal, "id")))
                title = html.escape(str(cls._field(proposal, "title"))[:100])
                agent = html.escape(str(cls._field(proposal, "suggested_agent"))[:40])
                effort = html.escape(str(cls._field(proposal, "estimated_effort"))[:20])
                lines.append(f"• <code>{proposal_id}</code> — {title}")
                lines.append(f"  🤖 {agent} · ⏱ {effort}")
                shown += 1
            lines.append("")

        hidden = len(proposals) - shown
        if hidden > 0:
            lines.append(f"Yana {hidden} ta taklif ro'yxatda.")
        lines.append("Qaror berish: /oisha_takliflar")
        return "\n".join(lines)[:3900]

    @classmethod
    def format_proposal_card(cls, proposal: Any) -> str:
        """Render one proposal for owner approval without leaking raw secrets."""
        proposal_id = html.escape(str(cls._field(proposal, "id")))
        title = html.escape(str(cls._field(proposal, "title"))[:160])
        problem = html.escape(str(cls._field(proposal, "problem"))[:700])
        solution = html.escape(str(cls._field(proposal, "proposed_solution"))[:700])
        agent = html.escape(str(cls._field(proposal, "suggested_agent"))[:80])
        effort = html.escape(str(cls._field(proposal, "estimated_effort"))[:40])
        severity = html.escape(str(cls._field(proposal, "severity", "medium")))
        files = cls._field(proposal, "affected_files", []) or []
        file_text = html.escape(", ".join(str(path) for path in files[:5])[:500])
        return (
            f"🧬 <b>{title}</b>\n"
            f"ID: <code>{proposal_id}</code> · {severity}\n\n"
            f"<b>Muammo:</b> {problem}\n\n"
            f"<b>Taklif:</b> {solution}\n\n"
            f"<b>Agent:</b> {agent} · <b>Vaqt:</b> {effort}\n"
            f"<b>Fayllar:</b> {file_text or 'aniqlanmagan'}\n\n"
            f"<i>⚠️ Tasdiqlansa, tanlangan AI-agent muammoni hal qilishga avtomatik kirishadi.</i>"
        )[:3900]

    @staticmethod
    def format_weekly_summary(
        current_proposals: List[ImprovementProposal],
        resolved_count: int = 0,
        total_proposed: int = 0,
    ) -> str:
        """Haftalik progress hisoboti."""
        lines = [
            "📊 <b>OISHA WEEKLY EVOLUTION REPORT</b>",
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            "",
            f"📥 Jami takliflar: <b>{total_proposed}</b>",
            f"✅ Hal qilingan: <b>{resolved_count}</b>",
            f"⏳ Kutilmoqda: <b>{len(current_proposals)}</b>",
            "",
        ]

        if total_proposed > 0:
            ratio = resolved_count / total_proposed * 100
            bar_filled = int(ratio / 10)
            bar = "█" * bar_filled + "░" * (10 - bar_filled)
            lines.append(f"📈 Progress: [{bar}] {ratio:.0f}%")

        # Open critical/high items
        urgent = [
            p
            for p in current_proposals
            if p.severity in (SEVERITY_CRITICAL, SEVERITY_HIGH)
        ]
        if urgent:
            lines.append("")
            lines.append(f"⚠️ <b>Ochiq urgent takliflar ({len(urgent)}):</b>")
            for p in urgent[:5]:
                lines.append(f"  • {p.title} ({p.suggested_agent})")

        return "\n".join(lines)
