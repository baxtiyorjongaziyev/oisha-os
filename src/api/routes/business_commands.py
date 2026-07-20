"""Secure API contract for Oisha Business Command Center."""

from __future__ import annotations

import hmac
import os

from fastapi import APIRouter, HTTPException, Request
from fastapi import Query
from pydantic import BaseModel, Field

from src.api.routes.state import api_state
from src.services.core.business_command_center import (
    branding_erp_roadmap,
    collect_business_command_snapshot,
    collect_finance_project_risks,
    collect_project_delivery_risks,
    collect_sales_today_priorities,
    collect_team_capacity_snapshot,
    list_integration_capabilities,
    plan_business_command,
    telegram_bot_migration_status,
)


router = APIRouter(prefix="/api/oisha", tags=["business-command-center"])


class BusinessCommandRequest(BaseModel):
    command: str = Field(min_length=1, max_length=2000)
    actor_id: str = Field(default="owner", min_length=1, max_length=128)


def _authorize(request: Request) -> None:
    secret = (os.getenv("OISHA_API_SECRET") or "").strip()
    supplied = request.headers.get("Authorization", "")
    if not secret or not hmac.compare_digest(supplied, f"Bearer {secret}"):
        raise HTTPException(status_code=401, detail="Unauthorized")


@router.get("/integrations")
async def integration_capabilities(request: Request):
    _authorize(request)
    integrations = list_integration_capabilities()
    return {
        "integrations": integrations,
        "configured_count": sum(item["configured"] for item in integrations),
        "total_count": len(integrations),
        "claim_policy": "Only runtime-verified configuration is counted.",
    }


@router.get("/erp/roadmap")
async def erp_roadmap(request: Request):
    _authorize(request)
    return {
        "positioning": "Oisha Integration ERP Brain for branding agencies",
        "principles": [
            "Use external free or low-cost platforms as source of truth.",
            "Run all production workers 24/7 on server infrastructure.",
            "Never invent data when a live source is missing.",
            "Require owner approval before external mutations.",
            "Keep Telegram userbot on Telethon; migrate bot-account head to Aiogram in phases.",
        ],
        "phases": branding_erp_roadmap(),
    }


@router.get("/telegram/migration")
async def telegram_migration(request: Request):
    _authorize(request)
    return {
        "policy": "Userbot remains Telethon on Oracle VM; bot-account head migrates to Aiogram gradually.",
        "status": telegram_bot_migration_status(),
    }


@router.get("/sales/today-priorities")
async def sales_today_priorities(
    request: Request,
    limit: int = Query(default=12, ge=1, le=50),
):
    _authorize(request)
    return await collect_sales_today_priorities(_get_runtime_amocrm(), limit=limit)


@router.get("/projects/risks")
async def project_delivery_risks(
    request: Request,
    limit: int = Query(default=12, ge=1, le=50),
):
    _authorize(request)
    return await collect_project_delivery_risks(_get_runtime_airtable(), limit=limit)


@router.get("/finance/risks")
async def finance_project_risks(
    request: Request,
    limit: int = Query(default=12, ge=1, le=50),
):
    _authorize(request)
    source = _get_runtime_airtable() or _get_runtime_project_engine()
    return await collect_finance_project_risks(source, limit=limit)


@router.get("/team/capacity")
async def team_capacity(
    request: Request,
    limit: int = Query(default=12, ge=1, le=50),
):
    _authorize(request)
    source = _get_runtime_airtable() or _get_runtime_project_engine()
    return await collect_team_capacity_snapshot(
        source,
        hr_source=_get_runtime_hr_engine(),
        limit=limit,
    )


@router.get("/command-center")
async def command_center(
    request: Request,
    limit: int = Query(default=5, ge=1, le=20),
):
    _authorize(request)
    project_source = _get_runtime_airtable() or _get_runtime_project_engine()
    return await collect_business_command_snapshot(
        amocrm=_get_runtime_amocrm(),
        project_source=project_source,
        finance_source=project_source,
        hr_source=_get_runtime_hr_engine(),
        limit=limit,
    )


@router.post("/command/plan")
async def business_command_plan(payload: BusinessCommandRequest, request: Request):
    _authorize(request)
    plan = plan_business_command(payload.command, actor_id=payload.actor_id)
    return {
        "status": "approval_required" if plan.approval_required else "read_only_ready",
        "plan": plan.to_payload(),
        "execution_policy": (
            "Mutations must pass owner approval; reads must include source timestamp and evidence."
        ),
    }


def _get_runtime_amocrm():
    if api_state.amocrm_instance is not None:
        return api_state.amocrm_instance
    try:
        from src.api.routes.amocrm_integration import _get_amocrm_instance

        return _get_amocrm_instance()
    except Exception:
        return None


def _get_runtime_airtable():
    msg_controller = api_state.msg_controller
    crm = getattr(msg_controller, "crm", None)
    airtable = getattr(crm, "airtable", None)
    if airtable is not None:
        return airtable
    try:
        from src.settings import settings

        if not getattr(settings, "AIRTABLE_API_KEY", None) and not getattr(
            settings, "AIRTABLE_OAUTH_CLIENT_ID", None
        ):
            return None
        from src.services.core.airtable_sync import AirtableSync

        return AirtableSync()
    except Exception:
        return None


def _get_runtime_project_engine():
    if api_state.db_instance is None:
        return None
    try:
        from src.services.core.project_engine import ProjectEngine

        return ProjectEngine(db=api_state.db_instance)
    except Exception:
        return None


def _get_runtime_hr_engine():
    if api_state.db_instance is None:
        return None
    try:
        from src.services.core.hr_engine import HREngine

        return HREngine(db=api_state.db_instance)
    except Exception:
        return None
