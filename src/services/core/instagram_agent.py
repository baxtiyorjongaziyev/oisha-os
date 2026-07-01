"""
Instagram / Meta Webhook Event Processor & Agent Core Service
"""
from __future__ import annotations

import hmac
import hashlib
import json
import re
import requests
import structlog
from typing import Dict, Any, Optional

from src.settings import settings
from src.agents.autonomous_sales_agent import AutonomousSalesAgent

logger = structlog.get_logger("InstagramAgent")


def verify_signature(payload: bytes, signature: str, app_secret: str) -> bool:
    """Verifies the SHA256 signature from Meta webhook requests."""
    if not app_secret:
        logger.warning("[META] APP_SECRET not set, signature verification skipped")
        return True

    if not signature:
        logger.warning("[META] Signature header missing")
        return False

    if signature.startswith("sha256="):
        signature = signature[7:]

    expected = hmac.new(
        app_secret.encode("utf-8"), payload, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


def send_ig_reply(recipient_id: str, text: str, access_token: str) -> bool:
    """Sends a Direct Message to the user using the Meta Graph API."""
    if not access_token:
        logger.warning("[META] PAGE_ACCESS_TOKEN not set, reply not sent")
        return False

    url = "https://graph.facebook.com/v19.0/me/messages"
    payload = {
        "recipient": {"id": recipient_id},
        "message": {"text": text}
    }
    headers = {"Content-Type": "application/json"}
    params = {"access_token": access_token}

    try:
        resp = requests.post(
            url, json=payload, headers=headers, params=params, timeout=10
        )
        if resp.status_code == 200:
            logger.info("[META] DM reply sent successfully", recipient_id=recipient_id)
            return True
        else:
            logger.error("[META] Failed to send DM reply", status_code=resp.status_code, body=resp.text)
            return False
    except Exception as exc:
        logger.error("[META] Exception in send_ig_reply", error=str(exc))
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


def notify_crm(source: str, user_name: str, user_id: str, message: str, reply: str) -> None:
    """Sends a notification message to the Telegram CRM group."""
    crm_group_id = settings.CRM_GROUP_ID
    bot_token = settings.BOT_TOKEN.get_secret_value() if settings.BOT_TOKEN else None

    if not crm_group_id or not bot_token:
        logger.warning("[CRM] CRM_GROUP_ID or BOT_TOKEN not configured, notification skipped")
        return

    # Analyze lead quality from tags
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


async def process_instagram_webhook(payload: dict, db) -> None:
    """Asynchronously processes entry events from Meta webhook payload."""
    if not payload:
        return

    access_token = settings.META_PAGE_ACCESS_TOKEN.get_secret_value() if settings.META_PAGE_ACCESS_TOKEN else ""

    for entry in payload.get("entry", []):
        # Direct Message Handling
        messaging = entry.get("messaging", [])
        if messaging:
            event = messaging[0]
            sender_id = event.get("sender", {}).get("id")
            message = event.get("message", {})
            text = message.get("text", "")

            if text and sender_id:
                user_id_str = f"ig_{sender_id}"
                logger.info("[META] Received Instagram DM", sender_id=sender_id, text=text[:50])

                # Log incoming message to DB
                await db.log_message(user_id_str, text, is_ai=False)

                # Query AI Agent
                agent = AutonomousSalesAgent(db=db)
                agent_result = await agent.handle_incoming(
                    user_id=user_id_str,
                    message=text,
                    autonomy_level="full"
                )
                ai_reply = agent_result.get("response", "Assalomu alaykum! Tez orada siz bilan bog'lanamiz. 😊")

                # Parse and save info tags
                info_updates = {}
                for m in re.finditer(r"\[SAVE_INFO:\s*(.*?)\]", ai_reply, re.IGNORECASE):
                    try:
                        parts = m.group(1).split("=", 1)
                        if len(parts) == 2:
                            info_updates[parts[0].strip().lower()] = parts[1].strip()
                    except Exception:
                        pass

                if info_updates:
                    await db.upsert_user(user_id_str, "Foydalanuvchi", **info_updates)

                # Clean reply tag decorators
                clean_reply = re.sub(r"\[.*?\]", "", ai_reply).strip()

                # Log outgoing AI reply
                await db.log_message(user_id_str, clean_reply, is_ai=True)

                # Send reply via Graph API
                send_ig_reply(sender_id, clean_reply, access_token)

                # Notify CRM Telegram Channel
                notify_crm("Instagram DM", "Foydalanuvchi", sender_id, text, ai_reply)

        # Comment / Page Feed Change Handling
        changes = entry.get("changes", [])
        for change in changes:
            value = change.get("value", {})
            comment_text = value.get("text", "")
            comment_id = value.get("id", "")
            from_obj = value.get("from", {})
            commenter_name = from_obj.get("name") or from_obj.get("username") or "Foydalanuvchi"
            commenter_id = from_obj.get("id", "")

            # Ignore webhook events triggered by our own replies to prevent infinite loops
            if comment_text and comment_id and commenter_id:
                user_id_str = f"ig_comment_{commenter_id}"
                logger.info("[META] Received Instagram Comment", commenter=commenter_name, text=comment_text[:50])

                # Log incoming comment
                await db.log_message(user_id_str, f"COMMENT: {comment_text}", is_ai=False)

                # Query AI Agent
                agent = AutonomousSalesAgent(db=db)
                agent_result = await agent.handle_incoming(
                    user_id=user_id_str,
                    message=f"Sharh yozdi: {comment_text}",
                    autonomy_level="full"
                )
                ai_reply = agent_result.get("response", "Rahmat! Tez orada javob beramiz. 😊")

                # Clean reply tag decorators
                clean_reply = re.sub(r"\[.*?\]", "", ai_reply).strip()

                # Log outgoing comment reply
                await db.log_message(user_id_str, clean_reply, is_ai=True)

                # Reply to comment via Graph API
                reply_to_comment(comment_id, clean_reply, access_token)

                # Notify CRM Telegram Channel
                notify_crm("Instagram Comment", commenter_name, commenter_id, comment_text, ai_reply)
