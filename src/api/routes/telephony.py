"""Telefoniya va kiruvchi qo'ng'iroqlar webhook marshruti.

Android MacroDroid, Tasker yoki Cloud PBX (Ezzy/Moizvonki) dan
kiruvchi qo'ng'iroq signallarini qabul qilib, real vaqtda mijoz
kartasini Telegram'ga chiqaradi.
"""
from __future__ import annotations

import hmac
import logging
import os
from typing import Any, Dict, Optional

from fastapi import APIRouter, Header, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from src.services.call_analytics.incoming_call_card import (
    handle_incoming_call,
    is_incoming_call_card_enabled,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/telephony", tags=["telephony"])


class IncomingCallRequest(BaseModel):
    phone: str = Field(min_length=7, max_length=32, description="Kiruvchi telefon raqami")
    manager: Optional[str] = Field(default=None, max_length=100, description="Menejer ismi")
    manager_phone: Optional[str] = Field(default=None, max_length=32, description="Menejer telefon raqami")
    call_id: Optional[str] = Field(default=None, max_length=100, description="Qo'ng'iroq ID si")
    source: Optional[str] = Field(default=None, max_length=100, description="Kanal / reklama manbasi")
    chat_id: Optional[str] = Field(default=None, max_length=50, description="Ixtiyoriy maqsadli Telegram chat ID")


def _verify_secret(
    x_telephony_secret: Optional[str],
    authorization: Optional[str],
    secret_query: Optional[str],
) -> None:
    expected = (
        os.getenv("TELEPHONY_WEBHOOK_SECRET")
        or os.getenv("OISHA_API_SECRET")
        or ""
    ).strip()
    if not expected:
        # Agar tizimda maxfiy kalit o'rnatilmagan bo'lsa, o'tkaziladi
        return

    provided = ""
    if x_telephony_secret:
        provided = x_telephony_secret.strip()
    elif authorization and authorization.lower().startswith("bearer "):
        provided = authorization[7:].strip()
    elif secret_query:
        provided = secret_query.strip()

    if not provided or not hmac.compare_digest(provided.encode("utf-8"), expected.encode("utf-8")):
        raise HTTPException(
            status_code=401,
            detail="Noto'g'ri maxfiy kalit (Unauthorized telephony secret)",
        )


@router.post("/incoming-call", status_code=200)
async def incoming_call_webhook(
    payload: IncomingCallRequest,
    x_telephony_secret: Optional[str] = Header(None, alias="X-Telephony-Secret"),
    authorization: Optional[str] = Header(None, alias="Authorization"),
    secret: Optional[str] = Query(None),
) -> JSONResponse:
    """Kiruvchi qo'ng'iroq signali kelganda mijoz kartasini tayyorlash va yuborish."""
    _verify_secret(x_telephony_secret, authorization, secret)

    if not is_incoming_call_card_enabled():
        return JSONResponse(
            status_code=200,
            content={"status": "disabled", "message": "Incoming call card feature is disabled"},
        )

    amocrm: Any = None
    try:
        from src.services.core.crm.amocrm_sync import AmoCRMSync
        amocrm = AmoCRMSync()
    except Exception as exc:
        logger.warning("[TELEPHONY ROUTE] AmoCRMSync yuklanmadi: %s", exc)

    result = await handle_incoming_call(payload.model_dump(), amocrm=amocrm)
    return JSONResponse(status_code=200, content={"status": "ok", "result": result})
