"""Dashboard API backed only by persisted call analyses."""

import json
from typing import Any, List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.api.routes.state import api_state

router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])


class CallMetric(BaseModel):
    label: str
    score: int
    status: str


class Entity(BaseModel):
    key: str
    value: str


class CallDetails(BaseModel):
    call_id: str
    lead_name: str
    summary: str
    sentiment: str
    metrics: List[CallMetric]
    entities: List[Entity]
    transcript: List[dict]
    next_steps: List[str]


def _json_list(value: Any) -> list:
    if isinstance(value, list):
        return value
    if not value:
        return []
    try:
        parsed = json.loads(str(value))
        return parsed if isinstance(parsed, list) else []
    except (TypeError, ValueError):
        return []


async def _query(sql: str, params: tuple = ()) -> list:
    if api_state.db_instance is None:
        raise HTTPException(status_code=503, detail="Database not connected")
    try:
        conn = await api_state.db_instance.get_connection()
        result = conn.execute(sql, params)
        if hasattr(result, "__await__"):
            result = await result
        fetchall = getattr(result, "fetchall", None)
        rows = fetchall() if callable(fetchall) else []
        if hasattr(rows, "__await__"):
            rows = await rows
        return list(rows or [])
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Call analytics unavailable: {type(exc).__name__}") from exc


@router.get("/call/{call_id}", response_model=CallDetails)
async def get_call_analytics(call_id: str):
    rows = await _query("SELECT * FROM call_analyses WHERE call_id = ? LIMIT 1", (call_id,))
    if not rows:
        raise HTTPException(status_code=404, detail="Call analysis not found")
    row = rows[0]
    get = row.get if isinstance(row, dict) else lambda key, default=None: getattr(row, key, default)
    scores = _json_list(get("scores"))
    transcript_raw = get("transcript", "") or ""
    transcript = _json_list(transcript_raw)
    if not transcript and transcript_raw:
        transcript = [{"speaker": "Transcript", "text": transcript_raw, "timestamp": ""}]
    metrics = [
        CallMetric(
            label=str(item.get("label") or item.get("name") or "Mezon"),
            score=int(item.get("score") or 0),
            status=str(item.get("status") or "measured"),
        )
        for item in scores
        if isinstance(item, dict)
    ]
    return CallDetails(
        call_id=str(get("call_id", call_id)),
        lead_name=str(get("client_name") or "Noma'lum mijoz"),
        summary=str(get("summary") or ""),
        sentiment=str(get("client_mood") or "unknown"),
        metrics=metrics,
        entities=[],
        transcript=transcript,
        next_steps=[str(item) for item in _json_list(get("next_steps"))],
    )


@router.get("/stats")
async def get_general_stats():
    rows = await _query(
        "SELECT COUNT(*) AS total_calls, AVG(overall_score) AS avg_score "
        "FROM call_analyses"
    )
    row = rows[0] if rows else {}
    get = row.get if isinstance(row, dict) else lambda key, default=None: getattr(row, key, default)
    return {
        "source": "real_call_analytics",
        "total_calls": int(get("total_calls") or 0),
        "avg_score": round(float(get("avg_score") or 0), 1),
    }
