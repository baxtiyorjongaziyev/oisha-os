"""Google Calendar API endpoints for Oisha-OS and connected agents."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from src.api.rbac import Permission, require_permissions
from src.services.core.gcalendar import GoogleCalendarSync

router = APIRouter(
    prefix="/api/calendar",
    tags=["calendar"],
    dependencies=[require_permissions(Permission.DASHBOARD_READ)],
)
logger = logging.getLogger(__name__)


class CreateCalendarEventRequest(BaseModel):
    summary: str = Field(..., min_length=1, max_length=500, description="Tadbir mavzusi")
    start_time: str = Field(..., description="Boshlanish vaqti ISO-8601 (masalan: 2026-11-03T15:00:00+05:00)")
    end_time: str = Field(..., description="Tugash vaqti ISO-8601 (masalan: 2026-11-03T16:00:00+05:00)")
    description: Optional[str] = Field(default="", max_length=2000, description="Tadbir tavsifi")
    location: Optional[str] = Field(default="", max_length=500, description="Joylashuv yoki havola")
    calendar_id: Optional[str] = Field(default=None, description="Maxsus kalendar ID (agar berilmasa asosiy kalendar ishlatiladi)")


class CalendarEventResponse(BaseModel):
    id: Optional[str] = None
    summary: str
    start: Optional[Dict[str, Any]] = None
    end: Optional[Dict[str, Any]] = None
    html_link: Optional[str] = None
    status: Optional[str] = None


def _get_calendar_sync(calendar_id: Optional[str] = None) -> GoogleCalendarSync:
    try:
        sync = GoogleCalendarSync(calendar_id=calendar_id)
        if not sync.service:
            raise HTTPException(
                status_code=503,
                detail="Google Calendar servisi bilan aloqa o'rnatilmadi (avtorizatsiya topilmadi).",
            )
        return sync
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("[CALENDAR_ROUTE] Sync yaratishda xato: %s", exc)
        raise HTTPException(
            status_code=500,
            detail=f"Google Calendar sozlamalarida xatolik: {exc}",
        )


@router.get("/events")
async def list_events(
    date: Optional[str] = Query(None, description="Sana (YYYY-MM-DD), agar ko'rsatilmasa bugun olinadi"),
    limit: int = Query(10, ge=1, le=100, description="Ko'rsatiladigan tadbirlar soni"),
    calendar_id: Optional[str] = Query(None, description="Kalendar ID"),
):
    """Google Calendar'dagi yaqinlashib kelayotgan tadbirlarni olish."""
    sync = _get_calendar_sync(calendar_id=calendar_id)
    try:
        raw_events = sync.get_upcoming_events(date_str=date, limit=limit)
        events = []
        for item in raw_events:
            events.append({
                "id": item.get("id"),
                "summary": item.get("summary", "(Mavzusiz)"),
                "start": item.get("start"),
                "end": item.get("end"),
                "html_link": item.get("htmlLink"),
                "status": item.get("status"),
            })
        return {
            "status": "ok",
            "calendar_id": sync.calendar_id,
            "date": date,
            "count": len(events),
            "events": events,
        }
    except Exception as exc:
        logger.error("[CALENDAR_ROUTE] Tadbirlarni olishda xato: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/events")
async def create_event(payload: CreateCalendarEventRequest):
    """Google Calendar'ga yangi tadbir yoki uchrashuv qo'shish."""
    sync = _get_calendar_sync(calendar_id=payload.calendar_id)
    try:
        result = sync.create_event(
            summary=payload.summary,
            start_time=payload.start_time,
            end_time=payload.end_time,
            description=payload.description or "",
            location=payload.location or "",
        )
        if not result:
            raise HTTPException(status_code=500, detail="Tadbirni Google Calendar'ga qo'shib bo'lmadi.")

        event_id = result.get("id") if isinstance(result, dict) else None
        html_link = result.get("htmlLink") if isinstance(result, dict) else None

        return {
            "status": "ok",
            "message": "Tadbir muvaffaqiyatli yaratildi",
            "calendar_id": sync.calendar_id,
            "event_id": event_id,
            "html_link": html_link,
            "event": result if isinstance(result, dict) else None,
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("[CALENDAR_ROUTE] Tadbir yaratishda xato: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/free-slots")
async def get_free_slots(
    date: Optional[str] = Query(None, description="Sana (YYYY-MM-DD), agar ko'rsatilmasa bugun olinadi"),
    calendar_id: Optional[str] = Query(None, description="Kalendar ID"),
):
    """Ma'lum bir kun uchun bo'sh uchrashuv vaqtlarini olish (10:00-18:00 oraliqda)."""
    sync = _get_calendar_sync(calendar_id=calendar_id)
    try:
        slots = sync.get_free_slots(date_str=date)
        return {
            "status": "ok",
            "calendar_id": sync.calendar_id,
            "date": date,
            "free_slots": slots,
        }
    except Exception as exc:
        logger.error("[CALENDAR_ROUTE] Bo'sh vaqtlarni olishda xato: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))
