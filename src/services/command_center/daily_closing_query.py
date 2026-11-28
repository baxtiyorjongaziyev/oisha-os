"""Low-level checked SQL/timestamp helpers for daily closing DB queries."""
from __future__ import annotations

import logging
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from src.services.core.crm.amocrm_pipeline_config import (
    ACTIVE_PIPELINE_IDS,
    HR_PIPELINE_ID,
    PARTNERSHIP_PIPELINE_ID,
    QC_PIPELINE_ID,
)
from src.services.utils.db_rows import fetch_rows
from src.time_utils import get_local_timezone

logger = logging.getLogger(__name__)
_SALES_PIPES = (
    *ACTIVE_PIPELINE_IDS[:4],
    PARTNERSHIP_PIPELINE_ID,
)


def parse_mixed_ts(raw: Any, *, naive_tz: Any = UTC) -> datetime | None:
    """Parse ISO or space-separated SQLite timestamp into UTC-aware datetime."""
    text = str(raw or "").strip()
    if not text:
        return None
    try:
        dt = datetime.fromisoformat(text)
    except (ValueError, TypeError, OverflowError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=naive_tz)
    return dt.astimezone(UTC)


async def query_table_rows(
    bridge: Any, sql: str, params: tuple[Any, ...] = (), *, local_path: str | None = None
) -> tuple[list[dict[str, Any]], bool]:
    """Query remote conn first, then local SQLite; distinguish empty table vs missing."""
    conn = bridge._resolve_conn()
    if conn is not None:
        res, ok = await _query_conn_checked(conn, sql, params)
        if ok:
            return res, True
    target = local_path or bridge.dialer_db_path
    if bridge.use_local_files and target and Path(target).exists():
        try:
            with sqlite3.connect(target) as sconn:
                sconn.row_factory = sqlite3.Row
                rows = [dict(r) for r in sconn.execute(sql, params).fetchall()]
            return rows, True
        except (sqlite3.Error, OSError):
            return [], False
    return [], False


async def _query_conn_checked(
    conn: Any, sql: str, params: tuple[Any, ...]
) -> tuple[list[dict[str, Any]], bool]:
    """Execute SQL on remote/mock conn, returning (rows, True) on valid empty result."""
    try:
        return await fetch_rows(conn, sql, params or None), True
    except (TypeError, ValueError, KeyError, RuntimeError, sqlite3.Error, OSError) as exc:
        logger.debug("fetch_rows fallback in _query_conn_checked: %s", exc)
    exec_fn = getattr(conn, "execute", None)
    if not callable(exec_fn):
        return [], False
    try:
        cur = exec_fn(sql, params) if params else exec_fn(sql)
        if hasattr(cur, "__await__"):
            cur = await cur
        raw = cur.fetchall() if hasattr(cur, "fetchall") else []
        if hasattr(raw, "__await__"):
            raw = await raw
        desc = [c[0] for c in (getattr(cur, "description", None) or [])]
        out = [dict(r) if isinstance(r, dict) else dict(zip(desc, r, strict=False)) for r in (raw or [])]
        return out, True
    except (TypeError, ValueError, KeyError, RuntimeError, sqlite3.Error, OSError) as exc:
        logger.debug("cursor execute failed in _query_conn_checked: %s", exc)
        return [], False


async def load_non_sales_lead_ids(bridge: Any) -> set[str]:
    """Return lead IDs in HR/QC or synthetic test rows when dialer_leads exists."""
    q = (
        "SELECT CAST(id AS TEXT) AS lid FROM dialer_leads "
        "WHERE pipeline_id IN (?, ?) OR LOWER(COALESCE(name, '')) LIKE 'synthetic test%'"
    )
    rows, ok = await query_table_rows(
        bridge, q, (HR_PIPELINE_ID, QC_PIPELINE_ID), local_path=bridge.dialer_db_path
    )
    if ok:
        return {str(r.get("lid") or "") for r in rows if r.get("lid")}
    q_no_pipe = (
        "SELECT CAST(id AS TEXT) AS lid FROM dialer_leads "
        "WHERE LOWER(COALESCE(name, '')) LIKE 'synthetic test%'"
    )
    rows2, _ = await query_table_rows(bridge, q_no_pipe, local_path=bridge.dialer_db_path)
    return {str(r.get("lid") or "") for r in rows2 if r.get("lid")}


async def fetch_overdue_tasks_from_db(bridge: Any, now_utc: datetime) -> int | None:
    """Count open tasks whose normalized deadline is earlier than now_utc."""
    local_tz = get_local_timezone()
    q = "SELECT due_at FROM crm_tasks WHERE COALESCE(is_completed, 0) = 0"
    rows, ok = await query_table_rows(bridge, q, local_path=bridge.dialer_db_path)
    if not ok:
        return None
    return sum(
        1
        for r in rows
        if (due_dt := parse_mixed_ts(r.get("due_at"), naive_tz=local_tz)) is not None
        and due_dt < now_utc
    )


async def fetch_active_deals_from_db(bridge: Any) -> int | None:
    """Return uncapped count of open sales deals across dialer_leads or crm_active_deals."""
    q_scoped = (
        "SELECT COUNT(*) AS cnt FROM dialer_leads WHERE is_active = 1 "
        "AND COALESCE(pipeline_id, 11162698) IN (?, ?, ?, ?, ?) "
        "AND status_slug NOT IN ('won', 'lost', 'closed', 'sotuv', 'rad', 'yopilgan') "
        "AND LOWER(COALESCE(name, '')) NOT LIKE 'synthetic test%'"
    )
    q_legacy = (
        "SELECT COUNT(*) AS cnt FROM dialer_leads WHERE is_active = 1 "
        "AND status_slug NOT IN ('won', 'lost', 'closed', 'sotuv', 'rad', 'yopilgan') "
        "AND LOWER(COALESCE(name, '')) NOT LIKE 'synthetic test%'"
    )
    q_act = "SELECT COUNT(*) AS cnt FROM crm_active_deals WHERE status = 'open'"

    rows, ok = await query_table_rows(bridge, q_scoped, _SALES_PIPES, local_path=bridge.dialer_db_path)
    if not ok:
        rows, ok = await query_table_rows(bridge, q_legacy, local_path=bridge.dialer_db_path)
    dialer_cnt = int(rows[0].get("cnt") or 0) if ok and rows else None
    if dialer_cnt:
        return dialer_cnt
    a_rows, ok_act = await query_table_rows(bridge, q_act, local_path=bridge.dialer_db_path)
    act_cnt = int(a_rows[0].get("cnt") or 0) if ok_act and a_rows else None
    return act_cnt if (act_cnt is not None and act_cnt > 0) else (dialer_cnt if dialer_cnt is not None else act_cnt)
