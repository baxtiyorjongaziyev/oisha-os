"""Deterministic closing-likelihood. No LLM, no I/O. Injected `now`."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

DISCLAIMER = "AI bahosi (taxminiy), fakt emas."


@dataclass(frozen=True)
class ScoreResult:
    score: int
    band: str
    reasons: list[str]


def _epoch_to_dt(ts) -> datetime | None:
    try:
        return datetime.fromtimestamp(int(ts), tz=timezone.utc)
    except (TypeError, ValueError, OSError):
        return None


def _note_text(note: dict) -> str:
    params = note.get("params") or {}
    return str(params.get("text") or note.get("text") or "").lower()


def derive_features(lead, lead_tasks, lead_notes, lead_events, config, now):
    stage_weights = config.get("score.stage_weights", {})
    status_id = str(lead.get("status_id", ""))
    stage_weight = float(stage_weights.get(status_id, 0.15))

    open_tasks = [t for t in lead_tasks if not t.get("is_completed")]
    has_open_next_task = bool(open_tasks)
    now_epoch = now.timestamp()
    task_overdue = any(
        (t.get("complete_till") or 0) and float(t["complete_till"]) < now_epoch
        for t in open_tasks
    )
    meeting_held = any(
        t.get("is_completed") and t.get("task_type_id") == 2 for t in lead_tasks
    )

    notes_sorted = sorted(lead_notes, key=lambda n: n.get("created_at") or 0)
    obj_kw = config.get("score.objection_keywords", [])
    pay_kw = config.get("score.payment_keywords", [])
    objection_open = False
    for n in notes_sorted:
        txt = _note_text(n)
        if any(k in txt for k in obj_kw):
            later = [_note_text(m) for m in notes_sorted
                     if (m.get("created_at") or 0) > (n.get("created_at") or 0)]
            if not any(("hal qilindi" in t or "kelishildi" in t) for t in later):
                objection_open = True
    payment_promised = any(
        any(k in _note_text(n) for k in pay_kw) for n in notes_sorted
    )
    proposal_sent = stage_weight >= 0.5 or any(
        ("kp" in _note_text(n) or "taklif" in _note_text(n)) for n in notes_sorted
    )

    status_events = sorted(
        (e for e in lead_events if e.get("type") == "lead_status_changed"),
        key=lambda e: e.get("created_at") or 0,
    )
    if status_events:
        stage_start = _epoch_to_dt(status_events[-1]["created_at"])
    else:
        stage_start = _epoch_to_dt(lead.get("created_at"))
    days_in_stage = (now - stage_start).total_seconds() / 86400 if stage_start else 999.0

    interaction_epochs = []
    interaction_epochs += [e.get("created_at") or 0 for e in lead_events]
    interaction_epochs += [
        t.get("complete_till") or 0 for t in lead_tasks if t.get("is_completed")
    ]
    interaction_epochs += [n.get("created_at") or 0 for n in lead_notes]
    latest = max(interaction_epochs) if interaction_epochs else 0
    last_interaction_hours = (
        (now_epoch - latest) / 3600 if latest else 999.0
    )

    return {
        "stage_weight": stage_weight,
        "last_interaction_hours": last_interaction_hours,
        "has_open_next_task": has_open_next_task,
        "task_overdue": task_overdue,
        "proposal_sent": proposal_sent,
        "meeting_held": meeting_held,
        "objection_open": objection_open,
        "payment_promised": payment_promised,
        "days_in_stage": days_in_stage,
    }


def score_lead(features, config) -> ScoreResult:
    w = config["score.weights"]
    cutoffs = config["score.band_cutoffs"]
    score = 0.0
    reasons: list[str] = []

    score += round(features["stage_weight"] * w["stage"])
    if features["stage_weight"] >= 0.5:
        reasons.append("Bosqich yakuniga yaqin")

    if features["has_open_next_task"]:
        score += w["open_next_task"]
    else:
        score += -abs(w["open_next_task"])
        reasons.append("Keyingi task yo'q")

    if features["proposal_sent"]:
        score += w["proposal_sent"]
        reasons.append("KP yuborilgan")
    if features["meeting_held"]:
        score += w["meeting_held"]
        reasons.append("Uchrashuv bo'lgan")
    if features["payment_promised"]:
        score += w["payment_promised"]
        reasons.append("To'lov va'da qilingan")

    h = features["last_interaction_hours"]
    if h <= 24:
        score += w["recent_0_24h"]
    elif h > 72:
        score += w["recent_gt_72h"]
        reasons.append("72 soatdan beri aloqa yo'q")

    if features["objection_open"]:
        score += w["objection_open"]
        reasons.append("Ochiq e'tiroz bor")
    if features["task_overdue"]:
        score += w["task_overdue"]
        reasons.append("Muddati o'tgan task")

    d = features["days_in_stage"]
    if d <= 7:
        score += w["days_in_stage_le_7"]
    elif d > 21:
        score += w["days_in_stage_gt_21"]
        reasons.append("Bosqichda 3 haftadan ko'p")

    score_i = max(0, min(100, int(round(score))))
    if score_i >= cutoffs["hot"]:
        band = "HOT"
    elif score_i >= cutoffs["warm"]:
        band = "WARM"
    else:
        band = "COLD"
    return ScoreResult(score=score_i, band=band, reasons=reasons)
