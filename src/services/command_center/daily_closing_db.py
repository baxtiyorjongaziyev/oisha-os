"""SQLite/Turso single-day fallback collectors for the 19:30 sales wrapup."""
from __future__ import annotations

import inspect
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from src.services.command_center.daily_closing_query import (
    fetch_active_deals_from_db,
    fetch_overdue_tasks_from_db,
    load_non_sales_lead_ids,
    parse_mixed_ts,
    query_table_rows,
)
from src.services.command_center.live_db_parsers import safe_parse_dt
from src.services.core.marketing.seller_metrics import business_minutes

if TYPE_CHECKING:
    from src.services.command_center.daily_closing import DailyClosingSnapshot

__all__ = [
    "collect_from_db",
    "collect_from_legacy_mock_bridge",
    "fetch_active_deals_from_db",
    "fetch_overdue_tasks_from_db",
]


async def _db_won_today(
    bridge: Any, start_utc: datetime, end_utc: datetime, excluded_ids: set[str]
) -> tuple[int | None, float | None, set[str]]:
    """Count deals with a verified transition to won inside [start_utc, end_utc]."""
    min_date = (start_utc - timedelta(days=1)).strftime("%Y-%m-%d")
    won_by_id: dict[str, float] = {}
    verified = False

    q_logs = (
        "SELECT CAST(l.lead_id AS TEXT) AS lid, l.created_at AS ts, COALESCE(d.price, 0) AS price "
        "FROM dialer_call_logs l JOIN dialer_leads d ON d.id = l.lead_id "
        "WHERE l.new_status IN ('won', 'sotuv') AND COALESCE(l.old_status, '') NOT IN ('won', 'sotuv') "
        "AND d.status_slug IN ('won', 'sotuv') AND SUBSTR(TRIM(COALESCE(l.created_at, '')), 1, 10) >= ?"
    )
    l_rows, ok_logs = await query_table_rows(bridge, q_logs, (min_date,), local_path=bridge.dialer_db_path)
    if ok_logs:
        verified = True
        for r in l_rows:
            lid, dt = str(r.get("lid") or ""), parse_mixed_ts(r.get("ts"))
            if lid and lid not in excluded_ids and dt and start_utc <= dt <= end_utc:
                won_by_id[lid] = float(r.get("price") or 0.0)

    q_col = (
        "SELECT CAST(id AS TEXT) AS lid, closed_at AS ts, COALESCE(price, 0) AS price "
        "FROM dialer_leads WHERE status_slug IN ('won', 'sotuv') AND closed_at IS NOT NULL "
        "AND SUBSTR(TRIM(CAST(closed_at AS TEXT)), 1, 10) >= ?"
    )
    c_rows, ok_col = await query_table_rows(bridge, q_col, (min_date,), local_path=bridge.dialer_db_path)
    if ok_col:
        verified = True
        for r in c_rows:
            lid, dt = str(r.get("lid") or ""), parse_mixed_ts(r.get("ts"))
            if lid and lid not in excluded_ids and dt and start_utc <= dt <= end_utc:
                won_by_id[lid] = float(r.get("price") or 0.0)

    if not verified:
        return None, None, set()
    return len(won_by_id), sum(won_by_id.values()), set(won_by_id.keys())


async def _add_call_and_log_activity(
    bridge: Any, start_utc: datetime, end_utc: datetime, excluded: set[str], worked: set[str]
) -> tuple[bool, dict[str, list[datetime]]]:
    """Add answered calls and seller call-log entries within today's window."""
    min_date = (start_utc - timedelta(days=1)).strftime("%Y-%m-%d")
    callbacks: dict[str, list[datetime]] = {}
    q_calls = (
        "SELECT call_id, CAST(lead_id AS TEXT) AS lid, answered, duration_seconds, "
        "COALESCE(occurred_at, created_at) AS ts FROM call_events "
        "WHERE SUBSTR(TRIM(COALESCE(occurred_at, created_at, '')), 1, 10) >= ?"
    )
    c_rows, ok_c = await query_table_rows(bridge, q_calls, (min_date,), local_path=bridge.dialer_db_path)
    for r in c_rows:
        lid = str(r.get("lid") or "").strip()
        dt = parse_mixed_ts(r.get("ts"))
        is_ans = int(r.get("answered") or 0) == 1 or int(r.get("duration_seconds") or 0) > 0
        if (not lid or lid not in excluded) and dt and is_ans and start_utc <= dt <= end_utc:
            worked.add(f"lead_{lid}" if lid else f"call_{r.get('call_id')}")
            if lid:
                callbacks.setdefault(lid, []).append(dt)

    q_logs = "SELECT CAST(lead_id AS TEXT) AS lid, created_at AS ts FROM dialer_call_logs WHERE SUBSTR(TRIM(COALESCE(created_at, '')), 1, 10) >= ?"
    l_rows, ok_l = await query_table_rows(bridge, q_logs, (min_date,), local_path=bridge.dialer_db_path)
    for r in l_rows:
        lid, dt = str(r.get("lid") or "").strip(), parse_mixed_ts(r.get("ts"))
        if lid and lid not in excluded and dt and start_utc <= dt <= end_utc:
            worked.add(f"lead_{lid}")
    return (ok_c or ok_l), callbacks


async def _collect_db_worked_and_callbacks(
    bridge: Any, start_utc: datetime, end_utc: datetime, excluded_ids: set[str], won_ids: set[str]
) -> tuple[int | None, dict[str, list[datetime]]]:
    """Gather today's worked leads across calls, logs, and outbound chat replies."""
    min_date = (start_utc - timedelta(days=1)).strftime("%Y-%m-%d")
    worked: set[str] = {f"lead_{lid}" for lid in won_ids if lid not in excluded_ids}
    ok_cl, callbacks = await _add_call_and_log_activity(bridge, start_utc, end_utc, excluded_ids, worked)

    q_out = (
        "SELECT t.id AS tid, CAST(t.lead_id AS TEXT) AS lid, m.created_at AS ts "
        "FROM crm_chat_messages m JOIN crm_chat_threads t ON t.id = m.thread_id "
        "WHERE m.direction = 'out' AND LOWER(COALESCE(t.contact_name, '')) NOT LIKE 'synthetic test%' "
        "AND SUBSTR(TRIM(COALESCE(m.created_at, '')), 1, 10) >= ?"
    )
    m_rows, ok_m = await query_table_rows(bridge, q_out, (min_date,), local_path=bridge.dialer_db_path)
    for r in m_rows:
        lid, dt = str(r.get("lid") or "").strip(), parse_mixed_ts(r.get("ts"))
        if (not lid or lid not in excluded_ids) and dt and start_utc <= dt <= end_utc:
            worked.add(f"lead_{lid}" if lid else f"chat_{r.get('tid')}")

    saw = bool(won_ids) or ok_cl or ok_m
    return (len(worked) if saw else None), callbacks


async def _add_thread_cohort(
    bridge: Any,
    start_utc: datetime,
    end_utc: datetime,
    excluded: set[str],
    callbacks: dict[str, list[datetime]],
    cohort: dict[str, tuple[datetime, datetime | None]],
) -> bool:
    """Populate SLA cohort from new inbound chat threads created today."""
    min_date = (start_utc - timedelta(days=1)).strftime("%Y-%m-%d")
    q_threads = (
        "SELECT t.id AS tid, CAST(t.lead_id AS TEXT) AS lid, t.created_at AS t_created, "
        "MIN(CASE WHEN m.direction = 'in' THEN m.created_at END) AS first_in_at, "
        "(SELECT MIN(m2.created_at) FROM crm_chat_messages m2 WHERE m2.thread_id = t.id "
        " AND m2.direction = 'out' AND m2.created_at >= "
        " COALESCE((SELECT MIN(m3.created_at) FROM crm_chat_messages m3 "
        "           WHERE m3.thread_id = t.id AND m3.direction = 'in'), t.created_at)) AS reply_at "
        "FROM crm_chat_threads t LEFT JOIN crm_chat_messages m ON m.thread_id = t.id "
        "WHERE LOWER(COALESCE(t.contact_name, '')) NOT LIKE 'synthetic test%' "
        "AND SUBSTR(TRIM(COALESCE(t.created_at, '')), 1, 10) >= ? GROUP BY t.id"
    )
    rows, ok = await query_table_rows(bridge, q_threads, (min_date,), local_path=bridge.dialer_db_path)
    for r in rows:
        lid = str(r.get("lid") or "").strip()
        t_dt, in_dt = parse_mixed_ts(r.get("t_created")), parse_mixed_ts(r.get("first_in_at"))
        if (lid and lid in excluded) or not t_dt or not in_dt:
            continue
        if not (start_utc <= t_dt <= end_utc and start_utc <= in_dt <= end_utc):
            continue
        cands = [d for d in [parse_mixed_ts(r.get("reply_at")), *callbacks.get(lid, [])] if d and d >= in_dt]
        key = f"lead_{lid}" if lid else f"chat_{r.get('tid')}"
        if key not in cohort or in_dt < cohort[key][0]:
            cohort[key] = (in_dt, min(cands) if cands else None)
    return ok


async def _collect_db_new_lead_sla(
    bridge: Any,
    start_utc: datetime,
    end_utc: datetime,
    excluded_ids: set[str],
    callbacks_by_lead: dict[str, list[datetime]],
) -> tuple[int | None, int | None, float | None]:
    """Compute SLA strictly over distinct new inbound leads/threads created today."""
    cohort: dict[str, tuple[datetime, datetime | None]] = {}
    ok_t = await _add_thread_cohort(bridge, start_utc, end_utc, excluded_ids, callbacks_by_lead, cohort)

    start_ts, end_ts = int(start_utc.timestamp()), int(end_utc.timestamp())
    q_attr = (
        "SELECT COALESCE(CAST(lead_id AS TEXT), leadgen_id) AS lid, lead_created_ts, first_touch_ts "
        "FROM lead_attribution WHERE lead_created_ts >= ? AND lead_created_ts <= ?"
    )
    a_rows, ok_a = await query_table_rows(
        bridge, q_attr, (start_ts, end_ts), local_path=bridge.attribution_db_path
    )
    for r in a_rows:
        lid = str(r.get("lid") or "").strip()
        if not lid or lid in excluded_ids or f"lead_{lid}" in cohort:
            continue
        c_dt = datetime.fromtimestamp(int(r["lead_created_ts"]), UTC)
        ft = int(r.get("first_touch_ts") or 0)
        cohort[f"lead_{lid}"] = (c_dt, datetime.fromtimestamp(ft, UTC) if ft >= int(r["lead_created_ts"]) else None)

    if not (ok_t or ok_a):
        return None, None, None
    total = len(cohort)
    if total == 0:
        return 0, 0, None
    sla_ok = sum(1 for c_dt, r_dt in cohort.values() if r_dt is not None and business_minutes(c_dt, r_dt) <= 30.0)
    return total, sla_ok, round(sla_ok / total * 100.0, 1)


async def collect_from_db(
    bridge: Any, day_start: datetime, local_now: datetime
) -> DailyClosingSnapshot:
    """Fallback single-day closing snapshot with strict per-metric availability."""
    from src.services.command_center.daily_closing import DailyClosingSnapshot

    start_utc, end_utc = day_start.astimezone(UTC), local_now.astimezone(UTC)
    excluded = await load_non_sales_lead_ids(bridge)
    won_cnt, won_amt, won_ids = await _db_won_today(bridge, start_utc, end_utc, excluded)
    worked_cnt, callbacks = await _collect_db_worked_and_callbacks(
        bridge, start_utc, end_utc, excluded, won_ids
    )
    total_new, sla_ok, sla_pct = await _collect_db_new_lead_sla(
        bridge, start_utc, end_utc, excluded, callbacks
    )
    active_cnt = await bridge.fetch_active_deals_count()
    overdue_cnt = await bridge.fetch_overdue_tasks_count(now_utc=end_utc)
    has_any = any(x is not None for x in (won_cnt, worked_cnt, total_new, active_cnt, overdue_cnt))

    return DailyClosingSnapshot(
        date_label=local_now.strftime("%d.%m.%Y"),
        time_label=local_now.strftime("%H:%M"),
        won_count=won_cnt,
        won_amount_uzs=won_amt,
        processed_leads_count=worked_cnt,
        today_new_leads_count=total_new,
        sla_within_30m_count=sla_ok,
        sla_rate_pct=sla_pct,
        active_deals_count=active_cnt,
        overdue_tasks_count=overdue_cnt,
        source="db" if has_any else "empty",
    )


async def collect_from_legacy_mock_bridge(
    bridge: Any, now: datetime | None = None
) -> DailyClosingSnapshot:
    """Support unit-test mock bridges that stub legacy LiveDataBridge methods."""
    from src.services.command_center.daily_closing import (
        DailyClosingSnapshot,
        day_bounds_tashkent,
    )

    day_start, local_now = day_bounds_tashkent(now)
    start_utc, end_utc = day_start.astimezone(UTC), local_now.astimezone(UTC)
    interactions = await bridge.fetch_recent_lead_interactions()
    today_items = [
        i
        for i in interactions
        if start_utc <= (safe_parse_dt(i.created_at.isoformat(), None) or start_utc) <= end_utc
    ] or list(interactions)
    answered = [i for i in today_items if i.first_response_at is not None]
    sla_ok = sum(
        1 for i in answered if ((i.first_response_at - i.created_at).total_seconds() / 60.0) <= 30.0
    )
    total_new = len(today_items)
    cnt_fn = getattr(bridge, "fetch_active_deals_count", None)
    active_cnt = (
        await cnt_fn()
        if inspect.iscoroutinefunction(cnt_fn)
        else len(await bridge.fetch_active_deal_records())
    )
    ov_fn = getattr(bridge, "fetch_overdue_tasks_count", None)
    overdue_cnt = await ov_fn() if inspect.iscoroutinefunction(ov_fn) else None
    _, ad_leads = await bridge.fetch_ad_attribution_data()
    won_leads = [ld for ld in ad_leads if getattr(ld, "status", "") == "won"]

    return DailyClosingSnapshot(
        date_label=local_now.strftime("%d.%m.%Y"),
        time_label=local_now.strftime("%H:%M"),
        won_count=len(won_leads),
        won_amount_uzs=sum(float(getattr(ld, "won_amount", 0.0) or 0.0) for ld in won_leads),
        processed_leads_count=len(answered),
        today_new_leads_count=total_new,
        sla_within_30m_count=sla_ok,
        sla_rate_pct=round(sla_ok / total_new * 100.0, 1) if total_new else None,
        active_deals_count=active_cnt,
        overdue_tasks_count=overdue_cnt,
        source="bridge_mock",
    )
