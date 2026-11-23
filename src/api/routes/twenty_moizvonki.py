"""Moizvonki to Twenty CRM Webhook Bridge.

Sotuvchilar Android'da Moizvonki ishlatganda qo'ng'iroq tugashi bilan
ushbu webhook orqali Twenty CRM'dagi kontakt va bitim timeline'iga
audio zapis va tafsilotlar avtomatik biriktiriladi.
"""
from __future__ import annotations

import hmac
import logging
import os
import re
import sqlite3
from typing import Any, Dict, Optional

from fastapi import APIRouter, Header, HTTPException, Query, Request
from pydantic import BaseModel, Field

from src.services.core.crm.twenty_client import TwentyClient, TwentyAuthError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/moizvonki", tags=["moizvonki-twenty"])


class MoizvonkiCallPayload(BaseModel):
    """MoiZvonki qo'ng'iroq hodisasi modeli."""
    phone: Optional[str] = Field(default=None, description="Mijoz raqami")
    client_phone: Optional[str] = Field(default=None, description="Mijoz raqami (muqobil)")
    direction: Optional[str] = Field(default="in", description="in / out (kiruvchi / chiquvchi)")
    status: Optional[str] = Field(default="answered", description="answered / missed / busy")
    duration: Optional[int] = Field(default=0, description="Davomiylik (soniya)")
    recording_url: Optional[str] = Field(default=None, description="Audio yozuv havolasi")
    link: Optional[str] = Field(default=None, description="Audio yozuv havolasi (muqobil)")
    manager_name: Optional[str] = Field(default="Sotuvchi", description="Menejer ismi")
    user_account: Optional[str] = Field(default=None, description="Moizvonki email / hisob")
    action: Optional[str] = Field(default=None, description="call.start yoki call.finish")
    call_id: Optional[str] = Field(default=None, description="Qo'ng'iroq ID si")
    start_time: Optional[str] = Field(default=None, description="Qo'ng'iroq boshlangan vaqt")


def normalize_phone_number(raw_phone: Optional[str]) -> str:
    """Telefon raqamni xalqaro standart formatga keltiradi (+998...)."""
    if not raw_phone:
        return ""
    digits = re.sub(r"\D", "", raw_phone)
    if digits.startswith("8") and len(digits) == 11:
        digits = "7" + digits[1:]
    elif len(digits) == 9:
        digits = "998" + digits
    return f"+{digits}" if digits else ""


def build_call_note_body(
    phone: str,
    manager: str,
    direction_str: str,
    duration: int,
    status_str: str,
    audio_url: str,
    start_time: Optional[str] = None,
) -> str:
    """Timeline uchun markdown matn shakllantiradi."""
    body_lines = [
        f"**📞 Qo'ng'iroq tafsilotlari ({direction_str})**",
        f"- **Mijoz raqami:** `{phone}`",
        f"- **Mas'ul xodim:** {manager}",
        f"- **Davomiyligi:** {duration} soniya ({duration // 60}m {duration % 60}s)",
        f"- **Natija:** {status_str}",
    ]
    if start_time:
        body_lines.append(f"- **Vaqti:** {start_time}")
    if audio_url:
        body_lines.append(f"- **🎧 Audio zapis:** [Yozuvni eshitish / Yuklab olish]({audio_url})")
    return "\n".join(body_lines)


def _is_call_processed(call_id: Optional[str], db_path: str = "data/moizvonki_calls.db") -> bool:
    """Tekshiradi: ushbu call_id avval qayta ishlanganmi."""
    if not call_id:
        return False
    conn = None
    try:
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
        conn = sqlite3.connect(db_path)
        with conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS processed_calls (call_id TEXT PRIMARY KEY, processed_at TEXT)"
            )
            cur = conn.cursor()
            cur.execute("SELECT 1 FROM processed_calls WHERE call_id = ?", (call_id,))
            return cur.fetchone() is not None
    except Exception as exc:
        logger.warning("[moizvonki-twenty] call_id check error: %s", exc)
        return False
    finally:
        if conn:
            conn.close()


def _record_call_processed(call_id: Optional[str], db_path: str = "data/moizvonki_calls.db") -> None:
    """Call_id ni muvaffaqiyatli qayd etilgan deb saqlaydi."""
    if not call_id:
        return
    conn = None
    try:
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
        conn = sqlite3.connect(db_path)
        with conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS processed_calls (call_id TEXT PRIMARY KEY, processed_at TEXT)"
            )
            conn.execute(
                "INSERT OR REPLACE INTO processed_calls VALUES (?, datetime('now'))",
                (call_id,),
            )
    except Exception as exc:
        logger.warning("[moizvonki-twenty] call_id record error: %s", exc)
    finally:
        if conn:
            conn.close()


def _verify_webhook_auth(
    x_secret: Optional[str],
    auth_header: Optional[str],
    query_secret: Optional[str],
) -> None:
    """Moizvonki webhook so'rovining haqiqiyligini tekshiradi."""
    from src.settings import settings

    def _secret_val(val: Any) -> str:
        getter = getattr(val, "get_secret_value", None)
        return str(getter() if callable(getter) else val or "").strip()

    expected = (
        os.getenv("MOIZVONKI_WEBHOOK_SECRET")
        or os.getenv("TELEPHONY_WEBHOOK_SECRET")
        or _secret_val(getattr(settings, "MOIZVONKI_WEBHOOK_SECRET", None))
        or _secret_val(getattr(settings, "TELEPHONY_WEBHOOK_SECRET", None))
        or ""
    ).strip()

    if not expected:
        # Test muhitida (SKIP_LIVE=1 yoki TESTING=1) ruxsat beriladi
        if os.getenv("SKIP_LIVE") == "1" or os.getenv("TESTING") == "1":
            return
        logger.error("[moizvonki-twenty] Webhook xavfsizlik kaliti belgilanmagan!")
        raise HTTPException(
            status_code=500,
            detail="Serverda MOIZVONKI_WEBHOOK_SECRET sozlanmagan. Autentifikatsiyasiz qabul qilinmaydi.",
        )

    provided = ""
    if x_secret:
        provided = x_secret.strip()
    elif auth_header and auth_header.lower().startswith("bearer "):
        provided = auth_header[7:].strip()
    elif query_secret:
        provided = query_secret.strip()

    if not provided or not hmac.compare_digest(provided.encode("utf-8"), expected.encode("utf-8")):
        logger.warning("[moizvonki-twenty] unauthorized webhook call")
        raise HTTPException(status_code=401, detail="Unauthorized webhook secret")


async def process_moizvonki_call(
    payload: MoizvonkiCallPayload,
    client: TwentyClient,
    db_path: str = "data/moizvonki_calls.db",
) -> Dict[str, Any]:
    """Qo'ng'iroqni Twenty CRM ga bog'lash jarayoni."""
    raw_phone = payload.phone or payload.client_phone or ""
    phone = normalize_phone_number(raw_phone)
    if not phone:
        raise HTTPException(status_code=400, detail="Telefon raqami topilmadi")

    # 0. Call ID orqali takrorlanishdan himoya
    call_id = payload.call_id
    if call_id and _is_call_processed(call_id, db_path=db_path):
        logger.info("[moizvonki-twenty] call_id=%s allaqachon mavjud, takrorlanmadi", call_id)
        return {
            "status": "duplicate",
            "message": "Ushbu qo'ng'iroq allaqachon qayd etilgan",
            "call_id": call_id,
            "phone": phone,
        }

    audio_url = payload.recording_url or payload.link or ""
    manager = payload.manager_name or "Sotuvchi"
    duration = int(payload.duration or 0)
    is_incoming = payload.direction in ("in", "incoming", "kiruvchi")
    direction_str = "Kiruvchi" if is_incoming else "Chiquvchi"
    status_str = "Javob berildi" if payload.status in ("answered", "success") else "Javobsiz"

    # 1. Kontaktni topish
    person = await client.find_person_by_phone(phone)
    opportunity_id = None

    if not person:
        # Yangi kontakt yaratish
        person = await client.create_person(
            first_name=f"Mijoz {phone[-4:]}",
            last_name="",
            phone=phone,
            job_title="Yangi Murojaat",
        )
        if person and "id" in person:
            # Yangi bitim (Opportunity) yaratish
            opp = await client.create_opportunity(
                name=f"Qo'ng'iroq: {phone}",
                stage="NEW",
                person_id=person["id"],
            )
            if opp and "id" in opp:
                opportunity_id = opp["id"]

    person_id = person.get("id") if person else None
    title = f"{direction_str} qo'ng'iroq: {duration}s ({status_str})"
    body = build_call_note_body(
        phone, manager, direction_str, duration, status_str, audio_url, payload.start_time
    )

    # 2. Timeline'ga Note sifatida audio va ma'lumotni biriktirish
    note = await client.add_timeline_note(
        title=title,
        body=body,
        target_person_id=person_id,
        target_opportunity_id=opportunity_id,
    )

    # 3. Yolg'on success qaytarmaslik: note saqlanmasa xatolik qaytarish
    if not note or not isinstance(note, dict) or not note.get("id"):
        logger.error("[moizvonki-twenty] note saqlanmadi: phone_tail=%s person=%s", str(phone)[-4:], person_id)
        raise HTTPException(
            status_code=502,
            detail="Twenty CRM timeline note saqlab bo'lmadi",
        )

    if call_id:
        _record_call_processed(call_id, db_path=db_path)

    try:
        from src.services.core.crm.dialer_store import DialerStore
        DialerStore().attach_call_recording(
            phone=phone,
            audio_url=audio_url,
            duration=duration,
            manager=manager,
        )
    except Exception as exc:
        logger.warning("[moizvonki-dialer] Could not attach to dialer store: %s", exc)

    logger.info(
        "[moizvonki-twenty] call logged: phone_tail=%s person_id=%s note_id=%s call_id=%s",
        str(phone)[-4:],
        person_id,
        note.get("id"),
        call_id,
    )

    return {
        "status": "success",
        "phone": phone,
        "person_id": person_id,
        "opportunity_id": opportunity_id,
        "note_id": note.get("id"),
        "call_id": call_id,
    }


@router.post("/webhook", status_code=200)
async def moizvonki_webhook(
    request: Request,
    x_secret: Optional[str] = Header(None, alias="X-Webhook-Secret"),
    authorization: Optional[str] = Header(None, alias="Authorization"),
    secret: Optional[str] = Query(None),
) -> Dict[str, Any]:
    """MoiZvonki Android qo'ng'iroqlari webhook qabul qiluvchi endpoint."""
    _verify_webhook_auth(x_secret, authorization, secret)
    body: Dict[str, Any] = {}
    try:
        body = await request.json()
    except Exception:
        pass

    # Nested webhook / event tuzilmasini yechish
    evt = body.get("event") or {}
    hook = body.get("webhook") or {}
    action = hook.get("action") or body.get("action") or ("call.start" if body.get("direction") in ("in", 0) and not body.get("duration") else "call.finish")
    phone = body.get("phone") or body.get("client_phone") or body.get("client_number") or evt.get("phone") or evt.get("client_number") or ""
    account = body.get("user_account") or hook.get("user_login") or hook.get("user_name") or evt.get("user_account") or body.get("manager_name") or ""
    call_id = str(body.get("call_id") or evt.get("call_id") or "")

    # 1. Agar call.start bo'lsa -> Real-time Caller ID pop-upini faollashtirish
    if action == "call.start" or (body.get("direction") in ("in", 0, "incoming") and int(body.get("duration") or 0) == 0):
        try:
            from src.services.core.crm.caller_id_service import CallerIdHub
            ring_ev = CallerIdHub().process_incoming_ring(phone=phone, account=account, call_id=call_id)
            return {"status": "ringing", "event": ring_ev}
        except Exception as ring_err:
            logger.warning("[moizvonki-caller-id] Ring dispatch error: %s", ring_err)

    # 2. Call finish bo'lsa -> Caller ID pop-upni yopish va Twenty CRM ga log qilish
    try:
        from src.services.core.crm.caller_id_service import CallerIdHub, resolve_rep
        rep_slug = resolve_rep(account)["slug"]
        CallerIdHub().dismiss_ring(rep_slug, call_id=call_id)
    except Exception:
        pass

    payload = MoizvonkiCallPayload(
        phone=phone,
        direction=str(body.get("direction") or "in"),
        status=str(body.get("status") or ("answered" if body.get("answered") else "missed")),
        duration=int(body.get("duration") or 0),
        recording_url=body.get("recording_url") or body.get("link") or "",
        manager_name=account or body.get("manager_name") or "Sotuvchi",
        user_account=account,
        action=action,
        call_id=call_id,
        start_time=str(body.get("start_time") or ""),
    )

    try:
        twenty_client = TwentyClient()
    except TwentyAuthError as auth_err:
        raise HTTPException(status_code=503, detail=str(auth_err))
    return await process_moizvonki_call(payload, twenty_client)
