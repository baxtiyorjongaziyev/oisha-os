"""
Sales quality payload builders and DB fetch helpers.
"""
from __future__ import annotations

import json
import logging
from collections import defaultdict
from typing import Any, Dict, Mapping, Optional

from src.api.rbac import Principal, Role, scope_owned_rows
from src.api.routes.state import api_state
from src.time_utils import get_local_now

logger = logging.getLogger(__name__)


def _safe_json_list(value: Any) -> list:
    if not value:
        return []
    if isinstance(value, list):
        return value
    try:
        parsed = json.loads(str(value))
        return parsed if isinstance(parsed, list) else []
    except (TypeError, ValueError):
        return []


def _row_to_dict(row: Any, columns: list) -> dict:
    if row is None:
        return {}
    if isinstance(row, Mapping):
        return dict(row)
    try:
        return {col: getattr(row, col, None) for col in columns}
    except Exception:
        logger.error("Exception handled in %s", __name__, exc_info=True)
        return {}


def _score_to_risk(score: int) -> str:
    if score >= 80:
        return "past"
    if score >= 60:
        return "o'rtacha"
    return "yuqori"


def _format_duration(seconds: int) -> str:
    if not seconds or seconds <= 0:
        return "0:00"
    mins = seconds // 60
    secs = seconds % 60
    return f"{mins}:{secs:02d}"


def _avatar(name: str) -> str:
    if not name:
        return "??"
    parts = name.strip().split()
    if len(parts) >= 2:
        return (parts[0][0] + parts[1][0]).upper()
    return name[:2].upper()


def _build_empty_sales_quality(timestamp: str, reason: str = "") -> dict:
    return {
        "timestamp": timestamp,
        "source": "real_call_analytics",
        "real_data": False,
        "overview": {"total_calls": 0, "average_score": 0},
        "team": {"calls_total": 0, "quality_score": 0},
        "managers": [],
        "calls": [],
        "reason": reason,
    }


async def _fetch_call_analysis_rows() -> list:
    if not api_state.db_instance:
        raise RuntimeError("database_not_connected")
    try:
        conn = await api_state.db_instance.get_connection()
        result = conn.execute(
            "SELECT * FROM call_analyses ORDER BY created_at DESC LIMIT 200"
        )
        if hasattr(result, "__await__"):
            result = await result
        rows_method = getattr(result, "fetchall", None)
        if callable(rows_method):
            rows = rows_method()
            if hasattr(rows, "__await__"):
                rows = await rows
            combined = list(rows or [])
        else:
            combined = []
        try:
            telegram_result = conn.execute(
                """
                SELECT
                    'telegram-' || id AS call_id,
                    manager_id,
                    '' AS manager_name,
                    NULL AS client_name,
                    0 AS duration_seconds,
                    overall_score,
                    CASE
                        WHEN overall_score >= 90 THEN 'excellent'
                        WHEN overall_score >= 80 THEN 'good'
                        WHEN overall_score >= 60 THEN 'average'
                        ELSE 'poor'
                    END AS category,
                    'Telegram SalesCoach: ' || status AS summary,
                    '[]' AS strengths,
                    '[]' AS weaknesses,
                    '' AS client_mood,
                    0 AS client_interest_level,
                    status AS outcome,
                    '[]' AS next_steps,
                    updated_at AS analyzed_at
                FROM conversation_analyses
                ORDER BY updated_at DESC
                LIMIT 200
                """
            )
            if hasattr(telegram_result, "__await__"):
                telegram_result = await telegram_result
            telegram_rows = telegram_result.fetchall()
            if hasattr(telegram_rows, "__await__"):
                telegram_rows = await telegram_rows
            combined.extend(list(telegram_rows or []))
        except Exception as exc:
            if "no such table" not in str(exc).lower():
                raise
        return combined
    except Exception as exc:
        logger.error("[SALES QUALITY] DB read failed: %s", exc)
        raise


def _build_sales_quality_payload(
    rows: list,
    *,
    principal: Optional[Principal] = None,
) -> dict:
    now = get_local_now().isoformat()
    if not rows:
        return _build_empty_sales_quality(now)

    columns = [
        "call_id", "manager_id", "manager_name", "client_name",
        "duration_seconds", "overall_score", "category", "summary",
        "strengths", "weaknesses", "client_mood", "client_interest_level",
        "outcome", "next_steps", "analyzed_at",
    ]
    records = [_row_to_dict(r, columns) for r in rows]
    if principal and principal.role is Role.SELLER:
        records = list(
            scope_owned_rows(principal, records, owner_field="manager_id")
        )

    total = len(records)
    avg_score = sum(r.get("overall_score", 0) for r in records) / max(total, 1)

    by_manager: Dict[str, list] = defaultdict(list)
    for r in records:
        key = r.get("manager_name") or f"Manager-{r.get('manager_id', '?')}"
        by_manager[key].append(r)

    managers = []
    for name, mgr_records in by_manager.items():
        scores = [r.get("overall_score", 0) for r in mgr_records]
        m_avg = sum(scores) / max(len(scores), 1)
        managers.append({
            "name": name,
            "avatar": _avatar(name),
            "total_calls": len(mgr_records),
            "average_score": m_avg,
            "risk_level": _score_to_risk(int(m_avg)),
        })
    managers.sort(key=lambda m: m["average_score"], reverse=True)

    calls = []
    for r in records:
        call = {
            "id": r.get("call_id"),
            "call_id": r.get("call_id"),
            "client": r.get("client_name"),
            "manager": r.get("manager_name"),
            "score": r.get("overall_score", 0),
            "duration": _format_duration(r.get("duration_seconds", 0)),
            "outcome": r.get("outcome", ""),
            "result": r.get("outcome", ""),
            "category": r.get("category", ""),
            "summary": r.get("summary", ""),
            "analyzed_at": r.get("analyzed_at", ""),
        }
        if principal and principal.role is Role.VIEWER:
            call.pop("client", None)
            call.pop("summary", None)
        calls.append(call)

    return {
        "timestamp": now,
        "source": "real_call_analytics",
        "real_data": True,
        "overview": {
            "total_calls": total,
            "average_score": round(avg_score, 1),
        },
        "team": {
            "calls_total": total,
            "quality_score": round(avg_score, 1),
        },
        "managers": managers,
        "calls": calls,
    }
