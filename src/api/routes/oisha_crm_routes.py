"""FastAPI Router for Native Oisha CRM Engine (amoCRM Replacement)."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from src.services.core.crm.engine import (
    CrmAiCoach,
    CrmAutomationEngine,
    DealCreate,
    DealUpdate,
    IntakeLeadPayload,
    LeadIntakeService,
    OishaCrmStore,
    TaskCreate,
    TimelineEventCreate,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/crm/native", tags=["oisha-crm-native"])

# Default singleton instances
store = OishaCrmStore()
automation = CrmAutomationEngine(store)
intake = LeadIntakeService(store, automation)
coach = CrmAiCoach(store)


class NotePayload(BaseModel):
    text: str
    author: str = "Menejer"


@router.get("/pipelines")
async def get_pipelines():
    """Barcha savdo voronkalari va ularning bosqichlarini olish."""
    return {"pipelines": store.get_pipelines()}


@router.get("/kanban")
async def get_kanban(pipeline_id: int = Query(1, description="Voronka ID")):
    """Kanban koʻrinishi uchun bosqichlar va bitimlarni olish."""
    return store.get_kanban_deals(pipeline_id)


@router.post("/deal")
async def create_deal(payload: DealCreate):
    """Yangi bitim yaratish."""
    deal = store.create_deal(payload)
    automation.handle_stage_changed(deal, "inbox")
    return {"status": "ok", "deal": deal}


@router.get("/deal/{deal_id}")
async def get_deal(deal_id: int):
    """Bitim tafsilotlarini olish."""
    deal = store.get_deal(deal_id)
    if not deal:
        raise HTTPException(status_code=404, detail="Bitim topilmadi")
    timeline = store.get_timeline(deal_id)
    return {"deal": deal, "timeline": timeline}


@router.patch("/deal/{deal_id}")
async def update_deal(deal_id: int, payload: DealUpdate):
    """Mavjud bitimni tahrirlash yoki bosqichini oʻzgartirish."""
    deal = store.update_deal(deal_id, payload)
    if not deal:
        raise HTTPException(status_code=404, detail="Bitim topilmadi")
    if payload.stage_id is not None:
        # Yangi bosqich slugini topish
        stages = {s.id: s.slug for p in store.get_pipelines() for s in p.stages}
        slug = stages.get(payload.stage_id, "unknown")
        automation.handle_stage_changed(deal, slug)
    return {"status": "ok", "deal": deal}


@router.post("/deal/{deal_id}/task")
async def create_task(deal_id: int, payload: TaskCreate):
    """Bitimga vazifa yuklash."""
    payload.deal_id = deal_id
    task = store.create_task(payload)
    return {"status": "ok", "task": task}


@router.post("/task/{task_id}/complete")
async def complete_task(task_id: int, result_text: str = Query("Bajarildi")):
    """Vazifani bajarilgan deb belgilash."""
    success = store.complete_task(task_id, result_text)
    if not success:
        raise HTTPException(status_code=404, detail="Vazifa topilmadi")
    return {"status": "ok", "task_id": task_id}


@router.get("/deal/{deal_id}/timeline")
async def get_timeline(deal_id: int):
    """Bitim tarixi (Timeline)ni olish."""
    return {"timeline": store.get_timeline(deal_id)}


@router.post("/deal/{deal_id}/note")
async def add_note(deal_id: int, payload: NotePayload):
    """Bitimga izoh qoldirish."""
    event = store.add_timeline_event(
        TimelineEventCreate(
            deal_id=deal_id,
            event_type="note",
            author=payload.author,
            text=payload.text,
        )
    )
    return {"status": "ok", "event": event}


@router.post("/deal/{deal_id}/surgical-mission")
async def run_surgical_mission(deal_id: int):
    """Oisha AI Surgical Mission taktik rejasini generatsiya qilish."""
    res = coach.generate_surgical_mission(deal_id)
    if "error" in res:
        raise HTTPException(status_code=404, detail=res["error"])
    return res


@router.post("/intake")
async def public_lead_intake(payload: IntakeLeadPayload):
    """Veb-sayt, Bot yoki Tashqi formadan kiruvchi yangi lidni qabul qilish."""
    result = intake.process_incoming_lead(payload)
    return result
