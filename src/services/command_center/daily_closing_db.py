"""SQLite/Turso single-day fallback collectors for the 19:30 sales wrapup."""
from __future__ import annotations

import inspect
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from src.services.command_center.live_db_parsers import safe_parse_dt
from src.services.core.marketing.seller_metrics import business_minutes

if TYPE_CHECKING:
    from src.services.command_center.daily_closing import DailyClosingSnapshot


async def _db_won_today(
    bridge: Any, start_utc: datetime, end_utc: datetime
) -> tuple[set[str], float, bool]:
    """Query today's closed-won deals across dialer_leads and lead_attribution."""
    start_sql = start_utc.strftime("%Y-%m-%d %H:%M:%S")
    start_date = start_utc.strftime("%Y-%m-%d")
    won_by_id: dict[str, float] = {}
    saw = False

    q_dialer = (
        "SELECT CAST(id AS TEXT) AS lead_id, COALESCE(price, 0) AS price, updated_at "
        "FROM dialer_leads WHERE status_slug IN ('won', 'sotuv') "
        "AND updated_at >= ? AND LOWER(COALESCE(name, '')) NOT LIKE 'synthetic test%'"
    )
    d_rows = await bridge._execute_on_conn(q_dialer, (start_sql,))
    if d_rows is None:
        d_rows = bridge._query_local_sqlite(bridge.dialer_db_path, q_dialer, (start_sql,))
    for row in d_rows or []:
        saw = True
        r = dict(row) if not isinstance(row, dict) else row
        dt = safe_parse_dt(str(r.get("updated_at") or ""), None)
        if dt and start_utc <= dt <= end_utc:
            won_by_id[str(r.get("lead_id") or "")] = float(r.get("price") or 0.0)

    q_attr = (
        "SELECT COALESCE(CAST(lead_id AS TEXT), leadgen_id) AS lead_id, "
        "COALESCE(lead_price, 0) AS price, created_at FROM lead_attribution "
        "WHERE (lead_won = 1 OR status_id = 142) AND date(created_at) >= date(?)"
    )
    a_rows = await bridge._execute_on_conn(q_attr, (start_date,))
    if a_rows is None:
        a_rows = bridge._query_local_sqlite(bridge.attribution_db_path, q_attr, (start_date,))
    for row in a_rows or []:
        saw = True
        r = dict(row) if not isinstance(row, dict) else row
        dt = safe_parse_dt(str(r.get("created_at") or ""), None)
        lid = str(r.get("lead_id") or "")
        if lid and dt and start_utc <= dt <= end_utc and lid not in won_by_id:
            won_by_id[lid] = float(r.get("price") or 0.0)

    return set(won_by_id.keys()), sum(won_by_id.values()), saw


async def _db_today_activity_and_sla(
    bridge: Any, start_utc: datetime, end_utc: datetime, won_ids: set[str]
) -> tuple[int, int, int, float | None, bool]:
    """Compute today's worked leads and genuine SLA from call_events and chat messages."""
    worked: set[str] = {f"lead_{lid}" for lid in won_ids if lid}
    inbound_sla: list[tuple[datetime, datetime | None]] = []
    saw = bool(won_ids)

    q_calls = (
        "SELECT call_id, lead_id, direction, answered, duration_seconds, "
        "COALESCE(occurred_at, created_at) AS ts FROM call_events "
        "WHERE COALESCE(occurred_at, created_at) >= ?"
    )
    for row in await bridge._execute_on_conn(q_calls, (start_utc.isoformat(),)) or []:
        if not isinstance(row, dict):
            continue
        saw = True
        dt = safe_parse_dt(str(row.get("ts") or ""), None)
        if not dt or not (start_utc <= dt <= end_utc):
            continue
        is_ans = int(row.get("answered") or 0) == 1 or int(row.get("duration_seconds") or 0) > 0
        if is_ans:
            worked.add(f"lead_{row['lead_id']}" if row.get("lead_id") else f"call_{row.get('call_id')}")
        if str(row.get("direction") or "") == "call_in":
            inbound_sla.append((dt, dt if is_ans else None))

    q_chats = (
        "SELECT t.id AS thread_id, t.lead_id, t.created_at, "
        "MIN(CASE WHEN m.direction = 'in' THEN m.created_at END) AS first_in_at, "
        "MIN(CASE WHEN m.direction = 'out' THEN m.created_at END) AS first_out_at "
        "FROM crm_chat_threads t LEFT JOIN crm_chat_messages m ON m.thread_id = t.id "
        "WHERE COALESCE(t.updated_at, t.created_at) >= ? "
        "AND LOWER(COALESCE(t.contact_name, '')) NOT LIKE 'synthetic test%' GROUP BY t.id"
    )
    start_sql = start_utc.strftime("%Y-%m-%d %H:%M:%S")
    for row in bridge._query_local_sqlite(bridge.dialer_db_path, q_chats, (start_sql,)):
        saw = True
        in_dt = safe_parse_dt(str(row.get("first_in_at") or row.get("created_at") or ""), None)
        out_dt = safe_parse_dt(str(row.get("first_out_at") or ""), None)
        if out_dt and start_utc <= out_dt <= end_utc:
            worked.add(f"lead_{row['lead_id']}" if row.get("lead_id") else f"chat_{row.get('thread_id')}")
        if in_dt and start_utc <= in_dt <= end_utc:
            inbound_sla.append((in_dt, out_dt if (out_dt and out_dt >= in_dt) else None))

    sla_ok = sum(
        1 for c_dt, r_dt in inbound_sla if r_dt is not None and business_minutes(c_dt, r_dt) <= 30.0
    )
    total = len(inbound_sla)
    return len(worked), total, sla_ok, (round(sla_ok / total * 100.0, 1) if total else None), saw


async def collect_from_db(
    bridge: Any, day_start: datetime, local_now: datetime
) -> DailyClosingSnapshot:
    """Fallback single-day closing snapshot from SQLite/Turso tables without row caps."""
    from src.services.command_center.daily_closing import DailyClosingSnapshot

    start_utc, end_utc = day_start.astimezone(UTC), local_now.astimezone(UTC)
    won_ids, won_amount, saw_won = await _db_won_today(bridge, start_utc, end_utc)
    worked, total_new, sla_ok, sla_pct, saw_act = await _db_today_activity_and_sla(
        bridge, start_utc, end_utc, won_ids
    )
    active_cnt = await bridge.fetch_active_deals_count()
    overdue_cnt = await bridge.fetch_overdue_tasks_count(now_utc=end_utc)
    has_src = saw_won or saw_act or active_cnt is not None or overdue_cnt is not None

    return DailyClosingSnapshot(
        date_label=local_now.strftime("%d.%m.%Y"),
        time_label=local_now.strftime("%H:%M"),
        won_count=len(won_ids),
        won_amount_uzs=won_amount,
        processed_leads_count=worked,
        today_new_leads_count=total_new,
        sla_within_30m_count=sla_ok,
        sla_rate_pct=sla_pct,
        active_deals_count=active_cnt,
        overdue_tasks_count=overdue_cnt,
        source="db" if has_src else "empty",
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
        if start_utc <= (i.created_at if i.created_at.tzinfo else i.created_at.replace(tzinfo=UTC)) <= end_utc
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
