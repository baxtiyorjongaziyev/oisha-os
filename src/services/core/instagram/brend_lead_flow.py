"""
Brend Video Lead Flow & Customer 360 Pipeline.
Handles comment triggers, humanized DM qualification, amoCRM sync,
and 360-degree customer profiling for Instagram leads.
"""
from __future__ import annotations

import os
import re
import random
import logging
from typing import Any, Dict, List, Optional

import structlog

from src.settings import settings
from src.services.core.instagram.agent_constants import (
    TARGET_BREND_VIDEO_SHORTCODE,
    TARGET_BREND_VIDEO_PERMALINK,
    BREND_COMMENT_DM_TEMPLATE,
    BREND_COMMENT_PUBLIC_REPLIES,
    get_public_ack_for_comment,
)
from src.services.core.instagram.api_helpers import (
    send_ig_message_payload,
    send_ig_reply,
    send_ig_private_reply,
    like_comment,
    reply_to_comment,
)

from src.services.core.instagram.comment_store import InstagramCommentStore

logger = structlog.get_logger("BrendLeadFlow")


def is_brend_keyword(text: str) -> bool:
    """Checks if the text contains the target keyword 'Brend' (or variations)."""
    lowered = (text or "").lower()
    return any(k in lowered for k in ("brend", "brand", "birend", "бренд"))


def format_customer_360_alert(profile: Any, brand_name: str = "", industry: str = "") -> str:
    """Formats a concise 360-degree customer briefing for Telegram CRM notification."""
    phone_display = profile.phone or "Noma'lum"
    lines = [
        "🎯 <b>Instagram 'Brend' Lidi — 360° Tahlil</b>",
        f"👤 <b>Mijoz:</b> {profile.name} (@{profile.instagram_handle or 'direct'})",
        f"📞 <b>Telefon:</b> {phone_display}",
    ]
    if brand_name:
        lines.append(f"🏢 <b>Brend nomi:</b> {brand_name}")
    if industry:
        lines.append(f"🏷 <b>Faoliyat sohasi:</b> {industry}")

    # AmoCRM ma'lumotlari
    if profile.amocrm_lead_id:
        status_text = profile.amocrm_status or "Yangi"
        if profile.amocrm_budget:
            lines.append(f"📊 <b>AmoCRM:</b> #{profile.amocrm_lead_id} — {status_text} ({profile.amocrm_budget:,} so'm)")
        else:
            lines.append(f"📊 <b>AmoCRM:</b> #{profile.amocrm_lead_id} — {status_text}")
        if profile.responsible_manager:
            lines.append(f"👨‍💼 <b>Mas'ul menejer:</b> {profile.responsible_manager}")
    else:
        lines.append("📊 <b>AmoCRM:</b> Avval murojaat qilmagan (Yangi lid yaratildi)")

    # Telegram ma'lumotlari
    if profile.telegram_username or profile.telegram_messages:
        t_user = f"@{profile.telegram_username}" if profile.telegram_username else "Topildi"
        lines.append(f"💬 <b>Telegram:</b> {t_user} ({len(profile.telegram_messages)} ta xabar tarixi)")
    else:
        lines.append("💬 <b>Telegram:</b> Yozishmalar tarixi mavjud emas")

    # Airtable ma'lumotlari
    if profile.airtable_project_name:
        lines.append(
            f"🎨 <b>Airtable:</b> {profile.airtable_project_name} "
            f"(Status: {profile.airtable_phase}, Qarz: {profile.airtable_debt})"
        )

    lines.append(f"📌 <b>Manba:</b> Instagram Video (<code>{TARGET_BREND_VIDEO_SHORTCODE}</code>)")
    return "\n".join(lines)


def _claim_brend_comment(store: InstagramCommentStore, cid: str, mid: str, uid: str, name: str, text: str) -> bool:
    if store.is_comment_processed(cid):
        logger.info("[BREND-FLOW] Comment already processed", comment_id=cid)
        return False
    if store.has_user_received_dm(uid, name, mid):
        logger.info("[BREND-FLOW] User already received DM", user=name, uid=uid)
        store.record_skipped(cid, mid, uid, name, text, "duplicate_user")
        return False
    return store.claim_comment(cid, mid, uid, name, text, "brend")


async def handle_brend_comment_trigger(
    comment_id: str,
    comment_text: str,
    commenter_name: str,
    commenter_id: str,
    access_token: str,
    media_id: str = "",
    db: Any = None,
    store: Optional[InstagramCommentStore] = None,
) -> bool:
    """Handles a comment matching the 'Brend' keyword."""
    if not is_brend_keyword(comment_text):
        return False

    store = store or InstagramCommentStore()
    cid, mid = str(comment_id).strip(), str(media_id or TARGET_BREND_VIDEO_SHORTCODE)
    if not _claim_brend_comment(store, cid, mid, commenter_id, commenter_name, comment_text):
        return False

    logger.info("[BREND-FLOW] Triggered for comment", comment_id=cid, commenter=commenter_name)
    like_comment(cid, access_token)
    dm_sent = send_ig_private_reply(cid, BREND_COMMENT_DM_TEMPLATE, access_token)
    if not dm_sent:
        store.record_failure(cid, "private_reply_failed")
        return False

    public_ack = get_public_ack_for_comment(comment_text)
    reply_to_comment(cid, public_ack, access_token)
    store.record_dm_success(cid, mid, commenter_id, commenter_name, BREND_COMMENT_DM_TEMPLATE, public_ack)
    if db:
        uid = f"ig_{commenter_id}"
        await db.log_message(uid, f"COMMENT: {comment_text}", is_ai=False)
        await db.log_message(uid, BREND_COMMENT_DM_TEMPLATE, is_ai=True)
    return True


async def handle_need_comment_trigger(
    comment_id: str,
    comment_text: str,
    commenter_name: str,
    commenter_id: str,
    access_token: str,
    media_id: str = "",
    post_caption: str = "",
    db: Any = None,
    store: Optional[InstagramCommentStore] = None,
) -> bool:
    """Detects any service question/need and moves the commenter to 1-on-1 DM."""
    from src.services.core.instagram.lead_qualifier import (
        should_trigger_dm,
        generate_initial_dm_message_ai,
    )
    is_triggered, reason = should_trigger_dm(comment_text, post_caption)
    if not is_triggered:
        return False

    store = store or InstagramCommentStore()
    cid, mid = str(comment_id).strip(), str(media_id or TARGET_BREND_VIDEO_SHORTCODE)
    if not _claim_brend_comment(store, cid, mid, commenter_id, commenter_name, comment_text):
        return False

    logger.info("[NEED-FLOW] Triggered DM for question/need", comment_id=cid, commenter=commenter_name, reason=reason)
    like_comment(cid, access_token)
    dm_text = await generate_initial_dm_message_ai(commenter_name, comment_text, keyword=reason, caption=post_caption)
    dm_sent = send_ig_private_reply(cid, dm_text, access_token)
    if not dm_sent:
        store.record_failure(cid, "private_reply_failed")
        return False

    public_ack = get_public_ack_for_comment(comment_text)
    reply_to_comment(cid, public_ack, access_token)
    store.record_dm_success(cid, mid, commenter_id, commenter_name, dm_text, public_ack)
    if db:
        uid = f"ig_{commenter_id}"
        await db.log_message(uid, f"COMMENT: {comment_text}", is_ai=False)
        await db.log_message(uid, dm_text, is_ai=True)
    return True


async def _sync_brend_lead_360(
    sender_id: str,
    commenter_name: str,
    phone: str,
    brand: str,
    industry: str,
) -> Any:
    from src.services.core.instagram.lead_qualifier import sync_lead_to_amocrm
    lead_title = f"Instagram Brend: {brand or commenter_name or 'Lid'}"
    details = (
        f"Brend nomi: {brand or 'Aniqlanmoqda'}\n"
        f"Faoliyat sohasi: {industry or 'Aniqlanmoqda'}\n"
        f"Instagram: @{commenter_name} (ID: {sender_id})\n"
        f"Post: {TARGET_BREND_VIDEO_PERMALINK}"
    )
    sync_lead_to_amocrm(commenter_name or "Instagram Mijoz", phone, lead_title, details, "Instagram Brend Video")
    try:
        from src.services.customer_360.collector import Customer360Collector
        collector = Customer360Collector()
        profile_360 = await collector.collect_profile(phone, phone=phone, name=commenter_name)
        profile_360.instagram_handle = commenter_name
        return profile_360
    except Exception as exc:
        logger.warning("[BREND-FLOW] 360 collection error: %s", exc)
        return None


def _extract_phone_number(text: str) -> str:
    """Extracts an Uzbek or international phone number from free text if present."""
    match = re.search(r"(?:\+?998[\s\-()]*)?\d{2}[\s\-()]*\d{3}[\s\-]*\d{2}[\s\-]*\d{2}", text or "")
    if not match:
        return ""
    digits = re.sub(r"\D", "", match.group(0))
    if len(digits) == 9:
        return f"+998{digits}"
    if len(digits) == 12 and digits.startswith("998"):
        return f"+{digits}"
    return match.group(0).strip()


async def process_brend_dm_conversation(
    sender_id: str,
    user_message: str,
    history: List[Dict[str, str]],
    commenter_name: str,
    access_token: str,
    db: Any = None,
    is_brend_lead: bool = False,
) -> Dict[str, Any]:
    """Processes ongoing DM dialogue with human-like qualification and 360 profiling."""
    from src.services.core.instagram.lead_qualifier import generate_qualifying_dm_response

    ai_reply = await generate_qualifying_dm_response(user_message, history, commenter_name)
    info_updates: Dict[str, str] = {}
    for m in re.finditer(r"\[SAVE_INFO:\s*([^\[\]]+)\]", ai_reply, re.IGNORECASE):
        parts = m.group(1).split("=", 1)
        if len(parts) == 2:
            info_updates[parts[0].strip().lower()] = parts[1].strip()

    if not info_updates.get("phone"):
        fallback_phone = _extract_phone_number(user_message)
        if fallback_phone:
            info_updates["phone"] = fallback_phone

    clean_reply = re.sub(r"\[[A-Z0-9_]+:[^\]]+\]", "", ai_reply).strip()
    sent = send_ig_reply(sender_id, clean_reply, access_token) if access_token else False
    user_id_str = f"ig_{sender_id}"
    if db:
        await db.log_message(user_id_str, clean_reply, is_ai=True)
        if info_updates:
            await db.upsert_user(user_id_str, commenter_name or "Foydalanuvchi", **info_updates)

    extracted_phone = info_updates.get("phone", "")
    profile_360 = None
    if is_brend_lead and extracted_phone:
        profile_360 = await _sync_brend_lead_360(
            sender_id=sender_id,
            commenter_name=commenter_name,
            phone=extracted_phone,
            brand=info_updates.get("brand", ""),
            industry=info_updates.get("industry", ""),
        )

    return {"reply": clean_reply, "raw_reply": ai_reply, "sent": sent, "info": info_updates, "profile_360": profile_360}


def get_brend_followup_message(stage: int = 1, brand_name: str = "", industry: str = "") -> str:
    """Returns a natural, non-pushy follow-up message."""
    if stage == 1:
        # User didn't answer opener
        return random.choice([
            "Assalomu alaykum! Loyihangiz bo'yicha maslahatlashib olishga vaqtingiz bo'ldimi? Savollaringiz bo'lsa, bemalol bering, batafsil tushuntirib beraman 😊",
            "Assalomu alaykum! Yangi brendingiz bo'yicha gaplashib olish uchun qulay vaqtingiz bo'lsa, bemalol yozing 🤝",
        ])
    # User gave brand/industry but didn't provide phone number
    target = brand_name or industry or "loyiha"
    return (
        f"Assalomu alaykum! {target} yo'nalishida o'xshash bir nechta chiroyli keyslarimiz va tavsiyalarimiz bor edi. "
        "Ko'rib chiqishingiz uchun qaysi raqamingizga (Telegramga) tashlab beray? 🤝"
    )
