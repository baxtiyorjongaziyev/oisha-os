"""Restricted KPI pilot preview using human-reviewed quality snapshots."""
import asyncio

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from src.api.rbac import Permission, Principal, Role, require_permissions
from src.services.sales_quality.kpi_pilot import POLICY, quality_component, simulate_kpi
from src.services.sales_quality.reviews import QualityReviews

router = APIRouter(tags=["sales-kpi-pilot"])
ACCESS = require_permissions(Permission.CALL_READ_ALL, Permission.FINANCE_READ)


class PilotInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    manager_id: str = Field(min_length=1, max_length=100)
    review_window_start: int = Field(ge=0)
    review_window_end: int = Field(gt=0)
    actual: float | None = Field(None, ge=0, allow_inf_nan=False)
    target: float | None = Field(None, gt=0, allow_inf_nan=False)
    completed_on_time: int | None = Field(None, ge=0)
    tasks_due: int | None = Field(None, ge=0)
    bonus_pool: float | None = Field(None, ge=0, allow_inf_nan=False)
    currency: str | None = None


@router.get("/api/sales-quality/kpi-policy")
async def policy(principal: Principal = ACCESS):
    return POLICY


@router.post("/api/sales-quality/kpi-simulation")
async def simulation(data: PilotInput, principal: Principal = ACCESS):
    if principal.role not in {Role.OWNER, Role.ADMIN}:
        raise HTTPException(403, "owner_or_admin_required")
    if data.review_window_end <= data.review_window_start:
        raise HTTPException(422, "invalid_review_window")
    store = await asyncio.to_thread(QualityReviews)
    rows = await asyncio.to_thread(store.manager_window, data.manager_id,
                                   data.review_window_start, data.review_window_end)
    quality = quality_component(rows, data.manager_id, data.review_window_start, data.review_window_end,
                                POLICY["minimum_reviewed_calls"])
    try:
        result = simulate_kpi(actual=data.actual, target=data.target, completed_on_time=data.completed_on_time,
                              tasks_due=data.tasks_due, quality=quality, bonus_pool=data.bonus_pool, currency=data.currency)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    return {**result, "manager_id": data.manager_id,
            "review_window": [data.review_window_start, data.review_window_end]}
