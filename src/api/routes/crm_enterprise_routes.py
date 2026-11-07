"""amoCRM Enterprise Routes (Digital Pipeline, Plan-Fakt, Loss Analytics, RBAC).

Ushbu marshrutlar amoCRM Enterprise tarifidagi chuqur funksiyalarni
frontend bilan to'liq bog'laydi:
1. Raqamli voronka (Digital Pipeline) avtomatlashtirish qoidalari va triggerlari.
2. Sotuv rejalari (Plan vs Fact), pacing va bashorat.
3. Rad etish sabablari tahlili va bosqichlar tezligi (Cycle Time).
4. Xodimlar rollari va ruxsatlar matrisasi (RBAC).
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from src.services.core.crm.digital_pipeline import DigitalPipelineEngine
from src.services.core.crm.sales_targets import SalesTargetsEngine
from src.services.core.crm.loss_analytics import LossAnalyticsEngine
from src.services.core.crm.crm_rbac import CrmRbacGuard
from src.api.routes.crm_dialer import require_dialer_access

logger = logging.getLogger(__name__)

# ApiAccessMiddleware skips /api/crm/dialer/*, so the dialer guard (seller
# session or admin principal) must be applied here too.
router = APIRouter(tags=["amoCRM Enterprise"], dependencies=[Depends(require_dialer_access)])

dp_engine = DigitalPipelineEngine()
target_engine = SalesTargetsEngine()
loss_engine = LossAnalyticsEngine()
rbac_guard = CrmRbacGuard()


class AddRulePayload(BaseModel):
    pipeline_id: int = 11162698
    stage_slug: str
    name: str
    trigger_type: str = "stage_enter"
    action_type: str
    action_payload: Dict[str, Any]


class StageTriggerPayload(BaseModel):
    lead_id: int
    pipeline_id: int = 11162698
    new_stage_slug: str
    seller_name: str = "Shahnoza Abdijabborova"


class SetTargetPayload(BaseModel):
    seller_name: str
    month_str: str = Field(..., pattern=r"^\d{4}-\d{2}$")
    target_revenue: float
    target_deals: int


class RecordLossPayload(BaseModel):
    reason: str
    note: str = ""
    lost_amount: float = 0.0
    seller_name: str = "Shahnoza Abdijabborova"


# ==========================================
# 1. RAQAMLI VORONKA (DIGITAL PIPELINE)
# ==========================================

@router.get("/api/crm/dialer/digital-pipeline/rules")
async def get_digital_pipeline_rules(pipeline_id: int = 11162698) -> Dict[str, Any]:
    """Voronka bo'yicha barcha avtomatlashtirish qoidalarini olish."""
    rules = dp_engine.get_pipeline_rules(pipeline_id=pipeline_id)
    return {"success": True, "pipeline_id": pipeline_id, "rules": rules}


@router.post("/api/crm/dialer/digital-pipeline/rules")
async def add_digital_pipeline_rule(payload: AddRulePayload) -> Dict[str, Any]:
    """Yangi avtomatlashtirish qoidasini kiritish."""
    rule_id = dp_engine.add_rule(
        pipeline_id=payload.pipeline_id,
        stage_slug=payload.stage_slug,
        name=payload.name,
        trigger_type=payload.trigger_type,
        action_type=payload.action_type,
        action_payload=payload.action_payload,
    )
    return {"success": True, "rule_id": rule_id}


@router.post("/api/crm/dialer/digital-pipeline/rules/{rule_id}/toggle")
async def toggle_digital_pipeline_rule(rule_id: int, is_active: bool = Query(...)) -> Dict[str, Any]:
    """Qoidani faollashtirish yoki to'xtatish."""
    ok = dp_engine.toggle_rule(rule_id=rule_id, is_active=is_active)
    return {"success": ok, "rule_id": rule_id, "is_active": is_active}


@router.post("/api/crm/dialer/digital-pipeline/trigger")
async def trigger_stage_enter(payload: StageTriggerPayload) -> Dict[str, Any]:
    """Sdelka yangi bosqichga o'tganda avtomatlashtirish qoidalarini ishga tushirish."""
    executed = await dp_engine.execute_stage_enter_triggers(
        lead_id=payload.lead_id,
        pipeline_id=payload.pipeline_id,
        new_stage_slug=payload.new_stage_slug,
        seller_name=payload.seller_name,
    )
    return {"success": True, "lead_id": payload.lead_id, "executed_rules": executed}


# ==========================================
# 2. SOTUV REJALARI (PLAN VS FACT & FORECAST)
# ==========================================

@router.get("/api/crm/dialer/targets/overview")
async def get_sales_targets_overview(month: Optional[str] = None) -> Dict[str, Any]:
    """Oylik sotuv rejalari, kassa bashorati va kunlik sur'at hisoboti."""
    overview = target_engine.get_plan_fact_overview(month_str=month)
    return {"success": True, **overview}


@router.post("/api/crm/dialer/targets")
async def set_sales_target(payload: SetTargetPayload) -> Dict[str, Any]:
    """Menejerga oylik sotuv rejasini belgilash."""
    ok = target_engine.set_seller_target(
        seller_name=payload.seller_name,
        month_str=payload.month_str,
        target_revenue=payload.target_revenue,
        target_deals=payload.target_deals,
    )
    return {"success": ok}


# ==========================================
# 3. RAD ETISH SABABLARI VA CYCLE TIME
# ==========================================

@router.get("/api/crm/dialer/loss-analytics")
async def get_loss_and_velocity_analytics() -> Dict[str, Any]:
    """Rad sabablari doiraviy tahlili va bosqichlar tezligi (Cycle Time) hisoboti."""
    loss_rep = loss_engine.get_loss_reasons_report()
    vel_rep = loss_engine.get_cycle_time_velocity_report()
    return {
        "success": True,
        "loss_reasons": loss_rep,
        "cycle_time_velocity": vel_rep,
    }


@router.post("/api/crm/dialer/lead/{lead_id}/loss")
async def record_deal_loss(lead_id: int, payload: RecordLossPayload) -> Dict[str, Any]:
    """Sdelkani rad etish sababi bilan birga yopish."""
    ok = loss_engine.record_loss(
        lead_id=lead_id,
        reason=payload.reason,
        note=payload.note,
        lost_amount=payload.lost_amount,
        seller_name=payload.seller_name,
    )
    return {"success": ok, "lead_id": lead_id}


# ==========================================
# 4. ROLLARDAGI RUXSATLAR (RBAC)
# ==========================================

@router.get("/api/crm/dialer/rbac/users")
async def get_crm_rbac_users() -> Dict[str, Any]:
    """Foydalanuvchilar va ularning huquqlar matrisasi."""
    users = rbac_guard.get_users_list()
    return {"success": True, "users": users}
