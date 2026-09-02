"""
Data collection and command planning functions for Business Command Center.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
from datetime import datetime, timezone
from typing import Any

from src.services.command_center.models import (
    CommandPlan,
    _PHONE_RE,
    _LEAD_ID_RE,
    _TIME_RE,
    _int_or_zero,
)

logger = logging.getLogger(__name__)
from src.services.command_center.builders import (
    build_finance_project_risks,
    build_project_delivery_risks,
    build_sales_today_priorities,
    build_team_capacity_snapshot,
)

async def collect_sales_today_priorities(
    amocrm: Any,
    *,
    limit: int = 12,
) -> dict[str, Any]:
    """Read AmoCRM and return seller priorities, or a truthful unavailable state."""
    if amocrm is None or not hasattr(amocrm, "get_leads_detailed"):
        return {
            "status": "source_unavailable",
            "source": "amocrm",
            "items": [],
            "reason": "amocrm_client_unavailable",
            "claim_policy": "No fake priorities are generated without live CRM access.",
        }

    try:
        leads = await amocrm.get_leads_detailed(limit=min(max(limit * 3, 20), 50))
    except Exception as exc:
        logger.error("Exception handled in %s", __name__, exc_info=True)
        return {
            "status": "source_unavailable",
            "source": "amocrm",
            "items": [],
            "reason": type(exc).__name__,
            "claim_policy": "No fake priorities are generated when AmoCRM read fails.",
        }

    if not leads and getattr(amocrm, "last_error", None):
        return {
            "status": "source_unavailable",
            "source": "amocrm",
            "items": [],
            "reason": getattr(amocrm, "last_error", "amocrm_empty_or_error"),
            "claim_policy": "No fake priorities are generated when AmoCRM has no evidence.",
        }

    open_tasks_by_lead = {}
    if hasattr(amocrm, "get_lead_open_tasks"):
        for lead in leads[: min(len(leads), 25)]:
            lead_id = lead.get("id")
            if not lead_id:
                continue
            try:
                open_tasks_by_lead[int(lead_id)] = await amocrm.get_lead_open_tasks(int(lead_id))
            except Exception:
                logger.error("Exception handled in %s", __name__, exc_info=True)
                open_tasks_by_lead[int(lead_id)] = []

    return build_sales_today_priorities(
        leads,
        open_tasks_by_lead=open_tasks_by_lead,
        limit=limit,
    )


async def collect_project_delivery_risks(
    airtable: Any,
    *,
    limit: int = 12,
) -> dict[str, Any]:
    """Read Airtable projects and return truthful project/deadline risks."""
    if airtable is None or not hasattr(airtable, "get_projects"):
        return {
            "status": "source_unavailable",
            "source": "airtable",
            "items": [],
            "reason": "airtable_client_unavailable",
            "claim_policy": "No fake project risks are generated without live project access.",
        }
    try:
        import asyncio

        projects = await asyncio.to_thread(airtable.get_projects)
    except Exception as exc:
        logger.error("Exception handled in %s", __name__, exc_info=True)
        return {
            "status": "source_unavailable",
            "source": "airtable",
            "items": [],
            "reason": type(exc).__name__,
            "claim_policy": "No fake project risks are generated when Airtable read fails.",
        }
    return build_project_delivery_risks(projects or [], limit=limit)


async def collect_finance_project_risks(
    source: Any,
    *,
    limit: int = 12,
) -> dict[str, Any]:
    """Read project finance source and return truthful payment risks."""
    if source is None:
        return {
            "status": "source_unavailable",
            "source": "project_finance",
            "items": [],
            "reason": "finance_source_unavailable",
            "claim_policy": "No fake finance risks are generated without project finance access.",
        }
    try:
        if hasattr(source, "get_projects"):
            import asyncio

            projects = await asyncio.to_thread(source.get_projects)
        elif hasattr(source, "get_active_projects"):
            projects = await source.get_active_projects()
        else:
            return {
                "status": "source_unavailable",
                "source": "project_finance",
                "items": [],
                "reason": "unsupported_finance_source",
                "claim_policy": "No fake finance risks are generated without project finance access.",
            }
    except Exception as exc:
        logger.error("Exception handled in %s", __name__, exc_info=True)
        return {
            "status": "source_unavailable",
            "source": "project_finance",
            "items": [],
            "reason": type(exc).__name__,
            "claim_policy": "No fake finance risks are generated when finance read fails.",
        }
    return build_finance_project_risks(projects or [], limit=limit)


async def collect_team_capacity_snapshot(
    project_source: Any,
    *,
    hr_source: Any = None,
    limit: int = 12,
) -> dict[str, Any]:
    """Read project assignments and return a truthful team capacity snapshot."""
    if project_source is None:
        return {
            "status": "source_unavailable",
            "source": "project_assignments",
            "items": [],
            "reason": "project_source_unavailable",
            "claim_policy": "No fake team capacity is generated without project assignments.",
        }
    try:
        if hasattr(project_source, "get_projects"):
            import asyncio

            projects = await asyncio.to_thread(project_source.get_projects)
        elif hasattr(project_source, "get_active_projects"):
            projects = await project_source.get_active_projects()
        else:
            return {
                "status": "source_unavailable",
                "source": "project_assignments",
                "items": [],
                "reason": "unsupported_project_source",
                "claim_policy": "No fake team capacity is generated without project assignments.",
            }
    except Exception as exc:
        logger.error("Exception handled in %s", __name__, exc_info=True)
        return {
            "status": "source_unavailable",
            "source": "project_assignments",
            "items": [],
            "reason": type(exc).__name__,
            "claim_policy": "No fake team capacity is generated when project read fails.",
        }

    employee_names: dict[int, str] = {}
    if hr_source is not None and hasattr(hr_source, "get_all_employees"):
        try:
            for employee in await hr_source.get_all_employees():
                employee_id = _int_or_zero(employee.get("id"))
                if employee_id:
                    employee_names[employee_id] = str(employee.get("name") or employee_id)
        except Exception:
            logger.error("Exception handled in %s", __name__, exc_info=True)
            employee_names = {}
    return build_team_capacity_snapshot(
        projects or [],
        employee_names=employee_names,
        limit=limit,
    )


async def collect_business_command_snapshot(
    *,
    amocrm: Any = None,
    project_source: Any = None,
    finance_source: Any = None,
    hr_source: Any = None,
    limit: int = 5,
) -> dict[str, Any]:
    """Collect the owner-facing command center snapshot from live sources."""
    sales = await collect_sales_today_priorities(amocrm, limit=limit)
    projects = await collect_project_delivery_risks(project_source, limit=limit)
    finance = await collect_finance_project_risks(
        finance_source or project_source,
        limit=limit,
    )
    team = await collect_team_capacity_snapshot(
        project_source,
        hr_source=hr_source,
        limit=limit,
    )
    sections = {
        "sales": sales,
        "projects": projects,
        "finance": finance,
        "team": team,
    }
    ready_sections = sum(1 for section in sections.values() if section.get("status") == "ready")
    unavailable_sections = [
        key
        for key, section in sections.items()
        if section.get("status") == "source_unavailable"
    ]
    total_items = sum(len(section.get("items") or []) for section in sections.values())
    if unavailable_sections:
        status = "partial"
    elif total_items:
        status = "attention_required"
    else:
        status = "clear"
    return {
        "status": status,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sections": sections,
        "summary": {
            "ready_sections": ready_sections,
            "total_sections": len(sections),
            "attention_items": total_items,
            "unavailable_sections": unavailable_sections,
        },
        "claim_policy": "Each section keeps its live-source status; missing sources are not filled with guesses.",
    }

def plan_business_command(command: str, *, actor_id: str = "owner") -> CommandPlan:
    """Classify an Uzbek business command into a safe, auditable plan."""
    normalized = " ".join(command.strip().lower().split())
    if not normalized:
        raise ValueError("command must not be empty")

    entities: dict[str, Any] = {"actor_id": actor_id}
    phone = _PHONE_RE.search(normalized)
    lead_id = _LEAD_ID_RE.search(normalized)
    time_match = _TIME_RE.search(normalized)
    if phone:
        value = phone.group(0)
        entities["phone"] = value if value.startswith("+") else f"+{value}"
    if lead_id:
        entities["lead_id"] = int(lead_id.group(1))
    if time_match and ("soat" in normalized or ":" in time_match.group(0)):
        entities["time"] = f"{int(time_match.group(1)):02d}:{int(time_match.group(2) or 0):02d}"

    if any(word in normalized for word in ("lead yarat", "lid yarat", "bitim yarat")):
        intent, mutation, confidence = "create_lead", True, 0.96
        sources, action = ("amocrm",), "approval_then_create_amocrm_lead"
    elif any(word in normalized for word in ("eslat", "vazifa yarat", "task yarat")):
        intent, mutation, confidence = "create_reminder", True, 0.94
        sources = ("amocrm", "telegram_bot")
        action = "approval_then_create_task_or_reminder"
    elif any(word in normalized for word in ("brief", "brif", "kp", "taklif")):
        intent, mutation, confidence = "client_document_workflow", True, 0.93
        sources = ("amocrm", "google_workspace")
        action = "approval_then_prepare_brief_or_proposal"
    elif any(
        word in normalized
        for word in ("loyiha holati", "deadline", "muddat", "qaysi bosqich")
    ):
        intent, mutation, confidence = "project_status_query", False, 0.95
        sources = ("airtable", "amocrm")
        action = "read_live_project_status_with_deadline"
    elif any(word in normalized for word in ("avans", "to'lov", "qarzdor", "debitor")):
        intent, mutation, confidence = "payment_status_query", False, 0.93
        sources = ("finance", "amocrm")
        action = "read_live_payment_status_with_evidence"
    elif any(word in normalized for word in ("jamoa yuklama", "bandlik", "capacity")):
        intent, mutation, confidence = "team_capacity_query", False, 0.91
        sources = ("airtable", "projects")
        action = "read_live_team_capacity_with_projects"
    elif any(word in normalized for word in ("hisobot", "kpi", "savdo", "daromad")):
        intent, mutation, confidence = "agency_analytics_query", False, 0.88
        sources, action = ("amocrm", "finance"), "read_live_metrics_with_evidence"
    else:
        intent, mutation, confidence = "clarification_required", False, 0.35
        sources, action = (), "ask_one_clarifying_question"

    digest = hashlib.sha256(f"{actor_id}:{normalized}".encode()).hexdigest()[:20]
    return CommandPlan(
        intent=intent,
        mutation=mutation,
        approval_required=mutation,
        confidence=confidence,
        entities=entities,
        required_sources=sources,
        next_action=action,
        idempotency_key=digest,
    )
