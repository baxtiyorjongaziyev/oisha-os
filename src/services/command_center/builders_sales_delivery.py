"""
Sales priority and project delivery risk builders for Command Center.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any
from src.services.command_center.models import (
    ProjectRiskItem,
    SalesPriorityLead,
    CLOSED_LEAD_STATUS_IDS,
    CLOSED_PROJECT_STAGE_MARKERS,
    _age_days,
    _age_hours,
    _field_text,
    _has_overdue_task,
    _int_or_zero,
    _lead_contacts,
    _parse_date,
)

def build_sales_today_priorities(
    leads: list[dict[str, Any]],
    *,
    open_tasks_by_lead: dict[int, list[dict[str, Any]]] | None = None,
    now: datetime | None = None,
    limit: int = 12,
) -> dict[str, Any]:
    """Rank open AmoCRM leads for today's seller conversations."""
    current = now or datetime.now(timezone.utc)
    tasks_map = open_tasks_by_lead or {}
    ranked: list[SalesPriorityLead] = []
    skipped_closed = 0

    for lead in leads:
        lead_id = _int_or_zero(lead.get("id"))
        status_id = _int_or_zero(lead.get("status_id"))
        if status_id in CLOSED_LEAD_STATUS_IDS:
            skipped_closed += 1
            continue
        if not lead_id:
            continue

        tasks = tasks_map.get(lead_id, [])
        contacts = _lead_contacts(lead)
        updated_at = _int_or_zero(lead.get("updated_at"))
        created_at = _int_or_zero(lead.get("created_at"))
        responsible_id = _int_or_zero(lead.get("responsible_user_id"))
        price = _int_or_zero(lead.get("price"))
        updated_age_hours = _age_hours(updated_at, current)
        created_age_days = _age_days(created_at, current)

        score = 0
        reasons: list[str] = []
        action = "Call or message the client, then log the next task in AmoCRM."

        if not tasks:
            score += 35
            reasons.append("no_open_task")
            action = "Create the next follow-up task after owner approval."
        elif _has_overdue_task(tasks, current):
            score += 30
            reasons.append("overdue_task")
            action = "Complete or reschedule the overdue follow-up today."

        if updated_age_hours is not None and updated_age_hours >= 48:
            score += 25
            reasons.append("stale_48h_plus")
        elif updated_age_hours is not None and updated_age_hours >= 24:
            score += 15
            reasons.append("stale_24h_plus")

        if not contacts:
            score += 20
            reasons.append("no_contact_attached")
            action = "Find or attach the decision-maker contact before outreach."

        if not responsible_id:
            score += 20
            reasons.append("no_responsible")

        if price >= 20_000_000:
            score += 15
            reasons.append("high_value")
        elif price > 0:
            score += 5
            reasons.append("priced")
        else:
            score += 8
            reasons.append("price_missing")

        if created_age_days is not None and created_age_days <= 1:
            score += 10
            reasons.append("fresh_lead")

        priority = "high" if score >= 55 else "medium" if score >= 30 else "low"
        evidence = {
            "source": "amocrm",
            "lead_id": lead_id,
            "status_id": status_id,
            "responsible_user_id": responsible_id or None,
            "price": price,
            "open_task_count": len(tasks),
            "contact_count": len(contacts),
            "updated_at": updated_at or None,
            "created_at": created_at or None,
            "updated_age_hours": updated_age_hours,
        }
        ranked.append(
            SalesPriorityLead(
                lead_id=lead_id,
                name=str(lead.get("name") or f"Lead #{lead_id}"),
                priority_score=score,
                priority=priority,
                action=action,
                reasons=tuple(reasons),
                evidence=evidence,
            )
        )

    ranked.sort(key=lambda item: (-item.priority_score, item.lead_id))
    selected = ranked[: max(1, min(int(limit), 50))]
    return {
        "status": "ready" if selected else "empty",
        "source": "amocrm",
        "generated_at": current.isoformat(),
        "items": [item.to_payload() for item in selected],
        "scanned_count": len(leads),
        "skipped_closed_count": skipped_closed,
        "claim_policy": "Only AmoCRM source fields are used; no invented leads or fake facts.",
    }


def build_project_delivery_risks(
    projects: list[dict[str, Any]],
    *,
    today: date | None = None,
    limit: int = 12,
) -> dict[str, Any]:
    """Rank active projects that need PM/owner attention."""
    current = today or datetime.now(timezone.utc).date()
    ranked: list[ProjectRiskItem] = []
    skipped_closed = 0

    for project in projects:
        fields = project.get("fields", project) or {}
        project_id = str(project.get("id") or _field_text(fields, "project_id") or "")
        name = _field_text(fields, "name") or "Nomsiz loyiha"
        stage = _field_text(fields, "stage") or ""
        deadline_raw = _field_text(fields, "deadline")
        manager = _field_text(fields, "manager")
        summary = _field_text(fields, "summary")

        if stage and any(marker in stage.lower() for marker in CLOSED_PROJECT_STAGE_MARKERS):
            skipped_closed += 1
            continue

        score = 0
        reasons: list[str] = []
        action = "PM statusini yangilang va keyingi deadline/owner qadamini belgilang."
        deadline_date = _parse_date(deadline_raw)
        days_until_due = None

        if deadline_date is None:
            score += 35
            reasons.append("deadline_missing")
            action = "Deadline aniqlang va loyiha kartasiga yozing."
        else:
            days_until_due = (deadline_date - current).days
            if days_until_due < 0:
                score += 50
                reasons.append("overdue")
                action = "Bugun mijozga va PMga yangi real deadline tasdiqlating."
            elif days_until_due == 0:
                score += 40
                reasons.append("due_today")
                action = "Bugun topshiriladigan deliverable va mas'ulni tasdiqlang."
            elif days_until_due <= 3:
                score += 28
                reasons.append("due_3_days")

        if not manager:
            score += 30
            reasons.append("owner_missing")
            action = "PM/mas'ul tayinlang va javobgarlikni yozib qo'ying."

        if not stage:
            score += 20
            reasons.append("stage_missing")

        if not summary:
            score += 8
            reasons.append("summary_missing")

        if score <= 0:
            continue

        risk = "critical" if score >= 70 else "high" if score >= 45 else "medium"
        evidence = {
            "source": "airtable",
            "project_id": project_id or None,
            "stage": stage or None,
            "deadline": deadline_raw,
            "days_until_due": days_until_due,
            "manager": manager,
            "has_summary": bool(summary),
        }
        ranked.append(
            ProjectRiskItem(
                project_id=project_id,
                name=name,
                risk_score=score,
                risk=risk,
                action=action,
                reasons=tuple(reasons),
                evidence=evidence,
            )
        )

    ranked.sort(key=lambda item: (-item.risk_score, item.name.lower()))
    selected = ranked[: max(1, min(int(limit), 50))]
    return {
        "status": "ready" if selected else "empty",
        "source": "airtable",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "items": [item.to_payload() for item in selected],
        "scanned_count": len(projects),
        "skipped_closed_count": skipped_closed,
        "claim_policy": "Only Airtable/project source fields are used; no invented project risks.",
    }
