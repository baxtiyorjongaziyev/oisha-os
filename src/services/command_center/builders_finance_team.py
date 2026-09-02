"""
Finance risk and team capacity snapshot builders for Command Center.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any
from src.services.command_center.models import (
    FinanceRiskItem,
    TeamCapacityItem,
    CLOSED_PROJECT_STAGE_MARKERS,
    _field_text,
    _int_or_zero,
    _money_value,
    _parse_date,
)

def build_finance_project_risks(
    projects: list[dict[str, Any]],
    *,
    limit: int = 12,
) -> dict[str, Any]:
    """Rank project payment risks without inventing missing finance numbers."""
    ranked: list[FinanceRiskItem] = []
    skipped_closed = 0

    for project in projects:
        fields = project.get("fields", project) or {}
        project_id = str(project.get("id") or fields.get("id") or _field_text(fields, "project_id") or "")
        name = _field_text(fields, "name") or str(fields.get("title") or "Nomsiz loyiha")
        stage = _field_text(fields, "stage") or str(fields.get("stage") or "")
        if stage and any(marker in stage.lower() for marker in CLOSED_PROJECT_STAGE_MARKERS):
            skipped_closed += 1
            continue

        budget = _money_value(_field_text(fields, "budget") or fields.get("budget"))
        paid = _money_value(_field_text(fields, "paid") or fields.get("paid_amount"))
        remaining_raw = _money_value(_field_text(fields, "remaining") or fields.get("remaining"))
        remaining = remaining_raw
        if remaining is None and budget is not None and paid is not None:
            remaining = max(0, budget - paid)
        payment_status = (_field_text(fields, "payment_status") or "").lower()

        score = 0
        reasons: list[str] = []
        action = "To'lov holatini manba kartada yangilang va keyingi pul qadamini belgilang."

        if budget is None or budget <= 0:
            score += 35
            reasons.append("price_missing")
            action = "Loyiha narxini aniqlang va source kartaga yozing."

        if paid is None:
            score += 30
            reasons.append("paid_amount_missing")
            action = "To'langan summani Hisobchi/Airtable bilan tasdiqlang."
        elif budget and paid < budget * 0.5:
            score += 35
            reasons.append("advance_below_50")
            action = "50% avans talabini tekshiring va mijoz bilan to'lovni yoping."

        if remaining and remaining > 0:
            score += 20
            reasons.append("remaining_payment")

        if payment_status and any(word in payment_status for word in ("qarz", "debt", "overdue", "kechik")):
            score += 30
            reasons.append("payment_overdue")
            action = "Qarzdorlik bo'yicha bugun eslatma va aniq to'lov sanasini oling."

        if not payment_status:
            score += 8
            reasons.append("payment_status_missing")

        if score <= 0:
            continue

        risk = "critical" if score >= 70 else "high" if score >= 45 else "medium"
        evidence = {
            "source": "project_finance",
            "project_id": project_id or None,
            "stage": stage or None,
            "budget": budget,
            "paid_amount": paid,
            "remaining_amount": remaining,
            "payment_status": payment_status or None,
            "margin": None,
            "margin_policy": "Margin is not calculated unless real cost source is available.",
        }
        ranked.append(
            FinanceRiskItem(
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
        "source": "project_finance",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "items": [item.to_payload() for item in selected],
        "scanned_count": len(projects),
        "skipped_closed_count": skipped_closed,
        "claim_policy": "Only project finance source fields are used; margin is not guessed.",
    }


def build_team_capacity_snapshot(
    projects: list[dict[str, Any]],
    *,
    employee_names: dict[int, str] | None = None,
    today: date | None = None,
    limit: int = 12,
) -> dict[str, Any]:
    """Summarize team workload from active project assignments."""
    current = today or datetime.now(timezone.utc).date()
    names = employee_names or {}
    owners: dict[str, dict[str, Any]] = {}
    unassigned_count = 0
    skipped_closed = 0

    for project in projects:
        fields = project.get("fields", project) or {}
        stage = _field_text(fields, "stage") or str(fields.get("stage") or "")
        if stage and any(marker in stage.lower() for marker in CLOSED_PROJECT_STAGE_MARKERS):
            skipped_closed += 1
            continue

        owner_name = _field_text(fields, "manager")
        assigned_to = _int_or_zero(fields.get("assigned_to"))
        if not owner_name and assigned_to:
            owner_name = names.get(assigned_to) or f"employee:{assigned_to}"
        owner_key = owner_name.strip().lower() if owner_name else "unassigned"
        if owner_key == "unassigned":
            unassigned_count += 1
            owner_name = "PM tayinlanmagan"

        deadline_date = _parse_date(_field_text(fields, "deadline") or fields.get("deadline"))
        days_until_due = (deadline_date - current).days if deadline_date else None
        row = owners.setdefault(
            owner_key,
            {
                "owner_name": owner_name,
                "active_projects": 0,
                "overdue_projects": 0,
                "due_3_days": 0,
                "missing_deadline": 0,
                "missing_stage": 0,
                "project_ids": [],
            },
        )
        row["active_projects"] += 1
        project_id = str(project.get("id") or fields.get("id") or fields.get("project_id") or "")
        if project_id:
            row["project_ids"].append(project_id)
        if days_until_due is None:
            row["missing_deadline"] += 1
        elif days_until_due < 0:
            row["overdue_projects"] += 1
        elif days_until_due <= 3:
            row["due_3_days"] += 1
        if not stage:
            row["missing_stage"] += 1

    items: list[TeamCapacityItem] = []
    for owner_key, row in owners.items():
        score = (
            row["active_projects"] * 12
            + row["overdue_projects"] * 25
            + row["due_3_days"] * 15
            + row["missing_deadline"] * 8
            + row["missing_stage"] * 5
        )
        reasons: list[str] = []
        if owner_key == "unassigned":
            score += 30
            reasons.append("unassigned_projects")
        if row["active_projects"] >= 5:
            reasons.append("high_project_count")
        if row["overdue_projects"]:
            reasons.append("overdue_projects")
        if row["due_3_days"]:
            reasons.append("due_3_days")
        if row["missing_deadline"]:
            reasons.append("missing_deadline")
        if row["missing_stage"]:
            reasons.append("missing_stage")

        load = "overloaded" if score >= 70 else "busy" if score >= 35 else "normal"
        action = (
            "PM tayinlang va egasiz loyihalarni jamoaga taqsimlang."
            if owner_key == "unassigned"
            else "Deadline va deliverablelarni tekshirib, ortiqcha yukni qayta taqsimlang."
            if load == "overloaded"
            else "Bugungi ustuvor deliverablelarni tasdiqlang."
        )
        evidence = {
            "source": "project_assignments",
            "active_projects": row["active_projects"],
            "overdue_projects": row["overdue_projects"],
            "due_3_days": row["due_3_days"],
            "missing_deadline": row["missing_deadline"],
            "missing_stage": row["missing_stage"],
            "project_ids": row["project_ids"][:10],
        }
        items.append(
            TeamCapacityItem(
                owner_key=owner_key,
                owner_name=row["owner_name"],
                load_score=score,
                load=load,
                action=action,
                reasons=tuple(reasons),
                evidence=evidence,
            )
        )

    items.sort(key=lambda item: (-item.load_score, item.owner_name.lower()))
    selected = items[: max(1, min(int(limit), 50))]
    return {
        "status": "ready" if selected else "empty",
        "source": "project_assignments",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "items": [item.to_payload() for item in selected],
        "scanned_count": len(projects),
        "skipped_closed_count": skipped_closed,
        "unassigned_project_count": unassigned_count,
        "claim_policy": "Only project assignment fields are used; team capacity is not guessed.",
    }
