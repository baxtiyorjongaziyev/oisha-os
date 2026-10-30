"""Gong/NICE-inspired review and intelligence interfaces with explicit row ownership."""
import asyncio
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from src.api.rbac import (
    Permission, Principal, Role, owns_resource, require_any_permission, scope_owned_rows,
)
from src.services.call_analytics.scorecards import TYPES, scorecard
from src.services.sales_quality.helpers import _fetch_call_analysis_rows
from src.services.sales_quality.intelligence import account_intelligence
from src.services.sales_quality.reviews import QualityReviews, ReviewConflict

router = APIRouter(tags=["conversation-intelligence"])
READ = require_any_permission(Permission.TRANSCRIPT_READ_ALL, Permission.TRANSCRIPT_READ_OWN)


class ReviewRequest(BaseModel):
    revision: str = Field(min_length=64, max_length=64)
    decision: Literal["approved", "rejected", "appealed"]
    reason: str = Field(min_length=1, max_length=2000)
    corrected_score: float | None = Field(default=None, ge=0, le=100, allow_inf_nan=False)


def _visible(principal, rows):
    return list(scope_owned_rows(principal, rows, owner_field="manager_id"))


@router.get("/api/sales-quality/scorecards")
async def get_scorecards(principal: Principal = READ):
    return {"policy": "pilot", "scorecards": [scorecard(key) for key in TYPES], "payroll_enabled": False}


@router.get("/api/sales-quality/evaluations")
async def get_evaluations(principal: Principal = READ):
    try:
        store = await asyncio.to_thread(QualityReviews)
        rows = await asyncio.to_thread(store.list)
        return {"evaluations": _visible(principal, rows),
                "can_review": principal.role in {Role.OWNER, Role.ADMIN}, "payroll_enabled": False}
    except Exception:
        raise HTTPException(503, "quality_store_unavailable") from None


@router.post("/api/sales-quality/evaluations/{call_id}/review")
async def review_evaluation(call_id: str, data: ReviewRequest, principal: Principal = READ):
    reviewer = principal.role in {Role.OWNER, Role.ADMIN}
    if not reviewer and (data.decision != "appealed" or data.corrected_score is not None):
        raise HTTPException(403, "reviewer_permission_required")
    store = await asyncio.to_thread(QualityReviews)
    row = await asyncio.to_thread(store.get, call_id)
    if not row or not owns_resource(principal, row, owner_field="manager_id"):
        raise HTTPException(404, "evaluation_not_found")
    try:
        return await asyncio.to_thread(store.review, call_id, data.revision, principal.subject,
                                       data.decision, data.reason, data.corrected_score)
    except ReviewConflict:
        raise HTTPException(409, "evaluation_changed_reload") from None
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None


@router.get("/api/sales-quality/intelligence")
async def get_intelligence(principal: Principal = READ):
    try:
        records = await _fetch_call_analysis_rows()
        # The canonical reader returns dictionaries; never expose unscoped transcripts.
        rows = _visible(principal, [dict(row) for row in records])
        store = await asyncio.to_thread(QualityReviews)
        evaluations = _visible(principal, await asyncio.to_thread(store.list))
        return account_intelligence(rows, evaluations)
    except Exception:
        raise HTTPException(503, "intelligence_sources_unavailable") from None


@router.get("/dashboard/conversation-intelligence", response_class=HTMLResponse)
async def intelligence_dashboard(principal: Principal = READ):
    path = Path(__file__).resolve().parents[2] / "api/templates/conversation_intelligence.html"
    return HTMLResponse(await asyncio.to_thread(path.read_text, encoding="utf-8"))
