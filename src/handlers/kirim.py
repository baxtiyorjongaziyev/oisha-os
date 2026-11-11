"""Kirim topic handler for celebrating sales income announcements."""
from __future__ import annotations

import asyncio
import re
import time
from typing import Any, Dict, Optional

import structlog

from src.context import app_ctx
from src.settings import settings
from src.handlers.income_workflow import (
    is_group_open_confirmation,
    is_finance_rejection,
)

from src.services.core.rop.fetchers import RopFetcher
from src.services.core.rop.targets import load_roster

logger = structlog.get_logger()

_APOSTROPHES = re.compile("['`\u2018\u2019\u02bb\u02bc]")
_NEGATION_TERMS = ("bolmadi", "kelmadi", "tushmadi", "yoq", "emas", "qilmadi", "bolmagan")
_PAYMENT_TERMS = ("tolov", "tushdi", "sotuv boldi", "sotildi", "kirim", "avans", "oplata", "chek")
_WON_CHECK_DELAY_SECONDS = 1800
_WON_LOOKBACK_SECONDS = 86400
_background_tasks: set = set()


def _kirim_won_check_key(chat_id: int, message_id: int) -> str:
    return f"kirim_won_check:{chat_id}:{message_id}"


def _plain(text: str) -> str:
    """Kichik harf, apostrofsiz: oʻ / o' / o’ yozuvlari bir xil taqqoslanadi."""
    return _APOSTROPHES.sub("", (text or "").lower()).strip()


def _is_rejected_text(text: str) -> bool:
    """Buyruq, savol, inkor yoki rad — tabrikka sabab emas."""
    plain = _plain(text)
    if plain.startswith("/") or plain.endswith("?"):
        return True
    if is_group_open_confirmation(plain) or is_finance_rejection(plain):
        return True
    return any(term in plain for term in _NEGATION_TERMS)


def _kirim_celebration_key(chat_id: int, message_id: int) -> str:
    return f"kirim_celebration:{chat_id}:{message_id}"


def _extract_income_amount(text: str) -> Dict[str, Any]:
    lowered = (text or "").lower()
    currency = "USD" if ("$" in lowered or "usd" in lowered) else "UZS"
    matches = list(re.finditer(r"\d[\d\s,.]*", text or ""))
    if not matches:
        return {"raw": "nomaʼlum", "value": None, "currency": currency}

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
    if not raw or raw == "nomaʼlum":
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
    if not _plain(text) or _is_rejected_text(text):
        return False
    amount = _extract_income_amount(text)
    return amount.get("value") is not None


def _looks_like_payment_confirmation(message: Any, text: str) -> bool:
    """Summasiz toʻlov tasdigʻi: chek rasmi/fayli yoki toʻlov haqidagi matn.

    Faqat topicning yuqori darajadagi xabari hisoblanadi — boshqa xabarga
    yozilgan javob (masalan buxgalterning "tushdi"si) tabrikni chaqirmaydi.
    """
    if getattr(message, "reply_to_msg_id", None) != settings.TOPIC_KIRIM_ID:
        return False
    if _is_rejected_text(text):
        return False
    if getattr(message, "photo", None) or getattr(message, "document", None):
        return True
    plain = _plain(text)
    return any(term in plain for term in _PAYMENT_TERMS)


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


async def _seller_won_lead_id(db, sender_id: int) -> Optional[int]:
    """Sotuvchining oxirgi sutkada Won boʻlgan bitimi. -1: sotuvchi rosterda yoʻq."""
    from src.database import get_db

    repo = getattr(db, "rop", None) or get_db().rop
    roster = await load_roster(repo)
    seller = next((t for t in roster if t.telegram_user_id == sender_id), None)
    if seller is None:
        return -1

    amocrm = app_ctx.msg_controller.crm.amocrm
    since = int(time.time()) - _WON_LOOKBACK_SECONDS
    for lead in await RopFetcher(amocrm).fetch_won_leads_since(since):
        if lead.get("responsible_user_id") == seller.responsible_user_id:
            return int(lead.get("id") or 0)
    return None


async def _check_won_after_payment(event, sender_id: int, seller_name: str, db, delay: Optional[int] = None) -> None:
    """Tabrikdan keyin amoCRMni tekshiradi; bitim Won boʻlmasa sotuvchiga eslatadi."""
    if delay is None:
        delay = int(getattr(settings, "KIRIM_WON_CHECK_DELAY_SECONDS", _WON_CHECK_DELAY_SECONDS))
    state_key = _kirim_won_check_key(int(event.chat_id), int(event.id))
    try:
        await asyncio.sleep(delay)
        lead_id = await _seller_won_lead_id(db, sender_id)
        if lead_id == -1:
            logger.warning(f"[KIRIM] Won check skipped: tg={sender_id} not in rop_targets")
            await db.set_state(state_key, "unknown_seller")
            return
        if lead_id is not None:
            await db.set_state(state_key, f"won:{lead_id}")
            return
        await _send_kirim_celebration(
            event,
            f"{seller_name}, amoCRMda bu bitim hali «Sotuv boʻldi» bosqichiga oʻtkazilmagan. "
            "Iltimos, bitimni Won bosqichiga oʻtkazib qoʻying.",
        )
        await db.set_state(state_key, "reminded")
    except Exception as exc:
        logger.error(f"[KIRIM] Won check failed: {exc}", exc_info=True)


def _schedule_won_check(event, sender_id: Optional[int], seller_name: str, db) -> None:
    if not sender_id:
        return
    task = asyncio.create_task(_check_won_after_payment(event, int(sender_id), seller_name, db))
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


async def kirim_topic_handler(event):
    """Team guruhidagi Kirim topicda sotuvchi kirim eʼlon qilsa tabriklaydi."""
    if not settings.TEAM_GROUP_ID or not settings.TOPIC_KIRIM_ID:
        return
    if event.chat_id != settings.TEAM_GROUP_ID:
        return
    if not _is_kirim_topic_message(event.message):
        return

    text = (getattr(event.message, "message", None) or getattr(event.message, "text", None) or "").strip()
    if not _looks_like_income_announcement(text) and not _looks_like_payment_confirmation(event.message, text):
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
        amount_line = "" if amount_label == "yangi kirim" else f"Yangi kirim: {amount_label}.\n"
        celebration = (
            f"{seller_name}, tabriklaymiz!\n\n"
            f"{amount_line}"
            "Zoʻr natija. Mijoz ishonchini kelishuvga aylantirish oson ish emas. "
            "Shu tempni ushlab turamiz!"
        )
    elif seller_name not in celebration:
        celebration = f"{seller_name}, {celebration}"

    try:
        await _send_kirim_celebration(event, celebration)
        await db.set_state(state_key, "done")
        logger.info(f"[KIRIM] Celebration sent chat={event.chat_id} msg={event.id} seller={seller_name}")
        _schedule_won_check(event, getattr(sender, "id", None), seller_name, db)
    except Exception as exc:
        await db.set_state(state_key, f"failed:{type(exc).__name__}")
        logger.error(f"[KIRIM] Celebration send failed: {exc}", exc_info=True)
