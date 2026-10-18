"""
Instagram / Meta Webhook Event Processor Submodule
Handles DMs, mentions, and comment entries asynchronously.
"""
from __future__ import annotations

import html
import os
import re
import time
from collections import defaultdict, deque
from typing import Any, Optional
import structlog

from src.settings import settings
from src.time_utils import get_local_now, is_quiet_hours
from src.services.core.instagram.api_helpers import send_ig_message_payload
from src.services.core.instagram.agent_constants import (
    KEYWORD_AUTOMATION_PUBLIC_ACK,
    match_comment_keyword_automation as _match_comment_keyword_automation,
)
from src.services.core.instagram.backfill import _contains_sensitive_terms

logger = structlog.get_logger("InstagramWebhookProcessor")

_UNSAFE_PUBLIC_REPLY = re.compile(
    r"https?://|www\.|t\.me/|\b[\w-]+\.(?:com|uz|ru|net|org|io|me|link|app)\b|@\w{3,}|\+?\d[\d\s-]{7,}",
    re.IGNORECASE,
)
MAX_PUBLIC_REPLY_CHARS = 400
AUTO_REPLY_LIMIT_PER_HOUR = 3
_auto_reply_log: dict[str, deque] = defaultdict(deque)


def is_safe_public_reply(text: str) -> bool:
    """AI javobini brend nomidan ommaviy joylashdan oldin tekshiradi."""
    t = (text or "").strip()
    return bool(t) and len(t) <= MAX_PUBLIC_REPLY_CHARS and not _UNSAFE_PUBLIC_REPLY.search(t)


def allow_auto_reply(commenter_id: str, now: Optional[float] = None) -> bool:
    """Bitta izohlovchiga soatiga ko'pi bilan AUTO_REPLY_LIMIT_PER_HOUR ta avto-javob."""
    now = time.time() if now is None else now
    log = _auto_reply_log[commenter_id]
    while log and now - log[0] > 3600:
        log.popleft()
    if len(log) >= AUTO_REPLY_LIMIT_PER_HOUR:
        return False
    log.append(now)
    return True


def _get_meta_credentials() -> tuple[str, str]:
    """Retrieves access token and account ID from environment or settings."""
    access_token = (
        os.environ.get("PAGE_ACCESS_TOKEN", "").strip()
        or os.environ.get("META_PAGE_ACCESS_TOKEN", "").strip()
        or (settings.PAGE_ACCESS_TOKEN.get_secret_value() if getattr(settings, "PAGE_ACCESS_TOKEN", None) else "")
        or (settings.META_PAGE_ACCESS_TOKEN.get_secret_value() if getattr(settings, "META_PAGE_ACCESS_TOKEN", None) else "")
    )
    my_ig_id = (
        os.environ.get("INSTAGRAM_USER_ID", "").strip()
        or os.environ.get("META_INSTAGRAM_USER_ID", "").strip()
        or getattr(settings, "INSTAGRAM_USER_ID", None)
        or getattr(settings, "META_INSTAGRAM_USER_ID", None)
        or getattr(settings, "META_INSTAGRAM_ACCOUNT_ID", None)
        or ""
    )
    return access_token, my_ig_id


async def _handle_dm_event(sender_id: str, text: str, my_ig_id: str, db: Optional[Any]) -> None:
    """Processes a single incoming Instagram Direct Message."""
    from src.services.core.instagram_agent import strip_bracket_tags, notify_crm
    if my_ig_id and sender_id == str(my_ig_id):
        logger.info("[META] Skipping own DM (loop protection)", sender_id=sender_id)
        return

    user_id_str = f"ig_{sender_id}"
    logger.info("[META] Received Instagram DM", sender_id=sender_id, text=text[:50])
    if db:
        await db.log_message(user_id_str, text, is_ai=False)

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
        except Exception:
            history = []

    from src.services.core.instagram.lead_qualifier import generate_qualifying_dm_response
    ai_reply = await generate_qualifying_dm_response(user_message=text, history=history, commenter_name="")

    info_updates: dict[str, str] = {}
    for m in re.finditer(r"\[SAVE_INFO:\s*([^\[\]]+)\]", ai_reply, re.IGNORECASE):
        parts = m.group(1).split("=", 1)
        if len(parts) == 2:
            info_updates[parts[0].strip().lower()] = parts[1].strip()
    if info_updates and db:
        await db.upsert_user(user_id_str, "Foydalanuvchi", **info_updates)

    clean_reply = strip_bracket_tags(ai_reply)
    if db:
        await db.log_message(user_id_str, clean_reply, is_ai=True)

    notify_crm("Instagram DM", "Foydalanuvchi", sender_id, text, ai_reply)


async def _dispatch_comment_reply(
    comment_id: str,
    clean_reply: str,
    access_token: str,
    commenter_id: str,
    commenter_name: str,
    comment_text: str,
) -> None:
    """Dispatches public comment reply considering quiet hours, safety, and rate limits."""
    from src.services.core.instagram_agent import reply_to_comment
    if (
        is_quiet_hours(get_local_now())
        or _contains_sensitive_terms(comment_text)
        or not is_safe_public_reply(clean_reply)
        or not allow_auto_reply(commenter_id)
    ):
        logger.warning(
            "[META] Auto-post skipped — quiet hours, sensitive/unsafe text or rate limit",
            comment_id=comment_id,
            commenter=commenter_name,
        )
    else:
        reply_to_comment(comment_id, clean_reply, access_token)


async def _handle_keyword_flow(
    comment_id: str,
    commenter_id: str,
    commenter_name: str,
    comment_text: str,
    keyword_template: str,
    field: Optional[str],
    value: dict,
    access_token: str,
    db: Optional[Any],
) -> None:
    """Executes keyword-triggered private reply and public ack."""
    from src.services.core.instagram_agent import send_ig_private_reply, reply_to_comment, notify_crm
    user_id_str = f"ig_comment_{commenter_id}"
    sent = send_ig_private_reply(comment_id, keyword_template, access_token)
    if sent:
        reply_to_comment(comment_id, KEYWORD_AUTOMATION_PUBLIC_ACK, access_token)
    if db:
        await db.log_message(user_id_str, keyword_template, is_ai=False)
    source = "Instagram Mention" if field in {"mentions", "mention"} else "Instagram Comment"
    ad_id = str((value.get("media") or {}).get("ad_id") or "")
    if ad_id:
        source = f"Instagram Reklama (ad_id: {ad_id})"
    notify_crm(f"{source} (keyword automation)", commenter_name, commenter_id, comment_text, keyword_template)


async def _handle_comment_event(
    change: dict,
    entry_id: str,
    my_ig_id: str,
    access_token: str,
    db: Optional[Any],
) -> None:
    """Processes a single incoming comment change event."""
    from src.services.core.instagram_agent import strip_bracket_tags, notify_crm, generate_comment_reply
    field = change.get("field")
    if field and field not in {"feed", "comments", "mentions", "mention"}:
        return
    value = change.get("value", {})
    if value.get("verb") and value.get("verb") != "add":
        return

    from_obj = value.get("from", {})
    commenter_id = str(from_obj.get("id") or "")
    commenter_name = from_obj.get("name") or from_obj.get("username") or "Foydalanuvchi"
    comment_text = value.get("text") or value.get("message") or ""
    comment_id = str(value.get("id") or value.get("comment_id") or "")

    if (my_ig_id and commenter_id == str(my_ig_id)) or (entry_id and commenter_id == entry_id):
        return
    if not (comment_text and comment_id and commenter_id):
        return

    user_id_str = f"ig_comment_{commenter_id}"
    logger.info("[META] Received Instagram Comment", commenter=commenter_name, text=comment_text[:50])
    if db:
        await db.log_message(user_id_str, f"COMMENT: {comment_text}", is_ai=False)

    keyword_template = _match_comment_keyword_automation(comment_text)
    if keyword_template:
        await _handle_keyword_flow(
            comment_id, commenter_id, commenter_name, comment_text,
            keyword_template, field, value, access_token, db
        )
        return

    media_id = str((value.get("media") or {}).get("id") or "")
    post_caption = ""
    if media_id:
        from src.services.core.instagram.video_analyzer import analyze_media_content
        post_caption = await analyze_media_content(media_id, access_token)

    from src.services.core.instagram.emoji_utils import get_mirror_emoji_reply
    emoji_mirror = get_mirror_emoji_reply(comment_text)
    clean_reply = ai_reply = emoji_mirror if emoji_mirror else strip_bracket_tags(
        await generate_comment_reply(comment_text=comment_text, post_caption=post_caption, commenter_name=commenter_name)
    )

    if db:
        await db.log_message(user_id_str, clean_reply, is_ai=True)

    await _dispatch_comment_reply(comment_id, clean_reply, access_token, commenter_id, commenter_name, comment_text)
    source = "Instagram Mention" if field in {"mentions", "mention"} else "Instagram Comment"
    notify_crm(source, commenter_name, commenter_id, comment_text, ai_reply)


def _extract_dm_events(entry: dict) -> list[tuple[str, str]]:
    """Extracts direct messaging event tuples from a webhook entry."""
    dm_events: list[tuple[str, str]] = []
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
            s = str((m.get("from") or {}).get("id") or m.get("sender_id") or val.get("sender", {}).get("id") or "")
            body = m.get("message") or m.get("text") or ""
            if isinstance(body, dict):
                body = body.get("text", "")
            if s and body:
                dm_events.append((s, body))
    return dm_events


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

    access_token, my_ig_id = _get_meta_credentials()

    for entry in payload.get("entry", []):
        entry_id = str(entry.get("id") or "")
        for sender_id, text in _extract_dm_events(entry):
            await _handle_dm_event(sender_id, text, my_ig_id, db)

        for change in entry.get("changes", []):
            await _handle_comment_event(change, entry_id, my_ig_id, access_token, db)
