"""Accurate single-day sales closing collector and formatter (19:30 wrapup).

Computes strictly today's (00:00–now Asia/Tashkent) closed-won revenue, worked
leads, Speed-to-Lead SLA on today's new leads, uncapped active deal counts, and
real overdue open tasks — preferring live amoCRM v4 API with honest SQLite/Turso
fallbacks and zero fabricated triage claims.
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
    """Verified single-day closing metrics for the 19:30 sales summary."""

    date_label: str
    time_label: str
    won_count: int = 0
    won_amount_uzs: float = 0.0
    processed_leads_count: int = 0
    today_new_leads_count: int = 0
    sla_within_30m_count: int = 0
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
    except Exception:  # noqa: BLE001
        return None


def _amo_from_sync() -> Any | None:
    try:
        from src.services.core.crm.amocrm_sync import AmoCRMSync

        return AmoCRMSync()
    except Exception:  # noqa: BLE001
        return None


def _is_sales_lead(lead: dict[str, Any]) -> bool:
    """Exclude HR/QC pipelines and synthetic test fixtures."""
    if int(lead.get("pipeline_id") or 0) in _NON_SALES_PIPELINES:
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
    amocrm: Any, path: str, params: list[tuple[str, Any]], embed_key: str, *, max_pages: int = 10
) -> tuple[list[dict[str, Any]], bool]:
    """Fetch bounded pages from amoCRM v4 API, treating 204 as empty success."""
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
        payload = resp.json() or {}
        items.extend(r for r in payload.get("_embedded", {}).get(embed_key, []) if isinstance(r, dict))
        if not payload.get("_links", {}).get("next"):
            return items, True
    return items, True


def _compute_amo_sla_and_worked(
    today_new: list[dict[str, Any]],
    closed_today: list[dict[str, Any]],
    events: list[dict[str, Any]],
    *,
    sla_ready: bool,
) -> tuple[int, int, float | None]:
    """Compute distinct worked leads today and 30-min business-hours SLA."""
    tz = get_local_timezone()
    human_ev = [e for e in events if int(e.get("created_by") or 0) not in (0, BOT_RESPONSIBLE_USER_ID)]
    worked_ids = {int(e["entity_id"]) for e in human_ev if e.get("entity_id")}
    worked_ids.update(int(ld["id"]) for ld in closed_today if _is_sales_lead(ld) and ld.get("id"))

    by_lead: dict[int, list[dict[str, Any]]] = {}
    for ev in human_ev:
        if ev.get("type") in FIRST_TOUCH_EVENT_TYPES and ev.get("entity_id"):
            by_lead.setdefault(int(ev["entity_id"]), []).append(ev)

    sla_ok = 0
    for lead in today_new:
        lid, c_ts = int(lead.get("id") or 0), int(lead.get("created_at") or 0)
        if not c_ts:
            continue
        touch = first_touch_ts(c_ts, by_lead.get(lid, []))
        if touch is None and int(lead.get("status_id") or 0) in (STATUS_WON, STATUS_LOST):
            closed_ts = int(lead.get("closed_at") or 0)
            touch = closed_ts if closed_ts >= c_ts else None
        if touch is not None:
            mins = business_minutes(datetime.fromtimestamp(c_ts, tz), datetime.fromtimestamp(touch, tz))
            sla_ok += int(mins <= 30.0)

    if not sla_ready or not today_new:
        return len(worked_ids), sla_ok, None
    return len(worked_ids), sla_ok, round(sla_ok / len(today_new) * 100.0, 1)


async def _fetch_amo_active_and_overdue(amocrm: Any, end_ts: int) -> tuple[int | None, int | None]:
    """Fetch uncapped active deal count and overdue open task count from amoCRM."""
    pipe_leads, ok_act = await _amo_get_paged(
        amocrm,
        "/api/v4/leads",
        [("limit", 250), *[("filter[pipeline_id][]", pid) for pid in _CLIENT_PIPELINES]],
        "leads",
        max_pages=20,
    )
    active_cnt = (
        sum(
            1
            for ld in pipe_leads
            if _is_sales_lead(ld) and int(ld.get("status_id") or 0) not in (STATUS_WON, STATUS_LOST)
        )
        if ok_act
        else None
    )
    tasks, ok_tasks = await _amo_get_paged(
        amocrm,
        "/api/v4/tasks",
        [("limit", 250), ("filter[is_completed]", 0), ("filter[entity_type]", "leads")],
        "tasks",
        max_pages=8,
    )
    overdue_cnt = (
        sum(1 for t in tasks if 0 < int(t.get("complete_till") or 0) < end_ts) if ok_tasks else None
    )
    return active_cnt, overdue_cnt


async def collect_from_amocrm(
    amocrm: Any, day_start: datetime, local_now: datetime
) -> DailyClosingSnapshot | None:
    """Build today's closing snapshot from live amoCRM v4 endpoints."""
    start_ts, end_ts = int(day_start.timestamp()), max(int(day_start.timestamp()), int(local_now.timestamp()))
    closed_raw, ok_closed = await _amo_get_paged(
        amocrm, "/api/v4/leads",
        [("limit", 250), ("filter[closed_at][from]", start_ts), ("filter[closed_at][to]", end_ts)],
        "leads", max_pages=6,
    )
    if not ok_closed:
        return None

    won = [
        ld for ld in closed_raw
        if _is_sales_lead(ld) and int(ld.get("status_id") or 0) == STATUS_WON
        and start_ts <= int(ld.get("closed_at") or 0) <= end_ts
    ]
    new_raw, ok_new = await _amo_get_paged(
        amocrm, "/api/v4/leads",
        [("limit", 250), ("filter[created_at][from]", start_ts), ("filter[created_at][to]", end_ts)],
        "leads", max_pages=6,
    )
    today_new = [
        ld for ld in (new_raw if ok_new else [])
        if _is_sales_lead(ld) and start_ts <= int(ld.get("created_at") or 0) <= end_ts
    ]
    ev_params = [
        ("limit", 100), ("filter[entity]", "lead"),
        ("filter[created_at][from]", start_ts), ("filter[created_at][to]", end_ts),
        *[(f"filter[type][{i}]", et) for i, et in enumerate(_WORK_EVENT_TYPES)],
    ]
    events, ok_ev = await _amo_get_paged(amocrm, "/api/v4/events", ev_params, "events", max_pages=10)
    worked_cnt, sla_ok, sla_pct = _compute_amo_sla_and_worked(
        today_new, closed_raw, events if ok_ev else [], sla_ready=(ok_new and ok_ev)
    )
    active_cnt, overdue_cnt = await _fetch_amo_active_and_overdue(amocrm, end_ts)

    return DailyClosingSnapshot(
        date_label=local_now.strftime("%d.%m.%Y"),
        time_label=local_now.strftime("%H:%M"),
        won_count=len(won),
        won_amount_uzs=sum(float(ld.get("price") or 0.0) for ld in won),
        processed_leads_count=worked_cnt,
        today_new_leads_count=len(today_new),
        sla_within_30m_count=sla_ok,
        sla_rate_pct=sla_pct,
        active_deals_count=active_cnt,
        overdue_tasks_count=overdue_cnt,
        source="amocrm",
    )


def _format_uzs(amount: float) -> str:
    if amount <= 0:
        return "0 soʻm"
    if amount >= 1_000_000:
        return f"{amount / 1_000_000:.1f} mln soʻm"
    return f"{round(amount):,} soʻm"


def format_evening_closing_card(snap: DailyClosingSnapshot) -> str:
    """Render honest 19:30 daily sales wrapup HTML message."""
    if snap.source == "empty":
        won_str, proc_str, sla_str = "nomaʼlum", "nomaʼlum", "nomaʼlum"
        footer = (
            "⚠️ Maʼlumot manbasi (amoCRM / DB) ulanmaganligi sabab "
            "kunlik koʻrsatkichlar tasdiqlanmadi."
        )
    else:
        won_str = f"{snap.won_count} ta ({_format_uzs(snap.won_amount_uzs)})"
        proc_str = f"{snap.processed_leads_count} ta"
        sla_str = (
            "— (bugun yangi lid tushmadi)"
            if snap.today_new_leads_count == 0 or snap.sla_rate_pct is None
            else f"{snap.sla_rate_pct}% ({snap.sla_within_30m_count}/{snap.today_new_leads_count} ta ≤30 daq)"
        )
        if snap.overdue_tasks_count is not None and snap.overdue_tasks_count > 0:
            footer = (
                f"⚠️ amoCRM da muddati oʻtgan {snap.overdue_tasks_count} ta ochiq vazifa bor — "
                "ularni yoping yoki yangi muddat belgilang."
            )
        elif snap.overdue_tasks_count == 0:
            footer = "✅ Muddati oʻtgan ochiq vazifalar yoʻq. Rahmat, jamoa!"
        else:
            footer = "ℹ️ Vazifalar manbasi ulanmaganligi sabab muddati oʻtgan vazifalar tekshirilmadi."

    active_str = f"{snap.active_deals_count} ta" if snap.active_deals_count is not None else "nomaʼlum"
    overdue_str = f"{snap.overdue_tasks_count} ta" if snap.overdue_tasks_count is not None else "tekshirilmagan"

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
