"""Saytdagi "Sizga qo'ng'iroq qilamiz" vidjeti uchun ochiq endpoint.

Vidjet: `/api/callback-widget.js` (saytga bitta <script> bilan qo'yiladi).
Himoya: IP bo'yicha rate limit, honeypot maydon, raqam bo'yicha 10 daqiqalik
dedup, barcha maydonlar uzunligi cheklangan. Default o'chiq.
"""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Optional, Set

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field
from slowapi import Limiter
from slowapi.util import get_remote_address

from src.services.core.leads import call_tracking
from src.services.core.leads import callback_request as cb

router = APIRouter(tags=["callback-widget"])
limiter = Limiter(key_func=get_remote_address)
logger = logging.getLogger(__name__)

_background: Set[asyncio.Task] = set()
_WIDGET_JS = Path(__file__).resolve().parents[2] / "static" / "callback-widget.js"


class CallbackRequest(BaseModel):
    phone: str = Field(min_length=7, max_length=32)
    name: str = Field(default="", max_length=80)
    # Honeypot: odam ko'rmaydi, bot to'ldiradi.
    website: str = Field(default="", max_length=200)
    utm_source: str = Field(default="", max_length=120)
    utm_medium: str = Field(default="", max_length=120)
    utm_campaign: str = Field(default="", max_length=200)
    utm_content: str = Field(default="", max_length=200)
    utm_term: str = Field(default="", max_length=200)
    fbclid: str = Field(default="", max_length=300)
    gclid: str = Field(default="", max_length=300)
    yclid: str = Field(default="", max_length=300)
    page_url: str = Field(default="", max_length=500)
    landing_url: str = Field(default="", max_length=500)
    referrer: str = Field(default="", max_length=500)


def _tracking(body: CallbackRequest) -> dict:
    keys = cb.UTM_KEYS + cb.CLICK_ID_KEYS + ("page_url", "landing_url", "referrer")
    return {k: getattr(body, k).strip() for k in keys if getattr(body, k).strip()}


def _spawn(coro) -> None:
    task = asyncio.create_task(coro)
    _background.add(task)
    task.add_done_callback(_background.discard)


@router.post("/api/callback-request", status_code=202)
@limiter.limit("5/minute")
async def create_callback_request(request: Request, body: CallbackRequest) -> dict:
    if not cb.is_enabled():
        raise HTTPException(status_code=404, detail="Not found")
    if body.website:
        logger.info("[CALLBACK REQUEST] Honeypot to'ldirilgan — bot, e'tiborsiz")
        return {"status": "accepted"}
    try:
        phone = cb.normalize_phone(body.phone)
    except cb.InvalidPhoneError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if cb.is_duplicate_phone(phone):
        return {"status": "accepted"}
    _spawn(cb.handle_callback_request(body.name.strip(), phone, _tracking(body)))
    return {"status": "accepted"}


@router.get("/api/callback-widget.js", include_in_schema=False)
@router.get("/callback-widget.js", include_in_schema=False)
async def callback_widget_js() -> FileResponse:
    # /static mount faylni topmaydi va boshqa ichki sahifalarni ham ochadi —
    # shuning uchun faqat shu bitta fayl beriladi. Prod'da Nginx faqat /api/*
    # ni backend'ga yuboradi (qolgani Next.js) — saytga /api/callback-widget.js qo'yiladi.
    return FileResponse(
        _WIDGET_JS, media_type="application/javascript",
        headers={"Cache-Control": "public, max-age=3600"},
    )


@router.get("/api/call-tracking/config")
async def call_tracking_config() -> JSONResponse:
    """Saytdagi JS uchun manba → raqam (faqat ochiq telefon raqamlari)."""
    return JSONResponse(
        call_tracking.public_config(),
        headers={"Cache-Control": "public, max-age=300"},
    )


def get_pending_tasks() -> Optional[Set[asyncio.Task]]:
    """Testlar uchun."""
    return _background
