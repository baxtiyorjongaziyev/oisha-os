"""Source-bound account briefs and next actions; no fabricated forecast or cash totals."""
import json
from collections import defaultdict
from datetime import datetime, timezone


def _items(value):
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if not isinstance(value, str) or value.strip().lower() in {"", "n/a", "unknown", "noma'lum"}:
        return []
    try:
        parsed = json.loads(value)
    except ValueError:
        return [value]
    return [str(item) for item in parsed] if isinstance(parsed, list) else [value]


def account_intelligence(rows, evaluations, now=None):
    now = now or datetime.now(timezone.utc)
    by_lead = defaultdict(list)
    for row in rows:
        if row.get("lead_id"):
            by_lead[row["lead_id"]].append(row)
    briefs = []
    for lead_id, calls in by_lead.items():
        calls.sort(key=lambda row: str(row.get("analyzed_at") or row.get("created_at") or ""), reverse=True)
        latest = calls[0]
        next_steps = _items(latest.get("next_steps"))
        objections = list(dict.fromkeys(item for row in calls[:5] for item in _items(row.get("objections"))))
        warnings = []
        if not next_steps:
            warnings.append({"key": "next_step_unknown", "label": "Keyingi qadam qayd etilmagan"})
        if objections:
            warnings.append({"key": "objection_review", "label": "E'tirozlar qayd etilgan; yechimini tekshiring"})
        at = _timestamp(latest.get("analyzed_at") or latest.get("created_at"))
        if at and (now - at).total_seconds() > 7 * 86400:
            warnings.append({"key": "stale_analysis", "label": "Oxirgi tahlil 7 kundan eski"})
        action = next_steps[0] if next_steps else "Mijoz bilan keyingi qadam va muddatni aniqlashtiring"
        briefs.append({
            "lead_id": lead_id, "manager_id": latest.get("manager_id"),
            "summary": latest.get("summary") or "Xulosa mavjud emas",
            "source_call_ids": [r["call_id"] for r in calls[:5] if r.get("call_id")],
            "last_analyzed_at": at.isoformat() if at else None,
            "objections": objections, "next_action": action, "warnings": warnings,
            "priority": len(warnings), "crm_won_snapshot": latest.get("lead_won"),
            "follow_up_draft": "Assalomu alaykum. Avvalgi suhbatimizni davom ettirish uchun qaysi vaqt sizga qulay?",
            "draft_sent": False,
        })
    briefs.sort(key=lambda b: (-b["priority"], str(b["lead_id"])))
    differences = [abs(r["score"] - r["reviewed_score"]) for r in evaluations
                   if r.get("review_status") == "approved" and r.get("reviewed_score") is not None
                   and r.get("score") is not None]
    return {
        "source": "stored_call_analyses", "snapshot_at": now.isoformat(), "accounts": briefs,
        "review_summary": {"total": len(evaluations),
                           "pending": sum(r["review_status"] in {"pending", "appealed"} for r in evaluations),
                           "approved": sum(r.get("quality_approved", False) for r in evaluations)},
        "calibration": {"compared_reviews": len(differences),
                        "mean_absolute_difference": round(sum(differences) / len(differences), 1) if differences else None},
        "forecast": {"available": False, "reason": "Tasdiqlangan davr, reja va prognoz modeli ulanmagan"},
        "payroll_enabled": False,
    }


def _timestamp(value):
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        # Ambiguous naive time is unknown, never silently treated as UTC.
        return parsed.astimezone(timezone.utc) if parsed.tzinfo else None
    except (ValueError, TypeError):
        return None
