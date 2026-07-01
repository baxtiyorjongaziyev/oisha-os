"""Kirim topic handler for celebrating sales income announcements."""
from __future__ import annotations

import structlog
import re
from typing import Any, Dict, Optional

from src.context import app_ctx
from src.settings import settings
from src.handlers.income_workflow import (
    is_group_open_confirmation,
    is_finance_rejection,
)

logger = structlog.get_logger()


def _kirim_celebration_key(chat_id: int, message_id: int) -> str:
    return f"kirim_celebration:{chat_id}:{message_id}"


def _extract_income_amount(text: str) -> Dict[str, Any]:
    lowered = (text or "").lower()
    currency = "USD" if ("$" in lowered or "usd" in lowered) else "UZS"
    matches = list(re.finditer(r"\d[\d\s,.]*", text or ""))
    if not matches:
        return {"raw": "noma'lum", "value": None, "currency": currency}

    raw_amount = max(matches, key=lambda match: len(match.group(0))).group(0).strip()
    if currency == "USD":
        cleaned = raw_amount.replace(" ", "").replace(",", ".")
        if cleaned.count(".") > 1:
            parts = cleaned.split(".")
            cleaned = "".join(parts[:-1]) + "." + parts[-1]
        try:
            value = float(cleaned)
        except ValueError:
            value = None
    else:
        cleaned = re.sub(r"[^\d]", "", raw_amount)
        value = int(cleaned) if cleaned else None

    return {"raw": raw_amount, "value": value, "currency": currency}


def _format_income_amount_for_celebration(amount: Dict[str, Any]) -> str:
    raw = str(amount.get("raw") or "").strip()
    if not raw or raw == "noma'lum":
        return "yangi kirim"

    lowered = raw.lower()
    if "$" in raw or "usd" in lowered:
        return raw
    if "so'm" in lowered or "sum" in lowered or "uzs" in lowered:
        return raw
    if (amount.get("currency") or "UZS") == "USD":
        return f"{raw} USD"
    return f"{raw} so'm"


def _sender_display_name(sender: Any) -> str:
    username = (getattr(sender, "username", None) or "").strip()
    if username:
        return username if username.startswith("@") else f"@{username}"

    full_name = " ".join(
        part
        for part in (
            getattr(sender, "first_name", None),
            getattr(sender, "last_name", None),
        )
        if part
    ).strip()
    return full_name or "Sotuvchi"


def _looks_like_income_announcement(text: str) -> bool:
    lowered = (text or "").lower().strip()
    if not lowered or lowered.startswith("/"):
        return False
    if is_group_open_confirmation(lowered):
        return False

    if lowered.endswith("?"):
        return False
    negation_terms = (
        "bo'lmadi", "bolmadi", "kelmadi", "tushmadi",
        "yo'q", "yoq", "emas", "qilmadi", "bo'lmagan",
    )
    if any(term in lowered for term in negation_terms):
        return False
    if is_finance_rejection(lowered):
        return False

    amount = _extract_income_amount(text)
    return amount.get("value") is not None


def _is_kirim_topic_message(message: Any) -> bool:
    if not settings.TOPIC_KIRIM_ID:
        return False

    topic_id = settings.TOPIC_KIRIM_ID
    direct_reply_id = getattr(message, "reply_to_msg_id", None)
    reply_to = getattr(message, "reply_to", None)
    reply_top_id = getattr(message, "reply_to_top_id", None) or getattr(
        reply_to, "reply_to_top_id", None
    )
    forum_topic = getattr(reply_to, "forum_topic", False)

    return bool(
        direct_reply_id == topic_id
        or reply_top_id == topic_id
        or (forum_topic and direct_reply_id == topic_id)
    )


async def _send_kirim_celebration(event, celebration: str) -> None:
    """Prefer the bot head, then use the listening userbot when group access is absent."""
    if app_ctx.bot_client:
        try:
            await app_ctx.bot_client.send_message(
                settings.TEAM_GROUP_ID,
                celebration,
                reply_to=event.id,
                link_preview=False,
            )
            return
        except Exception as exc:
            logger.warning(
                "[KIRIM] Bot-token send failed (%s); using userbot reply fallback.",
                type(exc).__name__,
            )
    await event.reply(celebration, link_preview=False)


async def kirim_topic_handler(event):
    """Team guruhidagi Kirim topicda sotuvchi kirim e'lon qilsa tabriklaydi."""
    if not settings.TEAM_GROUP_ID or not settings.TOPIC_KIRIM_ID:
        return
    if event.chat_id != settings.TEAM_GROUP_ID:
        return
    if not _is_kirim_topic_message(event.message):
        return

    text = (getattr(event.message, "message", None) or getattr(event.message, "text", None) or "").strip()
    if not _looks_like_income_announcement(text):
        return

    sender = await event.get_sender()
    if getattr(sender, "bot", False):
        return

    db = app_ctx.msg_controller.db if app_ctx.msg_controller else None
    if not db:
        logger.warning("[KIRIM] DB unavailable; celebration skipped.")
        return

    state_key = _kirim_celebration_key(int(event.chat_id), int(event.id))
    if await db.get_state(state_key):
        return
    await db.set_state(state_key, "started")

    seller_name = _sender_display_name(sender)
    amount_label = _format_income_amount_for_celebration(_extract_income_amount(text))
    try:
        if app_ctx.advisor_agent:
            celebration = await app_ctx.advisor_agent.generate_sales_celebration(seller_name, amount_label)
        else:
            celebration = ""
    except Exception as exc:
        logger.warning(f"[KIRIM] AI celebration fallback: {type(exc).__name__}")
        celebration = ""

    if not celebration:
        celebration = (
            f"{seller_name}, tabriklaymiz!\n\n"
            f"Yangi kirim: {amount_label}.\n"
            "Zo'r natija. Mijoz ishonchini kelishuvga aylantirish oson ish emas. "
            "Shu tempni ushlab turamiz!"
        )
    elif seller_name not in celebration:
        celebration = f"{seller_name}, {celebration}"

    try:
        await _send_kirim_celebration(event, celebration)
        await db.set_state(state_key, "done")
        logger.info(f"[KIRIM] Celebration sent chat={event.chat_id} msg={event.id} seller={seller_name}")
    except Exception as exc:
        await db.set_state(state_key, f"failed:{type(exc).__name__}")
        logger.error(f"[KIRIM] Celebration send failed: {exc}", exc_info=True)
