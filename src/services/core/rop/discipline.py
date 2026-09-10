"""AI ROP amoCRM discipline checks. Pure; injected `now`."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from src.services.core.crm.amocrm_pipeline_config import STATUS_LOST, STATUS_WON

FINDING_TYPES = (
    "NO_NEXT_TASK", "OVERDUE_TASK", "STAGNANT", "NO_OWNER",
    "WRONG_STAGE", "IMPORTANT_NO_NOTE",
)


@dataclass(frozen=True)
class Finding:
    lead_name: str
    type: str
    detail: str


def _name(lead: dict) -> str:
    return lead.get("name") or f"Lead {lead.get('id')}"


def _day_bounds(now: datetime) -> tuple[float, float]:
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return start.timestamp(), now.timestamp()


def _note_time(note: dict) -> int:
    return int(note.get("created_at") or 0)


def find(seller_leads, tasks_by_lead, notes_by_lead, config, now) -> list[Finding]:
    stagnant_secs = int(config["discipline.stagnant_days"]) * 86400
    terminal_ids = set(config.get("discipline.terminal_stage_ids", []))
    now_epoch = now.timestamp()
    day_start, day_end = _day_bounds(now)
    out: list[Finding] = []

    for lead in seller_leads:
        lid = lead.get("id")
        name = _name(lead)
        status_id = lead.get("status_id")
        is_terminal = status_id in (STATUS_WON, STATUS_LOST)
        is_active = not is_terminal
        tasks = tasks_by_lead.get(lid, [])
        notes = notes_by_lead.get(lid, [])
        open_tasks = [t for t in tasks if not t.get("is_completed")]

        if not lead.get("responsible_user_id"):
            out.append(Finding(name, "NO_OWNER", ""))

        if is_active and not open_tasks:
            out.append(Finding(name, "NO_NEXT_TASK", ""))

        if is_active:
            for t in open_tasks:
                ct = t.get("complete_till") or 0
                if ct and float(ct) < now_epoch:
                    out.append(Finding(name, "OVERDUE_TASK", str(t.get("text") or "")))
                    break

        if is_active and (now_epoch - float(lead.get("updated_at") or now_epoch)) > stagnant_secs:
            out.append(Finding(name, "STAGNANT", ""))

        if (is_terminal and open_tasks) or (is_active and status_id in terminal_ids):
            out.append(Finding(name, "WRONG_STAGE", ""))

        for t in tasks:
            if not t.get("is_completed") or t.get("task_type_id") not in (1, 2):
                continue
            ct = float(t.get("complete_till") or 0)
            if not (day_start <= ct <= day_end):
                continue
            if not any(_note_time(n) >= ct for n in notes):
                out.append(Finding(name, "IMPORTANT_NO_NOTE", ""))
                break

    return out
