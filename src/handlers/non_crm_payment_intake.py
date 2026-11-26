"""CRM bilan ishlamaydigan sotuvchilar (masalan, Hasanboy) uchun guruhdan mijoz maʼlumotini olib amoCRMga kiritish."""
from __future__ import annotations

import asyncio
import json
import re
from typing import Any, Dict, Optional

import structlog

from src.context import app_ctx
from src.services.core.crm.amocrm_pipeline_config import SALES_PIPELINE_ID

logger = structlog.get_logger()

STATUS_WON_ID = 142
_PHONE_RE = re.compile(r"(?:\+?998[ \t\-()]*)?(?:\d[ \t\-()]*){9,12}")
_DIGITS_RE = re.compile(r"\d+")
_NAME_LINE_RE = re.compile(r"^(?:1\s*[\.\)]\s*)?(?:mijoz(?:\s+ismi)?|ism|f\.?i\.?sh\.?)\s*[:\-]\s*(.+)$", re.IGNORECASE)


def pending_intake_key(chat_id: int, message_id: int) -> str:
    return f"non_crm_intake:{chat_id}:{message_id}"


def parse_amount_uzs(amount_text: Optional[str]) -> int:
    """'11 760 000 soʻm' koʻrinishidagi matndan butun summani ajratadi."""
    if not amount_text:
        return 0
    if re.search(r"usd|\$|dollar", amount_text, re.IGNORECASE):
        return 0
    digits = "".join(_DIGITS_RE.findall(amount_text))
    return int(digits) if digits else 0


def extract_phone(text: str) -> Optional[str]:
    """Matndan Oʻzbekiston yoki xalqaro telefon raqamini ajratadi."""
    match = _PHONE_RE.search(text or "")
    if not match:
        return None
    digits = re.sub(r"\D", "", match.group(0))
    if len(digits) == 9:
        return f"+998{digits}"
    if len(digits) == 12 and digits.startswith("998"):
        return f"+{digits}"
    if 9 <= len(digits) <= 15:
        return f"+{digits}"
    return None


def extract_client_name(text: str, fallback: str) -> str:
    """Javob matnidan mijoz ismini ajratadi; topilmasa loyiha nomini qaytaradi."""
    for raw_line in (text or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        matched = _NAME_LINE_RE.match(line)
        if matched:
            candidate = _PHONE_RE.sub("", matched.group(1)).strip(" ,;-–—")
            if candidate:
                return candidate[:120]
    return (fallback or "Mijoz").strip()[:120]


async def save_pending_intake(
    db: Any,
    chat_id: int,
    card_message_id: int,
    ask_message_id: Optional[int],
    seller: str,
    card: Optional[Dict[str, Optional[str]]],
) -> None:
    """Hasanboydan javob kutilayotgan toʻlov kartasini DB state ga saqlaydi."""
    safe_ask_id = ask_message_id if isinstance(ask_message_id, int) else None
    payload = json.dumps(
        {
            "card_message_id": card_message_id,
            "ask_message_id": safe_ask_id,
            "seller": seller,
            "project": (card or {}).get("project") or "",
            "amount": (card or {}).get("amount") or "",
            "amount_uzs": parse_amount_uzs((card or {}).get("amount")),
            "status": "pending",
        },
        ensure_ascii=False,
    )
    await db.set_state(pending_intake_key(chat_id, card_message_id), payload)
    if safe_ask_id and safe_ask_id != card_message_id:
        await db.set_state(pending_intake_key(chat_id, safe_ask_id), payload)


def _build_note(intake: Dict[str, Any], reply_text: str) -> str:
    lines = [
        "Guruhdagi toʻlov kartasi asosida Oisha tomonidan kiritildi:",
        f"Sotuvchi: {intake.get('seller') or 'Hasanboy'}",
    ]
    if intake.get("project"):
        lines.append(f"Mijoz / Loyiha: {intake['project']}")
    if intake.get("amount"):
        lines.append(f"Summa: {intake['amount']}")
    lines.append("")
    lines.append("Sotuvchi javobi:")
    lines.append(reply_text.strip())
    return "\n".join(lines)


async def _create_won_lead_in_amocrm(
    amocrm: Any,
    *,
    lead_name: str,
    phone: Optional[str],
    price: int,
    note: str,
) -> Optional[int]:
    if phone:
        lead_id = await amocrm.create_lead(
            name=lead_name,
            phone=phone,
            price=price,
            pipeline_id=SALES_PIPELINE_ID,
            status_id=STATUS_WON_ID,
        )
        if lead_id:
            await asyncio.to_thread(amocrm.add_lead_note, int(lead_id), note)
        return int(lead_id) if lead_id else None

    lead_id = await amocrm.create_standalone_lead(
        name=lead_name,
        price=price,
        pipeline_id=SALES_PIPELINE_ID,
        status_id=STATUS_WON_ID,
        note=note,
    )
    return int(lead_id) if lead_id else None


async def handle_non_crm_client_info_reply(event: Any, send_as_oisha: Any) -> bool:
    """Hasanboyning mijoz maʼlumoti javobini oʻqib, amoCRMga Won bitim sifatida kiritadi."""
    text = (getattr(event.message, "message", None) or "").strip()
    if not text:
        return False

    reply_to_msg_id = getattr(event.message, "reply_to_msg_id", None)
    if not reply_to_msg_id:
        return False

    sender = await event.get_sender()
    if getattr(sender, "bot", False):
        return False

    db = app_ctx.msg_controller.db if app_ctx.msg_controller else None
    if not db:
        return False

    chat_id = int(event.chat_id)
    state_key = pending_intake_key(chat_id, int(reply_to_msg_id))
    raw_state = await db.get_state(state_key)
    if not raw_state:
        return False

    try:
        intake = json.loads(raw_state)
    except Exception:
        return False
    if intake.get("status") != "pending":
        return False

    amocrm = getattr(getattr(app_ctx.msg_controller, "crm", None), "amocrm", None)
    if not amocrm:
        logger.warning("[NON_CRM_INTAKE] amoCRM mavjud emas; bitim yaratilmadi.")
        return False

    project = intake.get("project") or ""
    client_name = extract_client_name(text, fallback=project or "Mijoz")
    lead_name = f"{client_name} — {project}" if project and project.lower() not in client_name.lower() else client_name
    phone = extract_phone(text)
    price = int(intake.get("amount_uzs") or 0)
    note = _build_note(intake, text)

    try:
        lead_id = await _create_won_lead_in_amocrm(
            amocrm, lead_name=lead_name, phone=phone, price=price, note=note
        )
    except Exception as exc:
        logger.error(f"[NON_CRM_INTAKE] amoCRM ga yozishda xato: {type(exc).__name__}")
        lead_id = None

    seller = intake.get("seller") or "@hasan_yahyo"
    if not lead_id:
        await send_as_oisha(
            chat_id,
            int(event.id),
            f"{seller}, maʼlumot qabul qilindi, lekin amoCRMga avtomatik kiritishda xatolik yuz berdi. Tekshirib qayta urinib koʻramiz.",
        )
        return True

    done_payload = json.dumps({**intake, "status": "created", "lead_id": lead_id}, ensure_ascii=False)
    await db.set_state(pending_intake_key(chat_id, int(intake["card_message_id"])), done_payload)
    if intake.get("ask_message_id"):
        await db.set_state(pending_intake_key(chat_id, int(intake["ask_message_id"])), done_payload)

    logger.info(f"[NON_CRM_INTAKE] amoCRM bitim yaratildi: lead_id={lead_id} chat={chat_id}")
    await send_as_oisha(
        chat_id,
        int(event.id),
        f"Rahmat, {seller}! ✅ Mijoz maʼlumotlari amoCRMga «Sotuv boʻldi» bosqichida kiritildi (bitim #{lead_id}).",
    )
    return True
