"""CRM Call Routing & 1-Click Callback API for Jon CRM.

Ushbu modul orqali:
1. 1-Click MoiZvonki callback qo'ng'iroqlari amalga oshiriladi.
2. Bitim bo'yicha audio yozuvlar va qo'ng'iroqlar tarixi olinadi.
3. Audio yozuvlar O'zbek tilida Whisper/Gemini orqali transkripsiya qilinadi.
4. BANT tahlili va mijoz og'riqlari avtomatik chiqariladi.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
import urllib.parse
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field
import requests

from src.services.core.crm.callback_service import CrmCallService, ACTIVE_SELLERS_MAP
from src.services.core.crm.call_intel_service import call_intel_service
from src.services.core.crm.seller_auth import get_current_crm_seller

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/crm/dialer/calls", tags=["crm-calls"])
call_service = CrmCallService()


class CallbackPayload(BaseModel):
    lead_id: int = Field(..., description="Bitim / Lid ID raqami")
    client_phone: str = Field(..., description="Mijozning telefon raqami")
    seller_slug: Optional[str] = Field(default=None, description="Sotuvchi slug (masalan: shahnoza)")


class ManualCallLogPayload(BaseModel):
    lead_id: int = Field(..., description="Bitim / Lid ID raqami")
    seller_slug: Optional[str] = Field(default=None, description="Sotuvchi slug")
    duration_seconds: int = Field(default=0, description="Suhbat davomiyligi (soniya)")
    outcome: str = Field(default="answered", description="Natija: answered, no_answer, busy, failed")
    note: Optional[str] = Field(default=None, description="Qo'ng'iroq bo'yicha qisqa izoh")


class TranscribeCallPayload(BaseModel):
    lead_id: int = Field(..., description="Bitim / Lid ID raqami")
    audio_url: Optional[str] = Field(default=None, description="Audio yozuv havolasi")
    transcript_override: Optional[str] = Field(default=None, description="Tayyor transkripsiya matni")


class CallRecordModel(BaseModel):
    id: str
    audio_url: Optional[str] = None
    duration: int = 0
    duration_formatted: str = "0s"
    by: str = "Sotuvchi"
    time: str = "Bugun"
    direction: str = "out"
    status: str = "answered"
    title: str = "Qo'ng'iroq"
    transcript: Optional[str] = None
    ai_analysis: Optional[Dict[str, Any]] = None


@router.post("/callback")
async def initiate_callback_endpoint(
    payload: CallbackPayload,
    current_seller: Optional[Dict[str, Any]] = Depends(get_current_crm_seller),
) -> Dict[str, Any]:
    """1-Click Callback: MoiZvonki yoki smart tel ko'prigi orqali mijozga bog'lanish."""
    seller_slug = payload.seller_slug or (current_seller.get("slug") if current_seller else "shahnoza")
    res = call_service.initiate_callback(
        lead_id=payload.lead_id,
        seller_slug=seller_slug,
        client_phone=payload.client_phone,
    )
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("detail", "Qo'ng'iroq chaqirishda xatolik yuz berdi"))
    return res


@router.get("/history/{lead_id}")
async def get_lead_calls_history(
    lead_id: int,
    current_seller: Optional[Dict[str, Any]] = Depends(get_current_crm_seller),
) -> Dict[str, Any]:
    """Bitim bo'yicha barcha audio yozuvlar va qo'ng'iroqlar ro'yxatini olish."""
    calls = call_service.get_lead_call_history(lead_id)
    return {
        "success": True,
        "lead_id": lead_id,
        "total_calls": len(calls),
        "calls": calls,
    }


@router.post("/log-manual")
async def log_manual_call_endpoint(
    payload: ManualCallLogPayload,
    current_seller: Optional[Dict[str, Any]] = Depends(get_current_crm_seller),
) -> Dict[str, Any]:
    """Menejer o'z telefoni orqali gaplashganda natijani qo'lda qayd etish."""
    seller_slug = payload.seller_slug or (current_seller.get("slug") if current_seller else "shahnoza")
    seller = call_service._get_seller(seller_slug)

    dur_min = payload.duration_seconds // 60
    dur_sec = payload.duration_seconds % 60
    dur_str = f"{dur_min}:{dur_sec:02d}"

    note_text = f"📞 Qo'ng'iroq ({seller['name']}): {payload.outcome}. Davomiyligi: {dur_str}."
    if payload.note:
        note_text += f" Izoh: {payload.note}"

    success = call_service.store.add_lead_note(
        lead_id=payload.lead_id,
        text=note_text,
        author=seller["name"],
    )

    with call_service.store._get_conn() as conn:
        conn.execute(
            """
            UPDATE dialer_leads
            SET calls_count = calls_count + 1, last_called_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?;
            """,
            (payload.lead_id,),
        )
        conn.commit()

    return {"success": success, "lead_id": payload.lead_id, "note": note_text}


@router.post("/transcribe")
async def transcribe_call_endpoint(
    payload: TranscribeCallPayload,
    current_seller: Optional[Dict[str, Any]] = Depends(get_current_crm_seller),
) -> Dict[str, Any]:
    """Qo'ng'iroq audiosini transkripsiya qilish va BANT tahlili chiqarish."""
    res = await call_intel_service.process_lead_call_intelligence(
        lead_id=payload.lead_id,
        audio_url=payload.audio_url,
        transcript_override=payload.transcript_override,
    )
    return res


@router.post("/ai-analyze-lead/{lead_id}")
async def ai_analyze_lead_endpoint(
    lead_id: int,
    current_seller: Optional[Dict[str, Any]] = Depends(get_current_crm_seller),
) -> Dict[str, Any]:
    """Bitim bo'yicha barcha aloqalar asosida 360° AI tahlili tuzish."""
    res = await call_intel_service.run_holistic_deal_analysis(lead_id)
    return res


@router.get("/proxy-audio")
async def proxy_audio_stream(
    url: str = Query(..., description="Audio manzilining to'liq havolasi"),
    current_seller: Optional[Dict[str, Any]] = Depends(get_current_crm_seller),
) -> Response:
    """Tashqi MoiZvonki audio fayllarini CORS to'siqlarisiz pleyerga uzatish."""
    clean_url = urllib.parse.unquote(url).strip()
    if not clean_url.startswith("http://") and not clean_url.startswith("https://"):
        raise HTTPException(status_code=400, detail="Noto'g'ri audio havolasi")

    try:
        r = requests.get(clean_url, timeout=15, stream=True)
        if r.status_code != 200:
            raise HTTPException(status_code=r.status_code, detail="Audio faylni yuklab bo'lmadi")

        content_type = r.headers.get("Content-Type", "audio/mpeg")
        return Response(content=r.content, media_type=content_type)
    except Exception as e:
        logger.warning("[AUDIO-PROXY] Stream error: %s", e)
        raise HTTPException(status_code=502, detail="Audio oqimida xatolik yuz berdi")


@router.get("/stats/{rep_slug}")
async def get_rep_call_stats(
    rep_slug: str,
    current_seller: Optional[Dict[str, Any]] = Depends(get_current_crm_seller),
) -> Dict[str, Any]:
    """Sotuvchining joriy sessiya / bugungi kun bo'yicha qo'ng'iroq statistikasi."""
    seller = call_service._get_seller(rep_slug)
    with call_service.store._get_conn() as conn:
        row = conn.execute(
            """
            SELECT COUNT(*) as total_leads, SUM(calls_count) as total_calls
            FROM dialer_leads
            WHERE responsible_name LIKE ?;
            """,
            (f"%{seller['name']}%",),
        ).fetchone()

        total_leads = row["total_leads"] if row else 0
        total_calls = row["total_calls"] if row else 0

    return {
        "success": True,
        "seller": seller["name"],
        "slug": seller["slug"],
        "phone": seller["phone"],
        "total_assigned_leads": total_leads,
        "total_calls_logged": total_calls or 0,
    }
