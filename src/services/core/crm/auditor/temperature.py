"""
Rule-based lead temperature (Iliq/Sovuq) scoring for CRM Contacts Auditor.

Runs entirely offline (no LLM call) on top of the data already collected during
`audit_lead_by_data`, so it costs nothing extra to compute.
"""
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, Tuple

logger = logging.getLogger(__name__)

# Signals that a lead is close to buying.
_HOT_KEYWORDS = (
    "narxi", "narx", "qancha turadi", "byudjet", "budget", "to'lov", "tolov",
    "shartnoma", "avans", "bank", "hisob raqam", "qachon boshlaymiz",
    "qachon boshlaysiz", "roziman", "kelishamiz", "kelishdik", "ha, davom eting",
    "ha davom eting", "buyurtma", "band qilaman", "band qiling",
)

# Signals that a lead has gone quiet or explicitly declined.
_COLD_KEYWORDS = (
    "keyinroq", "hozircha kerak emas", "hozir emas", "o'ylab ko'raman",
    "oylab koraman", "byudjetimiz yo'q", "budjetimiz yoq", "qimmat",
    "boshqasini topdik", "kerak bo'lmay qoldi", "kerak bolmay qoldi",
    "javob bermayapti", "javob bermadi",
)

_RECENT_DAYS_THRESHOLD = 7


def _days_since(timestamp: Any) -> float:
    try:
        ts = int(timestamp)
    except (TypeError, ValueError):
        return float("inf")
    if ts <= 0:
        return float("inf")
    delta = datetime.now(timezone.utc) - datetime.fromtimestamp(ts, tz=timezone.utc)
    return delta.total_seconds() / 86400.0


def _count_hits(text: str, keywords: Tuple[str, ...]) -> int:
    lowered = (text or "").lower()
    return sum(1 for kw in keywords if kw in lowered)


class TemperatureMixin:
    """Scores how close ('Iliq') or how stalled ('Sovuq') a lead currently is."""

    def score_lead_temperature(
        self,
        lead: Dict[str, Any],
        telegram_history: str = "",
        call_summary: str = "",
        notes_history: str = "",
        is_unanswered: bool = False,
    ) -> Tuple[str, str]:
        """Return (temperature, reason) where temperature is 'Iliq' or 'Sovuq'."""
        combined_text = "\n".join(
            filter(None, [telegram_history, call_summary, notes_history])
        )

        score = 0
        reasons = []

        hot_hits = _count_hits(combined_text, _HOT_KEYWORDS)
        if hot_hits:
            score += hot_hits
            reasons.append(f"xarid signali so'zlari topildi ({hot_hits})")

        cold_hits = _count_hits(combined_text, _COLD_KEYWORDS)
        if cold_hits:
            score -= cold_hits
            reasons.append(f"sovutuvchi so'zlar topildi ({cold_hits})")

        activity_days = min(
            _days_since(lead.get("updated_at")),
            _days_since(lead.get("created_at")),
        )
        if activity_days <= _RECENT_DAYS_THRESHOLD:
            score += 1
            reasons.append(f"so'nggi {_RECENT_DAYS_THRESHOLD} kun ichida faollik bor")
        else:
            score -= 1
            reasons.append(f"{_RECENT_DAYS_THRESHOLD} kundan ortiq faollik yo'q")

        if is_unanswered:
            score -= 1
            reasons.append("mijozning oxirgi xabari javobsiz qolgan")

        price = lead.get("price")
        try:
            if price and int(price) > 0:
                score += 1
                reasons.append("bitimda narx belgilangan")
        except (TypeError, ValueError):
            pass

        temperature = "Iliq" if score > 0 else "Sovuq"
        reason = "; ".join(reasons) if reasons else "yetarli ma'lumot yo'q"
        return temperature, reason
