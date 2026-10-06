"""
Instagram / Meta Webhook Event Processor & Agent Core Service
"""
from __future__ import annotations

import hashlib
import hmac
import os
import re
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

    access_token = (
        os.environ.get("META_PAGE_ACCESS_TOKEN", "").strip()
        or (settings.META_PAGE_ACCESS_TOKEN.get_secret_value() if settings.META_PAGE_ACCESS_TOKEN else "")
    )
    my_ig_id = (
        os.environ.get("META_INSTAGRAM_USER_ID", "").strip()
        or getattr(settings, "META_INSTAGRAM_USER_ID", None)
        or getattr(settings, "META_INSTAGRAM_ACCOUNT_ID", None)
        or ""
    )

    for entry in payload.get("entry", []):
        entry_id = str(entry.get("id") or "")

        # --- Direct Message handling -----------------------------------------
        # Meta delivers IG DMs in two shapes depending on the product config:
        #   1) entry[].messaging[]            (Messenger-style)
        #   2) entry[].changes[] field=messages, value.message(s)  (IG Graph)
        dm_events: list[tuple[str, str]] = []  # (sender_id, text)

        for event in entry.get("messaging", []) or []:
            s = str(event.get("sender", {}).get("id") or "")
            t = (event.get("message", {}) or {}).get("text", "") or ""
            if s and t:
                dm_events.append((s, t))

        for change in entry.get("changes", []) or []:
            if change.get("field") not in ("messages", "message"):
                continue
            val = change.get("value", {}) or {}
            msgs = val.get("messages") or ([val] if val.get("message") or val.get("text") else [])
            for m in msgs:
                s = str(
                    (m.get("from") or {}).get("id")
                    or m.get("sender_id")
                    or val.get("sender", {}).get("id")
                    or ""
                )
                body = m.get("message") or m.get("text") or ""
                if isinstance(body, dict):
                    body = body.get("text", "")
                if s and body:
                    dm_events.append((s, body))

        for sender_id, text in dm_events:
            if my_ig_id and sender_id == str(my_ig_id):
                logger.info("[META] Skipping own DM (loop protection)", sender_id=sender_id)
                continue

            user_id_str = f"ig_{sender_id}"
            logger.info("[META] Received Instagram DM", sender_id=sender_id, text=text[:50])
            if db:
                await db.log_message(user_id_str, text, is_ai=False)

            # Conversation history so the qualification funnel has context.
            history: list[dict] = []
            if db:
                try:
                    rows = await db.get_recent_messages(user_id_str, limit=12)
                    for r in (rows or []):
                        role = "assistant" if r.get("role") == "model" else "user"
                        parts = r.get("parts") or []
                        content = parts[0].get("text", "") if parts else r.get("content", "")
                        if content:
                            history.append({"role": role, "content": content})
                except Exception:  # noqa: BLE001 - history is best-effort
                    history = []

            from src.services.core.instagram.lead_qualifier import (
                generate_qualifying_dm_response,
            )
            ai_reply = await generate_qualifying_dm_response(
                user_message=text,
                history=history,
                commenter_name="",
            )

            info_updates: dict[str, str] = {}
            for m in re.finditer(r"\[SAVE_INFO:\s*([^\[\]]+)\]", ai_reply, re.IGNORECASE):
                parts = m.group(1).split("=", 1)
                if len(parts) == 2:
                    info_updates[parts[0].strip().lower()] = parts[1].strip()
            if info_updates and db:
                await db.upsert_user(user_id_str, "Foydalanuvchi", **info_updates)

            clean_reply = strip_bracket_tags(ai_reply)
            if db:
                # Stored as a draft suggestion only — is_ai=True marks it as
                # AI-authored text, but it is never sent to the customer.
                await db.log_message(user_id_str, clean_reply, is_ai=True)

            # NOTE: AmoCRM already ingests Instagram DMs via its own native
            # integration and opens the deal itself. Do NOT create a second
            # deal here — it produces junk "Instagram DM: <id>" duplicates.
            #
            # Policy: DM mijozlarga AI avtomatik javob YUBORMAYDI (faqat
            # Telegram va Instagram kommentlarida AI javob berish ruxsat
            # etilgan). AI javobi faqat taklif (draft) sifatida CRM guruhga
            # yuboriladi — jamoa qo'lda javob beradi.
            notify_crm("Instagram DM", "Foydalanuvchi", sender_id, text, ai_reply)

        # Comment / Page Feed Change Handling
        changes = entry.get("changes", [])
        for change in changes:
            field = change.get("field")
            if field and field not in {"feed", "comments", "mentions", "mention"}:
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

                keyword_template = _match_comment_keyword_automation(comment_text)
                if keyword_template:
                    sent = send_ig_private_reply(comment_id, keyword_template, access_token)
                    if sent:
                        reply_to_comment(comment_id, KEYWORD_AUTOMATION_PUBLIC_ACK, access_token)
                    if db:
                        await db.log_message(user_id_str, keyword_template, is_ai=False)
                    source = "Instagram Mention" if field in {"mentions", "mention"} else "Instagram Comment"
                    ad_id = str((value.get("media") or {}).get("ad_id") or "")
                    if ad_id:
                        source = f"Instagram Reklama (ad_id: {ad_id})"
                    notify_crm(
                        f"{source} (keyword automation)",
                        commenter_name,
                        commenter_id,
                        comment_text,
                        keyword_template,
                    )
                    logger.info(
                        "[META] Keyword automation DM sent",
                        sent=sent,
                        commenter=commenter_name,
                        comment_id=comment_id,
                    )
                    continue

                media_id = str((value.get("media") or {}).get("id") or "")
                if media_id:
                    from src.services.core.instagram.video_analyzer import analyze_media_content
                    # analyze_media_content fetches the caption itself and, for
                    # VIDEO/REELS, downloads and has Gemini describe the actual
                    # video content — so replies are grounded in what the video
                    # really shows/says, not just the caption text.
                    post_caption = await analyze_media_content(media_id, access_token)
                else:
                    post_caption = ""

                from src.services.core.instagram.emoji_utils import get_mirror_emoji_reply
                emoji_mirror = get_mirror_emoji_reply(comment_text)
                if emoji_mirror:
                    clean_reply = emoji_mirror
                    ai_reply = emoji_mirror
                else:
                    ai_reply = await generate_comment_reply(
                        comment_text=comment_text,
                        post_caption=post_caption,
                        commenter_name=commenter_name,
                    )
                    clean_reply = strip_bracket_tags(ai_reply)

                if db:
                    await db.log_message(user_id_str, clean_reply, is_ai=True)

                source = "Instagram Mention" if field in {"mentions", "mention"} else "Instagram Comment"
                if is_quiet_hours(get_local_now()) or _contains_sensitive_terms(comment_text):
                    logger.warning(
                        "[META] Auto-post skipped — quiet hours or sensitive terms, needs human review",
                        comment_id=comment_id,
                        commenter=commenter_name,
                    )
                else:
                    reply_to_comment(comment_id, clean_reply, access_token)

                notify_crm(source, commenter_name, commenter_id, comment_text, ai_reply)

