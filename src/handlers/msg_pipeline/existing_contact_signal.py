"""
Mavjud (allaqachon tanish/CRM'da bor) kontaktlar bilan DM suhbatidan CRM-relevant
signal aniqlash.

process_elite_intake faqat YANGI kontaktlar uchun ishlaydi (is_crm_synced=False).
Bu modul — allaqachon tanish odamlar (masalan hamkorlik/partnership muzokarasi
davom etayotgan kishilar) bilan suhbatda CRM harakati kerak bo'lgan lahzani AI
orqali aniqlab, "Biznes asisstant" guruhga tasdiqlash so'rovi yuboradi. Real CRM
yozuvi faqat owner tugmani bossagina amalga oshadi.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Optional

logger = logging.getLogger("OishaExistingContactSignal")

# "Biznes asisstant" guruhi — CRM signal va tasdiqlash so'rovlari shu yerga tushadi.
SIGNAL_GROUP_ID = -1003792973489

# sender_id -> {"sender_name", "summary", "suggested_action"}. Faqat process
# xotirasida — restart bo'lsa eski (hali tasdiqlanmagan) signal yo'qoladi, bu
# xavfsiz tomonga xato (aksincha, restart'dan keyin eski taklifni ko'r-ko'rona
# CRM'ga yozishdan ko'ra).
_PENDING_SIGNALS: dict[int, dict] = {}

_SIGNAL_PROMPT = """Sen Jon Branding agentligining CRM signal detektorisan.
Quyidagi Telegram DM xabarini o'qib, bu xabar CRM'da (AmoCRM) biror harakatni
talab qiladimi yo'qmi aniqla — masalan: narx kelishildi, hamkorlik/partnership
rasmiylashuvi boshlandi (hujjat, pechat, shartnoma), yangi bosqichga o'tish kerak,
yoki mijoz sovib ketyapti.

Faqat quyidagi JSON formatda javob ber, boshqa hech narsa yozma:
{{"has_signal": true/false, "summary": "qisqa xulosa (1-2 gap)", "suggested_action": "taklif qilinayotgan CRM harakati"}}

Xabar matni:
\"\"\"{text}\"\"\"
"""

_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


async def _ask_ai_for_signal(message_text: str) -> Optional[dict]:
    if not message_text or len(message_text.strip()) < 5:
        return None

    try:
        from src.settings import settings
        from google import genai
        from src.services.utils.gemini_failover.engine import generate_content_with_fallback

        gemini_key = settings.GEMINI_API_KEY
        api_key = gemini_key.get_secret_value() if hasattr(gemini_key, "get_secret_value") else str(gemini_key or "")
        if not api_key:
            return None

        client = genai.Client(api_key=api_key)
        response, _model_used = await generate_content_with_fallback(
            client,
            primary_model=getattr(settings, "GEMINI_CALL_MODEL", "gemini-2.5-flash"),
            contents=_SIGNAL_PROMPT.format(text=message_text[:2000]),
            log_prefix="[EXISTING_CONTACT_SIGNAL]",
        )
        raw_text = getattr(response, "text", "") or ""
        match = _JSON_RE.search(raw_text)
        if not match:
            return None
        return json.loads(match.group(0))
    except Exception as exc:
        logger.debug("[EXISTING_CONTACT_SIGNAL] AI baholash xatosi: %s", exc)
        return None


async def process_existing_contact_signal(
    event: Any,
    *,
    sender: Any,
    message_text: str,
    sender_name: str,
    msg_controller: Any,
    bot_client: Any,
) -> None:
    """Mavjud kontakt DM'sida CRM signal borligini AI orqali baholab, topilsa
    "Biznes asisstant" guruhga tasdiqlash so'rovi yuboradi."""
    if not bot_client:
        return

    verdict = await _ask_ai_for_signal(message_text)
    if not verdict or not verdict.get("has_signal"):
        return

    summary = str(verdict.get("summary") or "").strip()
    suggested_action = str(verdict.get("suggested_action") or "").strip()
    if not summary:
        return

    sender_id = getattr(sender, "id", None)
    username = getattr(sender, "username", None)
    username_label = f"@{username}" if username else str(sender_id or "noma'lum")

    from telethon.tl.custom import Button

    callback_data = f"exsig_confirm:{sender_id}".encode("utf-8")
    text = (
        "\U0001F514 CRM Signal\n\n"
        f"Kim: {sender_name} ({username_label})\n"
        f"Xulosa: {summary}\n"
        f"Taklif: {suggested_action or '-'}\n\n"
        f"Asl xabar: {message_text[:300]}"
    )

    if sender_id is not None:
        _PENDING_SIGNALS[int(sender_id)] = {
            "sender_name": sender_name,
            "username": username,
            "summary": summary,
            "suggested_action": suggested_action,
        }

    try:
        await bot_client.send_message(
            SIGNAL_GROUP_ID,
            text,
            buttons=[
                [
                    Button.inline("✅ Tasdiqlash", callback_data),
                    Button.inline("❌ Rad etish", b"exsig_reject"),
                ]
            ],
        )
        logger.info(
            "[EXISTING_CONTACT_SIGNAL] Signal yuborildi: sender=%s summary=%s",
            sender_id,
            summary,
        )
    except Exception as exc:
        logger.warning("[EXISTING_CONTACT_SIGNAL] Guruhga yuborishda xato: %s", exc)


async def confirm_existing_contact_signal(*, sender_id: int, msg_controller: Any) -> None:
    """Owner "Tasdiqlash" tugmasini bossa chaqiriladi — CRM'ga real yozadi.

    Voronka/pipeline ID hali ENV'dan sozlanmagan bo'lsa, oddiy lead sifatida
    (pipeline/status default) yaratadi va izohga taklif qilingan harakatni yozadi
    — owner keyin AmoCRM'da bosqichni qo'lda tanlaydi.
    """
    pending = _PENDING_SIGNALS.pop(sender_id, None)
    if not pending:
        logger.warning("[EXISTING_CONTACT_SIGNAL] Tasdiqlash uchun signal topilmadi: %s", sender_id)
        return

    import os

    crm_client = getattr(getattr(msg_controller, "crm", None), "amocrm", None)
    if crm_client is None:
        logger.warning("[EXISTING_CONTACT_SIGNAL] AmoCRM klient mavjud emas")
        return

    phone = None
    try:
        user_info = await msg_controller.db.get_user_info(sender_id)
        phone = user_info.get("phone") if user_info else None
    except Exception:
        logger.debug("[EXISTING_CONTACT_SIGNAL] Telefon topilmadi", exc_info=True)

    partnership_pipeline_id = os.getenv("AMOCRM_PARTNERSHIP_PIPELINE_ID")
    pipeline_id = int(partnership_pipeline_id) if partnership_pipeline_id else None

    note = (
        f"CRM Signal (avtomatik aniqlangan):\n{pending['summary']}\n\n"
        f"Taklif qilingan harakat: {pending['suggested_action']}"
    )

    lead_name = f"Partnership: {pending['sender_name']}"
    try:
        lead_id = await crm_client.create_lead(
            name=lead_name,
            phone=phone or "Raqam yo'q",
            pipeline_id=pipeline_id,
        )
        logger.info(
            "[EXISTING_CONTACT_SIGNAL] CRM lead yaratildi: sender=%s lead_id=%s note=%s",
            sender_id,
            lead_id,
            note,
        )
    except Exception as exc:
        logger.error("[EXISTING_CONTACT_SIGNAL] CRM yozish xatosi: %s", exc)
