"""
AmoCRM period metrics aggregation logic.
"""
from __future__ import annotations

import time
from typing import Any, Dict, List

from src.services.core.crm.daily_report.models import (
    ManagerRow,
    PeriodMetrics,
)


def call_answered(call: Dict[str, Any]) -> bool:
    """Best-effort: AmoCRM call note counted answered if it has duration > 0."""
    params = call.get("params") or {}
    duration = params.get("duration") or call.get("duration") or 0
    try:
        return float(duration) > 0
    except (TypeError, ValueError):
        return False


def aggregate_period_metrics(
    won_status: Any,
    lost_status: Any,
    ptype: Any,
    start: Any,
    end: Any,
    *,
    leads_all: List[Dict],
    leads_created: List[Dict],
    leads_closed: List[Dict],
    contacts_new: List[Dict],
    companies_new: List[Dict],
    calls: List[Dict],
    tasks_all: List[Dict],
    tasks_created: List[Dict],
    tasks_done: List[Dict],
    user_names: Dict[int, str],
) -> PeriodMetrics:
    now = time.time()
    won_s, lost_s = won_status, lost_status

    m = PeriodMetrics(period_type=ptype, period_start=start, period_end=end)
    m.new_leads = len(leads_created)
    m.new_contacts = len(contacts_new)
    m.new_companies = len(companies_new)
    m.incoming_calls = len(calls)
    m.tasks_created = len(tasks_created)
    m.tasks_completed = len(tasks_done)
    m.calls_total = len(calls)
    m.calls_answered = sum(1 for c in calls if call_answered(c))

    open_lead_ids = set()
    for l in leads_all:
        sid = l.get("status_id")
        price = l.get("price") or 0
        if sid in (won_s, lost_s):
            continue
        m.active_count += 1
        m.active_amount += price
        open_lead_ids.add(l.get("id"))
        if (now - (l.get("updated_at") or 0)) > 3 * 86400:
            m.stagnated_count += 1
    m.pipeline_value = m.active_amount

    mgr = {}
    for l in leads_closed:
        sid = l.get("status_id")
        price = l.get("price") or 0
        uid = l.get("responsible_user_id")
        if sid == won_s:
            m.won_count += 1
            m.won_amount += price
            if uid:
                row = mgr.setdefault(uid, ManagerRow(user_id=uid, name=user_names.get(uid, f"Manager #{uid}")))
                row.won_count += 1
                row.won_amount += price
        elif sid == lost_s:
            m.lost_count += 1
            m.lost_amount += price

    for c in calls:
        uid = c.get("created_by") or c.get("responsible_user_id")
        if not uid:
            continue
        row = mgr.setdefault(uid, ManagerRow(user_id=uid, name=user_names.get(uid, f"Manager #{uid}")))
        row.calls_count += 1
        if call_answered(c):
            row.calls_answered += 1

    leads_with_task = {
        t.get("entity_id")
        for t in tasks_all
        if t.get("entity_type") == "leads" and not t.get("is_completed")
    }
    for t in tasks_all:
        if t.get("is_completed"):
            continue
        m.tasks_open += 1
        till = t.get("complete_till") or 0
        overdue = bool(till) and till < now
        if overdue:
            m.tasks_overdue += 1
        uid = t.get("responsible_user_id")
        if uid:
            row = mgr.setdefault(uid, ManagerRow(user_id=uid, name=user_names.get(uid, f"Manager #{uid}")))
            row.open_tasks += 1
            if overdue:
                row.overdue_tasks += 1

    m.leads_without_task = len(open_lead_ids - leads_with_task)
    m.managers = sorted(mgr.values(), key=lambda r: r.won_amount, reverse=True)[:5]
    m.call_managers = sorted(
        [r for r in mgr.values() if r.calls_count], key=lambda r: r.calls_count, reverse=True
    )
    m.recompute_derived()
    return m
