"""
Oisha-OS WhatsApp Handler

WhatsApp Gateway (Baileys) dan keladigan webhooklarni qayta ishlaydi
va Oisha-OS orqali WhatsApp ga xabar yuborish imkonini beradi.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

import aiohttp
from src.settings import settings

logger = logging.getLogger(__name__)


def _get_wa_gateway_url() -> str:
    return getattr(settings, "WHATSAPP_GATEWAY_URL", "http://localhost:3001")


def _get_wa_secret() -> str:
    s = getattr(settings, "OISHA_WHATSAPP_SECRET", "secret")
    return s.get_secret_value() if hasattr(s, "get_secret_value") else str(s)


async def send_whatsapp_message(phone: str, text: str, image_url: Optional[str] = None) -> bool:
    """
    WhatsApp Gateway orqali mijozga xabar yuboradi.
    
    Args:
        phone: Telefon raqami (xalqaro format, masalan: 998901234567)
        text: Xabar matni
        image_url: Rasm URL (ixtiyoriy)
    
    Returns:
        True - muvaffaqiyatli yuborilgan, False - xatolik
    """
    gateway_url = _get_wa_gateway_url()
    secret = _get_wa_secret()
    
    payload: dict = {"phone": phone, "text": text}
    if image_url:
        payload["image_url"] = image_url

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{gateway_url}/send",
                json=payload,
                headers={"X-Oisha-Secret": secret},
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                if resp.status == 200:
                    logger.info(f"WhatsApp xabari yuborildi: {phone}")
                    return True
                elif resp.status == 503:
                    logger.warning("WhatsApp Gateway ga ulanmagan (QR kerak bo'lishi mumkin)")
                    return False
                else:
                    body = await resp.text()
                    logger.error(f"WhatsApp Gateway xatolik {resp.status}: {body[:200]}")
                    return False
    except Exception as e:
        logger.error(f"WhatsApp yuborishda xatolik: {e}")
        return False


async def get_whatsapp_status() -> dict:
    """Gateway holati: ulangan yoki yo'q."""
    gateway_url = _get_wa_gateway_url()
    secret = _get_wa_secret()
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{gateway_url}/status",
                headers={"X-Oisha-Secret": secret},
                timeout=aiohttp.ClientTimeout(total=5),
            ) as resp:
                if resp.status == 200:
                    return await resp.json()
    except Exception:
        logger.error("Exception handled in %s", __name__, exc_info=True)
    return {"connected": False, "phone": None}


async def handle_whatsapp_webhook(data: dict, bot=None) -> None:
    """
    WhatsApp Gateway dan kelgan kiruvchi xabarni qayta ishlash.
    
    Xabar oqimi:
    Mijoz WA -> Baileys Gateway -> POST /webhook/whatsapp -> shu funksiya
    -> Oisha NegotiationEngine / AmoCRM log
    """
    phone: str = data.get("phone", "")
    name: str = data.get("name", "Noma'lum")
    text: str = data.get("text", "")
    source: str = data.get("source", "whatsapp")

    if not phone or not text:
        logger.warning(f"Noto'liq WhatsApp webhook: {data}")
        return

    logger.info(f"WhatsApp kiruvchi xabar | {name} ({phone}): {text[:80]}")

    try:
        # AmoCRM da kontakt va leadni topib, izoh (note) qo'shish
        from src.context import app_ctx
        amocrm = getattr(app_ctx, "amocrm", None)
        if amocrm:
            contact = amocrm.get_contact_by_phone(phone)
            if contact:
                leads = amocrm.get_active_leads_for_contact(contact["id"])
                if leads:
                    lead = leads[0]
                    # AmoCRM ga WhatsApp xabarini note sifatida qo'shish
                    await amocrm.add_note(
                        entity_id=lead["id"],
                        entity_type="leads",
                        note_type=4,  # COMMON note
                        text=f"📱 WhatsApp ({name}): {text}",
                    )
                    logger.info(f"AmoCRM lead #{lead['id']} ga WhatsApp xabari note qilindi")
            else:
                logger.info(f"AmoCRM da kontakt topilmadi: {phone}")
    except Exception as e:
        logger.error(f"WhatsApp -> AmoCRM log xatoligi: {e}")
