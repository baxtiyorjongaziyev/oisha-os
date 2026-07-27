"""Sales quality analytics routes."""
from __future__ import annotations

import hmac
import json
import logging
import os
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field

from src.api.rbac import Permission, Principal, Role, require_permissions, scope_owned_rows
from src.api.routes.state import api_state
from src.time_utils import get_local_now

router = APIRouter(tags=["sales-quality"])
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
    if isinstance(row, dict):
        return row
    try:
        return {col: getattr(row, col, None) for col in columns}
    except Exception:
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
            return list(rows or [])
        return []
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


@router.get("/api/sales-quality/overview")
async def get_sales_quality_overview(
    principal: Principal = require_permissions(Permission.DASHBOARD_READ),
):
    try:
        rows = await _fetch_call_analysis_rows()
    except Exception as exc:
        logger.error("[SALES QUALITY] Real data read failed: %s", exc)
        return JSONResponse(
            status_code=503,
            content=_build_empty_sales_quality(
                get_local_now().isoformat(),
                f"Real call analytics o'qishda xato: {type(exc).__name__}",
            ),
        )
    return _build_sales_quality_payload(rows, principal=principal)


class SalesQualityAnalysisRequest(BaseModel):
    secret_key: str
    call_id: str
    lead_id: Optional[int] = None
    manager_id: Optional[int] = None
    manager_name: str = ""
    client_name: Optional[str] = None
    duration_seconds: int = 0
    overall_score: int
    category: Optional[str] = None
    scores: List[Dict[str, Any]] = Field(default_factory=list)
    summary: str = ""
    strengths: List[str] = Field(default_factory=list)
    weaknesses: List[str] = Field(default_factory=list)
    client_mood: str = "neutral"
    client_interest_level: int = 0
    objections_raised: List[str] = Field(default_factory=list)
    outcome: str = "unknown"
    next_steps: List[str] = Field(default_factory=list)
    recommended_tasks: List[Dict[str, Any]] = Field(default_factory=list)
    transcript: str = ""
    audio_url: Optional[str] = None
    source: str = "external"
    analyzed_at: Optional[str] = None


@router.post(
    "/api/sales-quality/ingest-analysis",
    dependencies=[require_permissions(Permission.CALL_WRITE)],
)
async def ingest_sales_quality_analysis(data: SalesQualityAnalysisRequest):
    expected_secret = os.environ.get("OISHA_API_SECRET")
    if not expected_secret or not hmac.compare_digest(data.secret_key, expected_secret):
        return JSONResponse(status_code=401, content={"status": "error", "message": "Unauthorized"})
    if not api_state.db_instance:
        return JSONResponse(status_code=503, content={"status": "error", "message": "Database not connected"})

    score = max(0, min(int(data.overall_score), 100))
    now = get_local_now().isoformat()
    analyzed_at = data.analyzed_at or now
    category = data.category or (
        "excellent" if score >= 90 else "good" if score >= 80 else "average" if score >= 60 else "poor"
    )

    conn = await api_state.db_instance.get_connection()
    result = conn.execute(
        """
        INSERT OR REPLACE INTO call_analyses (
            call_id, lead_id, manager_id, manager_name, client_name,
            duration_seconds, overall_score, category, scores, summary,
            strengths, weaknesses, client_mood, client_interest_level,
            objections, outcome, next_steps, recommended_tasks,
            transcript, audio_url, source, analyzed_at, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            data.call_id, data.lead_id, data.manager_id, data.manager_name,
            data.client_name, max(int(data.duration_seconds or 0), 0), score,
            category, json.dumps(data.scores, ensure_ascii=False), data.summary,
            json.dumps(data.strengths, ensure_ascii=False),
            json.dumps(data.weaknesses, ensure_ascii=False),
            data.client_mood, max(0, min(int(data.client_interest_level or 0), 100)),
            json.dumps(data.objections_raised, ensure_ascii=False), data.outcome,
            json.dumps(data.next_steps, ensure_ascii=False),
            json.dumps(data.recommended_tasks, ensure_ascii=False),
            data.transcript, data.audio_url, data.source, analyzed_at, now,
        ),
    )
    if hasattr(result, "__await__"):
        await result
    commit = getattr(conn, "commit", None)
    if callable(commit):
        committed = commit()
        if hasattr(committed, "__await__"):
            await committed

    return {"status": "ok", "call_id": data.call_id, "source": "real_call_analytics"}


@router.get(
    "/dashboard/sales-quality",
    dependencies=[require_permissions(Permission.DASHBOARD_READ)],
)
async def sales_quality_dashboard_html():
    """Serve a minimal HTML dashboard for sales quality."""
    html = """<!DOCTYPE html><html><head><title>Sales Quality</title></head>
    <body><h1>Sales Quality Dashboard</h1><p>Loading...</p></body></html>"""
    return HTMLResponse(content=html)
