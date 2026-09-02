"""
Instagram / Meta Webhook Event Processor & Agent Core Service
"""
from __future__ import annotations

import hashlib
import hmac
import re
from typing import Any, Optional
import requests
import structlog

from src.settings import settings
from src.agents.autonomous_sales_agent import AutonomousSalesAgent
from src.services.core.instagram.graph_client import InstagramGraphClient
from src.services.core.instagram.backfill import backfill_unanswered_comments
from src.services.core.instagram.lead_qualifier import (
    should_trigger_dm,
    generate_initial_dm_message,
)

logger = structlog.get_logger("InstagramAgent")

COMMENT_REPLY_SYSTEM = (
    "Sen Oisha — Baxtiyorjon Gaziyevning shaxsiy Instagram sahifasini yurituvchi "
    "aqlli hamrohisiz. Baxtiyorjon — brending bo'yicha ekspert va art-direktor. Sahifa mazmuni: "
    "brending, nomlash (naming), logo dizayn, keyslar va ijodiy strategiya.\n"
    "Qoidalar:\n"
    "- 1-shaxsdan yozma — Baxtiyorjon ovozida (iliq, ishonchli, samimiy) javob ber.\n"
    "- 'Jon Branding' nomini shaxsiy sahifada ishlatma, shaxsiy ekspert brendi sifatida gapir.\n"
    "- BIR XIL NOMNI HAMMAGA BERMA: Agar foydalanuvchi nom/g'oya so'rasa, har biriga "
    "alohida, o'ziga xos, zamonaviy va jarangdor yangi nom taklif qil.\n"
    "- Agar izohda 'nom', 'brend', 'logo', 'narx', 'xizmat' yoki videoda aytilgan kalit so'z bo'lsa, "
    "izohga qisqa ijodiy javob berib: 'Batafsil ma'lumot va savollarni Direct (DM)ingizga yubordim 📩' deb qo'sh.\n"
    "- O'zbekcha, 1-2 gap. Emoji 1 ta.\n"
    "- Shablon javob YOZMA ('Rahmat! Tez orada javob beramiz' taqiqlanadi)."
)

__all__ = [
    "InstagramGraphClient",
    "verify_signature",
    "send_ig_reply",
    "send_ig_private_reply",
    "like_comment",
    "reply_to_comment",
    "fetch_media_caption",
    "generate_comment_reply",
    "backfill_unanswered_comments",
    "notify_crm",
    "process_instagram_webhook",
]


def verify_signature(payload: Any, signature: str, app_secret: Optional[str] = None) -> bool:
    """Verifies the SHA256 signature from Meta webhook requests."""
    secret = app_secret
    if secret is None:
        secret = settings.META_APP_SECRET.get_secret_value() if settings.META_APP_SECRET else ""

    if not secret:
        logger.warning("[META] APP_SECRET not set, signature verification skipped")
        return True

    if not signature:
        logger.warning("[META] Signature header missing")
        return False

    if signature.startswith("sha256="):
        signature = signature[7:]

    if isinstance(payload, bytes):
        payload_bytes = payload
    elif isinstance(payload, str):
        payload_bytes = payload.encode("utf-8")
    else:
        import json
        payload_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")

    expected = hmac.new(
        secret.encode("utf-8"), payload_bytes, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


def _send_ig_message(recipient_payload: dict, text: str, access_token: str, log_tag: str) -> bool:
    if not access_token or not recipient_payload:
        logger.warning("[META] %s skipped: access_token or recipient missing", log_tag)
        return False
    url = "https://graph.facebook.com/v19.0/me/messages"
    try:
        resp = requests.post(
            url,
            json={"recipient": recipient_payload, "message": {"text": text}},
            headers={"Content-Type": "application/json"},
            params={"access_token": access_token},
            timeout=15,
        )
        if resp.status_code == 200:
            logger.info("[META] %s sent successfully", log_tag)
            return True
        logger.error("[META] %s failed", log_tag, status_code=resp.status_code, body=resp.text)
    except Exception as exc:
        logger.error("[META] %s exception", log_tag, error=str(exc))
    return False


def send_ig_reply(recipient_id: str, text: str, access_token: str) -> bool:
    """Sends a Direct Message to the user using the Meta Graph API."""
    return _send_ig_message({"id": recipient_id}, text, access_token, f"DM to {recipient_id}")


def send_ig_private_reply(comment_id: str, text: str, access_token: str) -> bool:
    """Sends a Private Direct Message in response to an Instagram comment."""
    return _send_ig_message({"comment_id": comment_id}, text, access_token, f"Private DM on comment {comment_id}")


def like_comment(comment_id: str, access_token: str) -> bool:
    """Likes a comment on Instagram via Graph API."""
    if not access_token:
        logger.warning("[META] PAGE_ACCESS_TOKEN not set, comment like not sent")
        return False

    url = f"https://graph.facebook.com/v19.0/{comment_id}/likes"
    params = {"access_token": access_token}

    try:
        resp = requests.post(url, params=params, timeout=10)
        if resp.status_code == 200:
            logger.info("[META] Comment liked successfully", comment_id=comment_id)
            return True
        else:
            logger.error("[META] Failed to like comment", status_code=resp.status_code, body=resp.text)
            return False
    except Exception as exc:
        logger.error("[META] Exception in like_comment", error=str(exc))
        return False


def reply_to_comment(comment_id: str, text: str, access_token: str) -> bool:
    """Replies to a comment on Instagram."""
    if not access_token:
        logger.warning("[META] PAGE_ACCESS_TOKEN not set, comment reply not sent")
        return False

    url = f"https://graph.facebook.com/v19.0/{comment_id}/replies"
    params = {
        "message": text,
        "access_token": access_token
    }

    try:
        resp = requests.post(url, params=params, timeout=10)
        if resp.status_code == 200:
            logger.info("[META] Comment reply sent successfully", comment_id=comment_id)
            return True
        else:
            logger.error("[META] Failed to send comment reply", status_code=resp.status_code, body=resp.text)
            return False
    except Exception as exc:
        logger.error("[META] Exception in reply_to_comment", error=str(exc))
        return False


def fetch_media_caption(media_id: str, access_token: str) -> str:
    """Fetches the caption of the post a comment belongs to (for reply context)."""
    if not media_id or not access_token:
        return ""
    url = f"https://graph.facebook.com/v19.0/{media_id}"
    params = {"fields": "caption", "access_token": access_token}
    try:
        resp = requests.get(url, params=params, timeout=10)
        if resp.status_code == 200:
            return resp.json().get("caption", "") or ""
        logger.warning("[META] Failed to fetch media caption", status_code=resp.status_code)
    except Exception as exc:
        logger.error("[META] Exception in fetch_media_caption", error=str(exc))
    return ""


async def generate_comment_reply(comment_text: str, post_caption: str = "", commenter_name: str = "") -> str:
    """Context-aware reply to an Instagram comment using the free-AI router."""
    caption_block = f'\nPost matni: "{post_caption[:500]}"' if post_caption else ""
    prompt = (
        f"{caption_block}\n"
        f'{commenter_name} yozgan izoh: "{comment_text}"\n\n'
        f"Shu izohga Oisha nomidan javob yoz:"
    )
    try:
        from src.services.utils.free_ai_router import get_free_ai_router
        result = await get_free_ai_router().generate_text(
            prompt,
            system=COMMENT_REPLY_SYSTEM,
            max_tokens=200,
            temperature=0.6,
        )
        reply = (result.text or "").strip().strip('"')
        if reply:
            return reply
    except Exception as exc:
        logger.warning("[META] generate_comment_reply fallback: %s", exc)
    return "Izohingiz uchun rahmat! 🙌"


def notify_crm(source: str, user_name: str, user_id: str, message: str, reply: str) -> None:
    """Sends a notification message to the Telegram CRM group."""
    crm_group_id = settings.CRM_GROUP_ID
    bot_token = settings.BOT_TOKEN.get_secret_value() if settings.BOT_TOKEN else None

    if not crm_group_id or not bot_token:
        logger.warning("[CRM] CRM_GROUP_ID or BOT_TOKEN not configured, notification skipped")
        return

    quality = "Oddiy ✅"
    if "quality=sifatli" in reply.lower():
        quality = "Sifatli 💎"

    clean_reply = re.sub(r"\[.*?\]", "", reply).strip()

    crm_msg = (
        f"📱 <b>YANGI {source.upper()} LEAD!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 <b>Foydalanuvchi:</b> {user_name}\n"
        f"🆔 <b>ID:</b> <code>{user_id}</code>\n"
        f"💎 <b>Sifati:</b> {quality}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"💬 <b>Xabar:</b> <i>{message[:300]}</i>\n"
        f"🤖 <b>Oisha Javobi:</b> <i>{clean_reply[:300]}</i>\n"
    )

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": crm_group_id,
        "text": crm_msg,
        "parse_mode": "HTML"
    }
    if settings.CRM_TOPIC_ID is not None:
        payload["message_thread_id"] = settings.CRM_TOPIC_ID

    try:
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code != 200:
            logger.error("[CRM] Failed to notify CRM", status_code=resp.status_code, body=resp.text)
    except Exception as exc:
        logger.error("[CRM] Exception in notify_crm", error=str(exc))


async def process_instagram_webhook(payload: dict, db: Optional[Any] = None) -> None:
    """Asynchronously processes entry events from Meta webhook payload."""
    if not payload:
        return

    if db is None:
        try:
            from src.api.routes.state import api_state
            db = api_state.db_instance
        except Exception:
            db = None

    access_token = settings.META_PAGE_ACCESS_TOKEN.get_secret_value() if settings.META_PAGE_ACCESS_TOKEN else ""
    my_ig_id = (
        getattr(settings, "META_INSTAGRAM_USER_ID", None)
        or getattr(settings, "META_INSTAGRAM_ACCOUNT_ID", None)
        or ""
    )

    for entry in payload.get("entry", []):
        entry_id = str(entry.get("id") or "")

        # Direct Message Handling
        messaging = entry.get("messaging", [])
        if messaging:
            event = messaging[0]
            sender_id = str(event.get("sender", {}).get("id") or "")
            message = event.get("message", {})
            text = message.get("text", "")

            if my_ig_id and sender_id == str(my_ig_id):
                logger.info("[META] Skipping own DM (loop protection)", sender_id=sender_id)
                continue

            if text and sender_id:
                user_id_str = f"ig_{sender_id}"
                logger.info("[META] Received Instagram DM", sender_id=sender_id, text=text[:50])

                if db:
                    await db.log_message(user_id_str, text, is_ai=False)

                agent = AutonomousSalesAgent(db=db)
                agent_result = await agent.handle_incoming(
                    user_id=user_id_str,
                    message=text,
                    autonomy_level="full"
                )
                ai_reply = agent_result.get("response", "Assalomu alaykum! Tez orada siz bilan bog'lanamiz. 😊")

                info_updates = {}
                for m in re.finditer(r"\[SAVE_INFO:\s*(.*?)\]", ai_reply, re.IGNORECASE):
                    try:
                        parts = m.group(1).split("=", 1)
                        if len(parts) == 2:
                            info_updates[parts[0].strip().lower()] = parts[1].strip()
                    except Exception as exc:
                        logger.debug("[META] Parse SAVE_INFO tag: %s", exc)

                if info_updates and db:
                    await db.upsert_user(user_id_str, "Foydalanuvchi", **info_updates)

                clean_reply = re.sub(r"\[.*?\]", "", ai_reply).strip()

                if db:
                    await db.log_message(user_id_str, clean_reply, is_ai=True)

                # Automatic Lead Creation in AmoCRM for Qualified leads
                phone_num = info_updates.get("phone", "")
                if phone_num or "quality=sifatli" in ai_reply.lower():
                    from src.services.core.instagram.lead_qualifier import sync_lead_to_amocrm
                    sync_lead_to_amocrm(
                        name=info_updates.get("name", "Instagram Mijoz"),
                        phone=phone_num,
                        lead_name=f"Instagram DM: {info_updates.get('name', sender_id)}",
                        details=f"Mijoz: {text}\nOisha: {clean_reply}",
                    )

                send_ig_reply(sender_id, clean_reply, access_token)
                notify_crm("Instagram DM", "Foydalanuvchi", sender_id, text, ai_reply)

        # Comment / Page Feed Change Handling
        changes = entry.get("changes", [])
        for change in changes:
            field = change.get("field")
            if field and field != "comments":
                continue

            value = change.get("value", {})
            verb = value.get("verb")
            if verb and verb != "add":
                continue

            from_obj = value.get("from", {})
            commenter_id = str(from_obj.get("id") or "")
            commenter_name = from_obj.get("name") or from_obj.get("username") or "Foydalanuvchi"
            comment_text = value.get("text") or value.get("message") or ""
            comment_id = str(value.get("id") or value.get("comment_id") or "")

            if my_ig_id and commenter_id == str(my_ig_id):
                logger.info("[META] Skipping own comment (loop protection)", commenter_id=commenter_id)
                continue

            if entry_id and commenter_id == entry_id:
                logger.info("[META] Skipping page own comment (loop protection)", commenter_id=commenter_id)
                continue

            if comment_text and comment_id and commenter_id:
                user_id_str = f"ig_comment_{commenter_id}"
                logger.info("[META] Received Instagram Comment", commenter=commenter_name, text=comment_text[:50])

                if db:
                    await db.log_message(user_id_str, f"COMMENT: {comment_text}", is_ai=False)

                media_id = str((value.get("media") or {}).get("id") or "")
                post_caption = fetch_media_caption(media_id, access_token) if media_id else ""

                ai_reply = await generate_comment_reply(
                    comment_text=comment_text,
                    post_caption=post_caption,
                    commenter_name=commenter_name,
                )

                clean_reply = re.sub(r"\[.*?\]", "", ai_reply).strip()

                if db:
                    await db.log_message(user_id_str, clean_reply, is_ai=True)

                reply_to_comment(comment_id, clean_reply, access_token)
                
                # Check for Lead Keyword triggers and initiate Direct Message
                is_trigger, kw = should_trigger_dm(comment_text, post_caption)
                if is_trigger:
                    initial_dm = generate_initial_dm_message(commenter_name, kw, post_caption)
                    send_ig_private_reply(comment_id, initial_dm, access_token)
                    if db:
                        dm_uid = f"ig_{commenter_id}"
                        await db.log_message(dm_uid, initial_dm, is_ai=True)

                notify_crm("Instagram Comment", commenter_name, commenter_id, comment_text, ai_reply)
