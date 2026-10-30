"""Conservative extraction; model outcomes are not proof of a sale."""
from __future__ import annotations

import math
import re

from src.services.utils.transcript import strip_timestamps

FAMILIES = {"Ehtiyoj aniqlash": "discovery", "Yechim taqdimoti": "presentation",
            "Narx muhokamasi": "negotiation", "Follow-up": "follow_up", "Shartnoma": "closing"}
SERVICES = {"Brending", "Dizayn", "SMM", "Sayt", "Biznes transformatsiya", "Reklama"}
AGENT = re.compile(r"^(?:sotuvchi|menejer|manager|agent|xodim)\s*:\s*(.+)$", re.I)
PRIVATE = re.compile(r"https?://\S+|\S+@\S+|\+?\d[\d\s().-]{5,}\d", re.I)
SENSITIVE = re.compile(r"(?:parol|password|token|api.?key|session|otp|pin.?kod)", re.I)


def quality_score(analysis: dict) -> float | None:
    contextual = analysis.get("contextual_evaluation")
    if isinstance(contextual, dict):
        if not contextual.get("review_ready") or not contextual.get("sales_quality"):
            return None
        raw = contextual.get("score")
    else:
        raw = analysis.get("sifat_bahosi", analysis.get("overall_score"))
    if isinstance(raw, bool):
        return None
    try:
        score = float(raw)
    except (ValueError, TypeError):
        return None
    return score if math.isfinite(score) and 75 <= score <= 100 else None


def script_group(analysis: dict) -> str | None:
    if analysis.get("category") != "Mijoz" or analysis.get("rubrik_amal_qiladi") is not True:
        return None
    family = FAMILIES.get(analysis.get("suhbat_oilasi"))
    contextual = analysis.get("contextual_evaluation")
    if isinstance(contextual, dict):
        from src.services.call_analytics.scorecards import SALES_TYPES
        family = contextual.get("call_type")
        if family not in SALES_TYPES:
            return None
    service = analysis.get("servis_yonalishi")
    return f"{family}:{service}" if family and service in SERVICES else None


def extract_examples(transcript: str) -> list[str]:
    """Private historical examples, not inferred promises or causal techniques."""
    examples = []
    for line in strip_timestamps(transcript).splitlines():
        match = AGENT.match(line.strip())
        if not match:
            continue
        quote = match.group(1).strip()
        if SENSITIVE.search(quote) or not 20 <= len(quote) <= 500:
            continue
        quote = PRIVATE.sub("[kontakt]", quote)
        if quote not in examples:
            examples.append(quote)
    return examples[:5]


def verified_sale(lead: object, lead_id: int, occurred_at: int, now: int) -> bool:
    """CRM won is a CRM sale signal, never proof that cash was received."""
    if not isinstance(lead, dict) or lead.get("is_deleted"):
        return False
    try:
        return (int(lead["id"]) == lead_id and int(lead["status_id"]) == 142
                and 0 < occurred_at <= int(lead["closed_at"]) <= now)
    except (KeyError, ValueError, TypeError, OverflowError):
        return False
