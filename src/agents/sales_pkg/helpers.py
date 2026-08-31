"""
Constants, escalation triggers and payload formatters for SalesAgent.
"""
from __future__ import annotations

import logging
import re
from datetime import timedelta
from typing import Any, Dict, List, Optional

from src.time_utils import get_local_now

logger = logging.getLogger(__name__)

try:
    from src.services.core.auto_reply_gate import ESCALATION_TRIGGERS
except Exception:
    ESCALATION_TRIGGERS = (
        "shikoyat",
        "qaytarish",
        "advokat",
        "sud",
        "vaqtida bermadi",
        "aldadi",
        "firibgar",
        "qaytarib bering",
    )

ESCALATION_CLOSE_PROB_THRESHOLD = 0.30
ESCALATION_RISK_FLAGS = {"legal_review", "competitive_pressure", "negative_sentiment"}


class SalesFormattingMixin:
    """Meeting extraction, escalation detection and note formatting."""

    def _extract_meeting_window(self, text: str) -> Optional[Dict[str, str]]:
        lowered = (text or "").lower()
        has_meeting_intent = any(
            token in lowered
            for token in [
                "uchrash", "zoom", "google meet", "gaplashaylik", "gaplashsak",
                "qo'ng'iroq", "qongiroq", "call", "audio", "video",
                "ertaga", "bugun", "dushanba", "seshanba", "chorshanba",
                "payshanba", "juma", "shanba", "yakshanba",
            ]
        )
        if not has_meeting_intent:
            return None

        match = re.search(r"(?<!\d)(?:soat\s*)?([01]?\d|2[0-3])(?::([0-5]\d))?\s*(?:da|ga|lar)?", lowered)
        hour = 15
        minute = 0
        if match:
            hour = int(match.group(1))
            minute = int(match.group(2) or 0)

        now = get_local_now()
        start = now.replace(minute=minute, second=0, microsecond=0)
        if hour < now.hour or (hour == now.hour and minute <= now.minute):
            start = (start + timedelta(days=1)).replace(hour=hour)
        else:
            start = start.replace(hour=hour)

        end = start + timedelta(minutes=45)
        iso_start = start.isoformat()
        iso_end = end.isoformat()
        return {
            "summary": "Mijoz bilan strategik sessiya (Jon Branding)",
            "start": iso_start,
            "end": iso_end,
            "start_time": iso_start,
            "end_time": iso_end,
        }

    def _fallback_reply(self, assessment, task_description: str) -> str:
        if assessment.stage == "qualified":
            return (
                "Taklifingizni ko'rib chiqdim. Jon Branding loyihangiz bo'yicha "
                "aniq konsepsiya va muddatni taklif qila oladi. Qaysi yo'nalish "
                "birlamchi: brending, logo yoki qadoq dizayni?"
            )
        if assessment.intent == "pricing":
            return (
                "Loyihangiz talablarini inobatga olgan holda narx variantlarini "
                "shakllantiramiz. Byudjet doirangiz va kutayotgan muddatni aytsangiz, "
                "optimal paketni taqdim qilamiz."
            )
        if assessment.stage in ("proposal", "negotiation"):
            return (
                "Sizga moslashtirilgan taklif va shartlarni yuborishga tayyormiz. "
                "Tafsilotlarni qisqa audio/matn orqali aniqlashtirib olsak bo'ladimi?"
            )
        return (
            "Xabaringiz uchun rahmat. Loyihangiz bo'yicha mas'ul mutaxassis "
            "qisqa vaqtda to'liq ma'lumot bilan aloqaga chiqadi."
        )

    def _build_lead_note(
        self,
        assessment,
        task_description: str,
        user_id: Optional[int],
        lead_id: Optional[int],
        action_plan: List[Dict[str, Any]],
        ai_reply: Optional[str] = None,
        persona: Optional[str] = None,
    ) -> str:
        lines = [
            "[OISHA NEGOTIATION]",
            f"Stage: {assessment.stage}",
            f"Intent: {assessment.intent}",
            f"Objection: {assessment.objection}",
            f"Urgency: {assessment.urgency}",
            f"Sentiment: {assessment.sentiment}",
            f"Close Prob: {int(assessment.close_probability * 100)}%",
            f"Mode: {assessment.autonomy_mode}",
            f"Next: {assessment.next_action}",
            f"Actions: {len(action_plan)}",
            f"Context: {task_description[:300]}",
        ]
        if ai_reply:
            lines.append(f"Draft Reply: {ai_reply[:400]}")
        if persona:
            lines.append(f"Persona: {persona}")
        return "\n".join(lines)

    def _build_followup_payload(self, assessment, user_id: Optional[int], lead_id: Optional[int]) -> Dict[str, Any]:
        complete_after_hours = 24
        if assessment.urgency in ("high", "urgent"):
            complete_after_hours = 4
        elif assessment.stage == "qualified":
            complete_after_hours = 12
        elif assessment.stage == "commitment":
            complete_after_hours = 6
        elif assessment.stage == "closed_won":
            complete_after_hours = 72

        complete_till = int((get_local_now() + timedelta(hours=complete_after_hours)).timestamp())
        task_text = f"Oisha CRM Followup: {assessment.intent} / {assessment.objection} -> {assessment.next_action}"

        return {
            "lead_id": lead_id,
            "user_id": user_id,
            "text": task_text,
            "complete_till": complete_till,
        }

    def _detect_escalation(self, message_text: str, assessment: Any) -> Optional[str]:
        lowered = (message_text or "").lower()
        for trigger in ESCALATION_TRIGGERS:
            if trigger in lowered:
                return f"trigger_word:{trigger}"

        if getattr(assessment, "risk_flags", None):
            hit_flags = [f for f in assessment.risk_flags if f in ESCALATION_RISK_FLAGS]
            if hit_flags:
                return f"risk_flag:{hit_flags[0]}"

        close_prob = getattr(assessment, "close_probability", 1.0)
        if close_prob < ESCALATION_CLOSE_PROB_THRESHOLD:
            return f"low_close_prob:{close_prob:.2f}"

        return None
