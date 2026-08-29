"""
Lead qualification, opening criteria, and elite intake pipeline handler.
"""
import asyncio
import logging
import re
from typing import Any, Dict, Optional

from src.settings import settings
from src.context import app_ctx

logger = logging.getLogger("OishaLeadIntake")

_CONTACT_HINT_RE = re.compile(
    r"(\+998\s?\d{2}\s?\d{3}\s?\d{2}\s?\d{2}"  # +998 XX XXX XX XX
    r"|\+\d{1,3}\s?\d{6,14}"  # boshqa xalqaro format
    r"|\b\d{9,12}\b"  # ochiq yozilgan raqam
    r"|[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})"  # email
)

# Ochilmaydigan intent — AI hech qanday biznes signali ko'rmagan holat.
_NO_SIGNAL_INTENTS = {"NO_SIGNAL", "NONE", "SPAM", "IRRELEVANT"}


def should_open_lead(
    lead_data: Optional[dict],
    message_text: Optional[str],
    mode: str = "balanced",
) -> tuple[bool, str]:
    """
    AUTO_LEAD_MODE bo'yicha DM sdelka ochishga arziydimi, hal qilish.

    Qaytaradi: (ochilsinmi, sabab). Sabab log va CRM tegi uchun ishlatiladi.

    Bu funksiya faqat "signal yetarlimi" savoliga javob beradi. Kimni umuman
    ko'rmaslik kerakligi (oila papkasi, xodim, bot, allaqachon sinxronlangan)
    chaqiruvchi tomonda hal qilinadi va bu yerda qayta tekshirilmaydi.
    """
    normalized = (mode or "balanced").strip().lower()
    if normalized not in {"strict", "balanced", "all"}:
        logger.warning(
            "[LEAD-GATE] Noma'lum AUTO_LEAD_MODE=%r — 'balanced' ishlatiladi", mode
        )
        normalized = "balanced"

    data = lead_data or {}
    is_lead = bool(data.get("is_lead"))
    intent = str(data.get("intent_category") or "NO_SIGNAL").strip().upper()
    text = (message_text or "").strip()

    if normalized == "strict":
        return (is_lead, "is_lead" if is_lead else "strict_no_lead")

    if is_lead:
        return (True, "is_lead")

    # Mijoz o'zi telefon/email qoldirgan bo'lsa — bu eng kuchli signal,
    # AI tasnifi nima deganidan qat'i nazar sdelka ochiladi.
    if text and _CONTACT_HINT_RE.search(text):
        return (True, "contact_in_message")

    if normalized == "all":
        # Bo'sh yoki bir belgili xabar (stiker, "ok", emoji) sdelka ochmaydi.
        return (len(text) >= 2, "all_mode" if len(text) >= 2 else "empty_message")

    # balanced
    if intent not in _NO_SIGNAL_INTENTS:
        return (True, f"intent_{intent.lower()}")

    return (False, "no_signal")


async def process_elite_intake(
    event,
    *,
    sender,
    message_text: str,
    sender_name: str,
    msg_controller,
    auto_lead_agent,
    folder_manager,
    admin_bot,
    bot_client,
    welcome_manager,
    TN5_GROUP_ID,
) -> None:
    """
    Yangi DM xabarlarini tahlil qilish, lead aniqlash va CRM ga qo'shish.
    """
    from src.settings import settings as _settings

    lead_mode = getattr(_settings, "AUTO_LEAD_MODE", "balanced")

    lead_data = await auto_lead_agent.extract_lead_info(
        message_text, {"id": sender.id, "first_name": sender_name}
    )

    # strict rejimda AI javobisiz davom etmaymiz. balanced/all rejimda AI
    # ishlamay qolishi (kvota, timeout) mijozni yo'qotish sababi bo'lmasligi
    # kerak — bo'sh dict bilan davom etamiz va qolgan signallarga tayanamiz.
    if not lead_data:
        if str(lead_mode).strip().lower() == "strict":
            return
        lead_data = {}

    intent = lead_data.get("intent_category", "POTENTIAL")

    if folder_manager:
        asyncio.create_task(folder_manager.assign_to_folder(sender.id, intent))

    open_lead, gate_reason = should_open_lead(lead_data, message_text, lead_mode)
    if not open_lead:
        logger.info(
            "[ELITE INTAKE] Lead ochilmadi: %s mode=%s reason=%s",
            sender_name,
            lead_mode,
            gate_reason,
        )

    if open_lead and not await msg_controller.db.is_crm_synced(event.sender_id):
        logger.info(
            f"[ELITE INTAKE] Yangi lid aniqlandi: {sender_name} (Intent: {intent})"
        )

        intent_label_map = {
            "HOT_LEAD": "🔥 Qaynoq mijoz",
            "WARM_LEAD": "♨️ Issiq mijoz",
            "POTENTIAL": "🌱 Potensial mijoz",
        }
        intent_label = intent_label_map.get(intent, f"🔵 {intent}")

        await msg_controller.db.upsert_user(
            sender.id,
            sender_name,
            username=getattr(sender, "username", None),
            intent=intent,
            region=lead_data.get("city"),
            business_type=lead_data.get("activity"),
            brand_name=lead_data.get("brand_name"),
        )

        if intent == "HOT_LEAD" and admin_bot:
            draft_prompt = (
                f"Mijoz: {sender_name}\n"
                f"Xabar: {event.message.text}\n\n"
                "Baxtiyor aka nomidan ushbu mijozga do'stona, lekin professional javob loyihasini tayyorlang. "
                "Unga yordam berishga tayyorligimizni va loyihasini o'rganib chiqishimizni ayting."
            )
            draft = await msg_controller.db.analyze_text_with_ai(draft_prompt)
            await admin_bot.send_draft_for_approval(
                sender.id, sender_name, draft
            )

        phone = lead_data.get("phone")
        if not phone and sender:
            phone = getattr(sender, "phone", None)
            if not phone and bot_client:
                try:
                    full_user = await bot_client.get_entity(sender.id)
                    phone = getattr(full_user, "phone", None)
                    if phone:
                        logger.info(
                            "📞 [PHONE] Telethon orqali raqam olindi: %s", sender.id
                        )
                except Exception as exc:
                    logger.debug("[PHONE] Telethon get_entity xato: %s", exc)

        if not phone:
            phone = "Raqam yo'q"

        username = getattr(sender, "username", None)
        if not username and sender and bot_client:
            try:
                if "full_user" not in locals():
                    full_user = await bot_client.get_entity(sender.id)
                username = getattr(full_user, "username", None)
                if username:
                    logger.info(
                        "[USERNAME] Telethon orqali username olindi: @%s", username
                    )
            except Exception as exc:
                logger.debug("[USERNAME] Telethon get_entity xato: %s", exc)

        if not username:
            username = "Username yo'q"

        username_str = (
            f"@{username}" if username != "Username yo'q" else username
        )
        note_lines = [
            f"AI Tahlil: {lead_data.get('needs')}",
            f"Intent: {intent}",
            f"User: {username_str}",
            f"Telegram ID: {sender.id}",
            f"Manba: tg_auto ({lead_mode}/{gate_reason})",
        ]
        crm_sync = await msg_controller.crm.sync_lead(
            user_id=sender.id,
            name=f"DM Lead: {sender_name}",
            phone=phone,
            note="\n".join(note_lines),
        )
        if crm_sync.get("success"):
            await msg_controller.db.set_crm_synced(event.sender_id)

        await welcome_manager.send_welcome(event.sender_id)

        sync_line = (
            "✅ AmoCRM-ga saqlandi."
            if crm_sync.get("success")
            else f"⚠️ CRM sync xato: {crm_sync.get('error', 'nomaʼlum')}"
        )
        lead_notify_text = (
            f"👸 **Yangi Lid aniqlandi!**\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 **Ism:** {sender_name}\n"
            f"🔗 **Username:** {username_str}\n"
            f"📞 **Raqam:** {phone}\n"
            f"🎯 **Holat:** {intent_label}\n"
            f"💬 **Xabar:** {(message_text or '')[:200]}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"{sync_line}"
        )
        if admin_bot:
            await admin_bot.notify_lead(lead_notify_text)

        if intent == "HOT_LEAD" and bot_client and TN5_GROUP_ID:
            try:
                await bot_client.send_message(
                    TN5_GROUP_ID, lead_notify_text, parse_mode="md"
                )
                logger.info(f"[HOT LEAD] CRM guruhiga yuborildi: {sender_name}")
            except Exception as crm_notif_err:
                logger.warning(
                    f"[HOT LEAD] CRM guruh notif xato: {crm_notif_err}"
                )
