"""
Instagram / Meta Webhook Event Processor & Agent Core Service
"""
from __future__ import annotations

import hashlib
import hmac
import html
import os
import re
import time
from collections import defaultdict, deque
from typing import Any, Dict, Optional
import requests
import structlog

from src.settings import settings
from src.services.core.instagram.graph_client import InstagramGraphClient
from src.services.core.instagram.backfill import (
    backfill_unanswered_comments,
    _contains_sensitive_terms,
)
from src.time_utils import get_local_now, is_quiet_hours
from src.services.core.instagram.api_helpers import (
    send_ig_message_payload,
    like_comment,
    reply_to_comment,
    fetch_media_caption,
)

logger = structlog.get_logger("InstagramAgent")

from src.services.core.instagram.agent_constants import (
    COMMENT_REPLY_SYSTEM,
    COMMENT_KEYWORD_AUTOMATIONS,
    KEYWORD_AUTOMATION_PUBLIC_ACK,
    FALLBACK_COMMENT_REPLIES,
    match_comment_keyword_automation as _match_comment_keyword_automation,
)
from src.services.core.instagram.webhook_verifier import verify_signature

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


def send_ig_reply(recipient_id: str, text: str, access_token: str) -> bool:
    """Sends a Direct Message to the user using the Meta Graph API."""
    return send_ig_message_payload({"id": recipient_id}, text, access_token, f"DM to {recipient_id}")


def send_ig_private_reply(comment_id: str, text: str, access_token: str) -> bool:
    """Sends a Private Direct Message in response to an Instagram comment."""
    return send_ig_message_payload({"comment_id": comment_id}, text, access_token, f"Private DM on comment {comment_id}")


async def generate_comment_reply(comment_text: str, post_caption: str = "", commenter_name: str = "") -> str:
    """Context-aware reply to an Instagram comment using the free-AI router.
    Evaluates video description and comment intent. Pure emojis get mirrored.
    """
    from src.services.core.instagram.emoji_utils import get_mirror_emoji_reply
    emoji_mirror = get_mirror_emoji_reply(comment_text)
    if emoji_mirror:
        return emoji_mirror

    caption_block = f'Video/Reels matni (caption):\n"{post_caption[:1000]}"\n\n' if post_caption else ""
    user_label = f"@{commenter_name}" if commenter_name else "Foydalanuvchi"
    prompt = (
        f"{caption_block}"
        f'{user_label} izohi: "{comment_text}"\n\n'
        f"Vazifa: Video mavzusi va matnini inobatga olgan holda Baxtiyor Gaziyev sifatida ushbu izohga munosib, tabiiy va samimiy javob yoz. "
        f"Agar izoh kalit so'z yoki material so'rovi bo'lsa, aslo kulmasdan va yig'lamasdan, ma'lumot bio'da ekanini bildirib munosib javob ber:"
    )

    try:
        from src.services.utils.free_ai_router import get_free_ai_router
        result = await get_free_ai_router().generate_text(
            prompt,
            system=COMMENT_REPLY_SYSTEM,
            max_tokens=150,
            temperature=0.6,
        )
        reply = (result.text or "").strip().strip('"')
        if reply:
            logger.info("[META] Comment reply generated", provider=result.provider)
            return reply
    except Exception as exc:
        logger.warning("[META] generate_comment_reply fallback: %s", exc)

    import random
    return random.choice(FALLBACK_COMMENT_REPLIES)


def strip_bracket_tags(text: str) -> str:
    """Safely strip bracket tags like [TAG] in linear O(N) time without regex/ReDoS."""
    if not text or "[" not in text:
        return text or ""
    out: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        if text[i] == "[":
            close_idx = text.find("]", i, min(i + 200, n))
            if close_idx != -1:
                i = close_idx + 1
                continue
        out.append(text[i])
        i += 1
    return "".join(out).strip()


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

    clean_reply = strip_bracket_tags(reply)
    # Ism, xabar va AI javobi tashqi foydalanuvchidan keladi — HTML escape
    # qilinmasa "<" (masalan "<3") xabarni buzadi (lid yo'qoladi) yoki
    # <a href> orqali jamoa guruhiga phishing havola joylanadi.
    esc = html.escape

    crm_msg = (
        f"📱 <b>YANGI {esc(source.upper())} LEAD!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 <b>Foydalanuvchi:</b> {esc(str(user_name))}\n"
        f"🆔 <b>ID:</b> <code>{esc(str(user_id))}</code>\n"
        f"💎 <b>Sifati:</b> {quality}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"💬 <b>Xabar:</b> <i>{esc(message[:300])}</i>\n"
        f"🤖 <b>Oisha Javobi:</b> <i>{esc(clean_reply[:300])}</i>\n"
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

from src.services.core.instagram.webhook_processor import (
    is_safe_public_reply,
    allow_auto_reply,
    _auto_reply_log,
    process_instagram_webhook,
)

