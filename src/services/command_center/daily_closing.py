"""Accurate single-day sales closing collector and formatter (19:30 wrapup).

Computes strictly today's (00:00–now Asia/Tashkent) closed-won revenue, worked
sales leads, Speed-to-Lead SLA on today's new leads, uncapped active deal counts,
and overdue open tasks — with per-metric availability and zero fabricated claims.
"""
from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import requests

from src.services.command_center.daily_closing_db import (
    collect_from_db,
    collect_from_legacy_mock_bridge,
)
from src.services.core.crm.amocrm_pipeline_config import (
    ACTIVE_PIPELINE_IDS,
    HR_PIPELINE_ID,
    PARTNERSHIP_PIPELINE_ID,
    QC_PIPELINE_ID,
    STATUS_LOST,
    STATUS_WON,
)
from src.services.core.marketing.seller_metrics import (
    FIRST_TOUCH_EVENT_TYPES,
    business_minutes,
    first_touch_ts,
)
from src.time_utils import get_local_now, get_local_timezone

logger = logging.getLogger(__name__)

BOT_RESPONSIBLE_USER_ID = 13021974
_NON_SALES_PIPELINES = frozenset({HR_PIPELINE_ID, QC_PIPELINE_ID})
_CLIENT_PIPELINES = tuple(dict.fromkeys([*ACTIVE_PIPELINE_IDS, PARTNERSHIP_PIPELINE_ID]))
_WORK_EVENT_TYPES = (
    "outgoing_call",
    "outgoing_chat_message",
    "lead_status_changed",
    "common_note_added",
)

__all__ = [
    "DailyClosingSnapshot",
    "collect_from_amocrm",
    "collect_from_db",
    "collect_from_legacy_mock_bridge",
    "day_bounds_tashkent",
    "format_evening_closing_card",
    "resolve_live_amocrm",
]


@dataclass(frozen=True)
class DailyClosingSnapshot:
    """Verified single-day closing metrics; None marks an unverified metric."""

    date_label: str
    time_label: str
    won_count: int | None = None
    won_amount_uzs: float | None = None
    processed_leads_count: int | None = None
    today_new_leads_count: int | None = None
    sla_within_30m_count: int | None = None
    sla_rate_pct: float | None = None
    active_deals_count: int | None = None
    overdue_tasks_count: int | None = None
    source: str = "empty"


def day_bounds_tashkent(now: datetime | None = None) -> tuple[datetime, datetime]:
    """Return (day_start, local_now) anchored to Asia/Tashkent."""
    tz = get_local_timezone()
    raw = now or get_local_now()
    local_now = raw.astimezone(tz) if raw.tzinfo else raw.replace(tzinfo=tz)
    return local_now.replace(hour=0, minute=0, second=0, microsecond=0), local_now


def resolve_live_amocrm(explicit_amocrm: Any | None, *, allow_auto: bool) -> Any | None:
    """Resolve live amoCRM client unless disabled by test/offline flags."""
    if explicit_amocrm is not None:
        return explicit_amocrm
    if not allow_auto or os.getenv("SKIP_LIVE", "").strip() == "1":
        return None
    for loader in (_amo_from_context, _amo_from_sync):
        cand = loader()
        if cand is not None and getattr(cand, "access_token", None):
            return cand
    return None


def _amo_from_context() -> Any | None:
    try:
        from src.context import app_ctx

        return (
            getattr(app_ctx, "amocrm_instance", None)
            or getattr(app_ctx, "amocrm", None)
            or getattr(getattr(getattr(app_ctx, "msg_controller", None), "crm", None), "amocrm", None)
        )
    except (ImportError, AttributeError, RuntimeError):
        return None


def _amo_from_sync() -> Any | None:
    try:
        from src.services.core.crm.amocrm_sync import AmoCRMSync

        return AmoCRMSync()
    except (ImportError, AttributeError, RuntimeError, OSError, ValueError):
        return None


def _to_pos_int(val: Any) -> int | None:
    try:
        parsed = int(val)
        return parsed if parsed > 0 else None
    except (TypeError, ValueError):
        return None


def _is_sales_lead(lead: dict[str, Any]) -> bool:
    """Validate lead boundary shape and exclude HR/QC and synthetic fixtures."""
    if _to_pos_int(lead.get("id")) is None:
        return False
    if (_to_pos_int(lead.get("pipeline_id")) or 0) in _NON_SALES_PIPELINES:
        return False
    return "synthetic test" not in str(lead.get("name") or "").lower()


async def _amo_request_page(amocrm: Any, url: str, page_params: list[tuple[str, Any]]) -> Any:
    """Execute one amoCRM GET request off the event loop with 401 refresh."""
    req_fn = getattr(amocrm, "_request_with_auth", None)

    async def _do() -> Any:
        if callable(req_fn):
            return await req_fn(requests.get, url, params=page_params, timeout=30)
        return await asyncio.to_thread(
            requests.get, url, headers=amocrm._get_headers(), params=page_params, timeout=30
        )

    resp = await _do()
    if (
        getattr(resp, "status_code", 0) == 401
        and callable(getattr(amocrm, "refresh_token", None))
        and await asyncio.to_thread(amocrm.refresh_token)
    ):
        return await _do()
    return resp


async def _amo_get_paged(
    amocrm: Any, path: str, params: list[tuple[str, Any]], embed_key: str, *, max_pages: int = 20
) -> tuple[list[dict[str, Any]], bool]:
    """Fetch amoCRM v4 pages; return ok=False if any page fails OR remains truncated."""
    items: list[dict[str, Any]] = []
    url = f"{amocrm.base_url}{path}"
    for page in range(1, max_pages + 1):
        try:
            resp = await _amo_request_page(amocrm, url, [*params, ("page", page)])
        except Exception as exc:  # noqa: BLE001
            logger.warning("[DAILY-WRAPUP] amoCRM %s p%d failed: %s", path, page, exc)
            return items, False
        code = getattr(resp, "status_code", 0)
        if code == 204:
            return items, True
        if code != 200:
            logger.warning("[DAILY-WRAPUP] amoCRM %s p%d -> HTTP %s", path, page, code)
            return items, False
        payload = resp.json() if callable(getattr(resp, "json", None)) else {}
        if not isinstance(payload, dict):
            return items, False
        batch = payload.get("_embedded", {}).get(embed_key, [])
        items.extend(r for r in (batch if isinstance(batch, list) else []) if isinstance(r, dict))
        if not payload.get("_links", {}).get("next"):
            return items, True
    logger.warning("[DAILY-WRAPUP] amoCRM %s truncated at max_pages=%d", path, max_pages)
    return items, False


async def _resolve_sales_entity_ids(
    amocrm: Any, candidate_ids: set[int], known_leads: list[dict[str, Any]]
) -> tuple[set[int], bool]:
    """Filter event entity IDs so HR/QC recruiting or synthetic leads are excluded."""
    verdict: dict[int, bool] = {}
    for ld in known_leads:
        lid = _to_pos_int(ld.get("id"))
        if lid is not None:
            verdict[lid] = _is_sales_lead(ld)

    unknown = sorted(eid for eid in candidate_ids if eid not in verdict)
    for idx in range(0, len(unknown), 50):
        chunk = unknown[idx : idx + 50]
        params: list[tuple[str, Any]] = [("limit", 250), *[("filter[id][]", eid) for eid in chunk]]
        fetched, ok = await _amo_get_paged(amocrm, "/api/v4/leads", params, "leads", max_pages=2)
        if not ok:
            return set(), False
        for ld in fetched:
            lid = _to_pos_int(ld.get("id"))
            if lid is not None:
                verdict[lid] = _is_sales_lead(ld)
        for eid in chunk:
            verdict.setdefault(eid, False)

    return {eid for eid in candidate_ids if verdict.get(eid, False)}, True


def _compute_amo_sla(
    today_new: list[dict[str, Any]], human_events: list[dict[str, Any]]
) -> tuple[int, float | None]:
    """Compute 30-min business-hours SLA strictly from genuine human first-touch events."""
    tz = get_local_timezone()
    by_lead: dict[int, list[dict[str, Any]]] = {}
    for ev in human_events:
        eid = _to_pos_int(ev.get("entity_id"))
        if eid and ev.get("type") in FIRST_TOUCH_EVENT_TYPES and _to_pos_int(ev.get("created_at")):
            by_lead.setdefault(eid, []).append(ev)

    sla_ok = 0
    for lead in today_new:
        lid, c_ts = _to_pos_int(lead.get("id")), _to_pos_int(lead.get("created_at"))
        if not lid or not c_ts:
            continue
        touch = first_touch_ts(c_ts, by_lead.get(lid, []))
        if touch is not None:
            mins = business_minutes(datetime.fromtimestamp(c_ts, tz), datetime.fromtimestamp(touch, tz))
            sla_ok += int(mins <= 30.0)

    return (sla_ok, round(sla_ok / len(today_new) * 100.0, 1)) if today_new else (0, None)


async def _fetch_amo_leads_and_tasks(
    amocrm: Any, start_ts: int, end_ts: int
) -> tuple[int | None, float | None, set[int], int | None, int | None, list[dict[str, Any]]]:
    """Fetch closed, active, and overdue-task metrics while reconciling mid-flight closes."""
    closed_raw, ok_closed = await _amo_get_paged(
        amocrm, "/api/v4/leads",
        [("limit", 250), ("filter[closed_at][from]", start_ts), ("filter[closed_at][to]", end_ts)],
        "leads", max_pages=10,
    )
    pipe_leads, ok_act = await _amo_get_paged(
        amocrm, "/api/v4/leads",
        [("limit", 250), *[("filter[pipeline_id][]", pid) for pid in _CLIENT_PIPELINES]],
        "leads", max_pages=40,
    )
    won_by_id: dict[int, float] = {}
    closed_sales_ids: set[int] = set()
    for ld in [*closed_raw, *pipe_leads]:
        lid, c_ts = _to_pos_int(ld.get("id")), _to_pos_int(ld.get("closed_at"))
        status = _to_pos_int(ld.get("status_id"))
        if lid and _is_sales_lead(ld) and c_ts and start_ts <= c_ts <= end_ts:
            if status in (STATUS_WON, STATUS_LOST):
                closed_sales_ids.add(lid)
            if status == STATUS_WON:
                won_by_id[lid] = float(ld.get("price") or 0.0)

    won_cnt = len(won_by_id) if ok_closed else None
    won_amt = sum(won_by_id.values()) if ok_closed else None
    active_cnt = (
        sum(
            1 for ld in pipe_leads
            if _is_sales_lead(ld) and (_to_pos_int(ld.get("status_id")) or 0) not in (STATUS_WON, STATUS_LOST)
        )
        if ok_act else None
    )
    tasks, ok_tasks = await _amo_get_paged(
        amocrm, "/api/v4/tasks",
        [("limit", 250), ("filter[is_completed]", 0), ("filter[entity_type]", "leads")],
        "tasks", max_pages=20,
    )
    overdue_cnt = (
        sum(
            1 for t in tasks
            if not bool(t.get("is_completed")) and 0 < (_to_pos_int(t.get("complete_till")) or 0) < end_ts
        )
        if ok_tasks else None
    )
    return won_cnt, won_amt, closed_sales_ids, active_cnt, overdue_cnt, [*closed_raw, *pipe_leads]


async def collect_from_amocrm(
    amocrm: Any, day_start: datetime, local_now: datetime, *, extra_overdue: int | None = None
) -> DailyClosingSnapshot | None:
    """Build today's closing snapshot from live amoCRM v4 with independent metric states."""
    start_ts = int(day_start.timestamp())
    end_ts = max(start_ts, int(local_now.timestamp()))
    won_cnt, won_amt, closed_ids, active_cnt, amo_overdue, known = await _fetch_amo_leads_and_tasks(
        amocrm, start_ts, end_ts
    )
    new_raw, ok_new = await _amo_get_paged(
        amocrm, "/api/v4/leads",
        [("limit", 250), ("filter[created_at][from]", start_ts), ("filter[created_at][to]", end_ts)],
        "leads", max_pages=10,
    )
    today_new = [
        ld for ld in (new_raw if ok_new else [])
        if _is_sales_lead(ld) and start_ts <= (_to_pos_int(ld.get("created_at")) or 0) <= end_ts
    ]
    ev_params: list[tuple[str, Any]] = [
        ("limit", 100), ("filter[entity]", "lead"),
        ("filter[created_at][from]", start_ts), ("filter[created_at][to]", end_ts),
        *[(f"filter[type][{i}]", et) for i, et in enumerate(_WORK_EVENT_TYPES)],
    ]
    events, ok_ev = await _amo_get_paged(amocrm, "/api/v4/events", ev_params, "events", max_pages=25)
    if won_cnt is None and active_cnt is None and amo_overdue is None and not ok_new and not ok_ev:
        return None

    human_ev = [
        e for e in (events if ok_ev else [])
        if (_to_pos_int(e.get("created_by")) or 0) not in (0, BOT_RESPONSIBLE_USER_ID)
    ]
    worked_cnt: int | None = None
    if ok_ev:
        cand_ids = {eid for e in human_ev if (eid := _to_pos_int(e.get("entity_id")))}
        sales_ev_ids, ok_resolve = await _resolve_sales_entity_ids(
            amocrm, cand_ids, [*known, *today_new]
        )
        if ok_resolve and won_cnt is not None:
            worked_cnt = len(sales_ev_ids | closed_ids)

    new_cnt = len(today_new) if ok_new else None
    sla_ok, sla_pct = _compute_amo_sla(today_new, human_ev) if (ok_new and ok_ev) else (None, None)
    overdue_total = (amo_overdue + (extra_overdue or 0)) if amo_overdue is not None else extra_overdue

    return DailyClosingSnapshot(
        date_label=local_now.strftime("%d.%m.%Y"),
        time_label=local_now.strftime("%H:%M"),
        won_count=won_cnt,
        won_amount_uzs=won_amt,
        processed_leads_count=worked_cnt,
        today_new_leads_count=new_cnt,
        sla_within_30m_count=sla_ok,
        sla_rate_pct=sla_pct,
        active_deals_count=active_cnt,
        overdue_tasks_count=overdue_total,
        source="amocrm",
    )


def _format_uzs(amount: float) -> str:
    if amount <= 0:
        return "0 soʻm"
    if amount >= 1_000_000:
        return f"{amount / 1_000_000:.1f} mln soʻm"
    return f"{round(amount):,} soʻm"


def _format_sla_field(snap: DailyClosingSnapshot) -> str:
    if snap.today_new_leads_count is None:
        return "nomaʼlum"
    if snap.today_new_leads_count == 0:
        return "— (bugun yangi lid tushmadi)"
    if snap.sla_rate_pct is None or snap.sla_within_30m_count is None:
        return f"nomaʼlum ({snap.today_new_leads_count} ta yangi lid, javob hodisalari oʻqilmadi)"
    return f"{snap.sla_rate_pct}% ({snap.sla_within_30m_count}/{snap.today_new_leads_count} ta ≤30 daq)"


def format_evening_closing_card(snap: DailyClosingSnapshot) -> str:
    """Render honest 19:30 daily sales wrapup HTML message with per-metric states."""
    won_str = (
        f"{snap.won_count} ta ({_format_uzs(snap.won_amount_uzs)})"
        if snap.won_count is not None and snap.won_amount_uzs is not None
        else "nomaʼlum"
    )
    proc_str = f"{snap.processed_leads_count} ta" if snap.processed_leads_count is not None else "nomaʼlum"
    sla_str = _format_sla_field(snap)
    active_str = f"{snap.active_deals_count} ta" if snap.active_deals_count is not None else "nomaʼlum"
    overdue_str = f"{snap.overdue_tasks_count} ta" if snap.overdue_tasks_count is not None else "tekshirilmagan"

    if snap.source == "empty":
        footer = (
            "⚠️ Maʼlumot manbasi (amoCRM / DB) ulanmaganligi sabab "
            "kunlik koʻrsatkichlar tasdiqlanmadi."
        )
    elif snap.overdue_tasks_count is not None and snap.overdue_tasks_count > 0:
        footer = (
            f"⚠️ CRM da muddati oʻtgan {snap.overdue_tasks_count} ta ochiq vazifa bor — "
            "ularni yoping yoki yangi muddat belgilang."
        )
    elif snap.overdue_tasks_count == 0:
        footer = "✅ Muddati oʻtgan ochiq vazifalar yoʻq. Rahmat, jamoa!"
    else:
        footer = "ℹ️ Vazifalar manbasi ulanmaganligi sabab muddati oʻtgan vazifalar tekshirilmadi."

    return (
        "🌆 <b>Oisha-OS — Kunlik Savdo Sarhisobi (19:30)</b>\n"
        f"📅 <b>Davr:</b> {snap.date_label} (00:00–{snap.time_label})\n\n"
        f"🏆 <b>Kunlik Tushum / Yopilgan Bitimlar:</b> {won_str}\n"
        f"📞 <b>Qayta ishlangan lidlar (bugun):</b> {proc_str}\n"
        f"⚡ <b>Kunlik SLA foizi:</b> {sla_str}\n"
        f"🎯 <b>Faol bitimlar soni:</b> {active_str}\n"
        f"⏰ <b>Muddati oʻtgan ochiq vazifalar:</b> {overdue_str}\n\n"
        f"{footer}"
    )
