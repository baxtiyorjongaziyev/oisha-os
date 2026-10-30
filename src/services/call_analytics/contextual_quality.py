"""Evidence-checked scoring with N/A and unknown kept distinct from failure."""
import hashlib
import math

from src.services.call_analytics.scorecards import EXCLUDED, SALES_TYPES, VERSION, scorecard


def _number(value):
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _quote(value, transcript):
    return value if isinstance(value, str) and 3 <= len(value) <= 1000 and value in transcript else ""


def evaluate_context(raw: dict, transcript: str) -> dict:
    call_type = raw.get("conversation_type")
    call_type = call_type if isinstance(call_type, str) else "unknown"
    card = scorecard(call_type)
    if card is None and call_type not in EXCLUDED:
        call_type = "unknown"
    confidence = _number(raw.get("type_confidence"))
    confidence = confidence if confidence is not None and 0 <= confidence <= 1 else None
    evidence = _quote(raw.get("type_evidence"), transcript)
    criteria = _evaluate_criteria(card, raw.get("qa_criteria"), transcript)
    scored = [c for c in criteria if c["status"] in {"met", "unmet"}]
    applicable = [c for c in criteria if c["status"] != "not_applicable"]
    score = round(100 * sum(c["status"] == "met" for c in scored) / len(scored), 1) if scored else None
    coverage = round(len(scored) / len(applicable), 3) if applicable else 0
    review_ready = bool(card and evidence and confidence is not None and confidence >= .8 and coverage >= .8)
    return {
        "call_type": call_type, "label": card["label"] if card else call_type,
        "scorecard_version": VERSION, "policy": "pilot", "type_confidence": confidence,
        "type_evidence": evidence, "criteria": criteria, "score": score, "coverage": coverage,
        "review_ready": review_ready, "sales_quality": call_type in SALES_TYPES,
        "review_status": "pending", "kpi_eligible": False,
        "transcript_digest": hashlib.sha256(transcript.encode()).hexdigest(),
    }


def _evaluate_criteria(card, raw, transcript):
    if not card:
        return []
    raw = raw if isinstance(raw, dict) else {}
    result = []
    for criterion in card["criteria"]:
        supplied = raw.get(criterion["id"])
        supplied = supplied if isinstance(supplied, dict) else {}
        status = supplied.get("status", "unknown")
        quote = _quote(supplied.get("quote"), transcript)
        reason = supplied.get("reason")
        reason = reason.strip()[:1000] if isinstance(reason, str) else ""
        if not isinstance(status, str) or status not in {"met", "unmet", "not_applicable", "unknown"}:
            status = "unknown"
        if status in {"met", "unmet"} and (not quote or not reason):
            status = "unknown"
        if status == "not_applicable" and (not criterion["conditional"] or not reason):
            status = "unknown"
        result.append({**criterion, "status": status, "quote": quote, "reason": reason})
    return result
