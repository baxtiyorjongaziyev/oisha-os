"""Sotuv guruhidagi "TOʻLOV TASDIQLASH" kartasiga uch botning alohida tabrigi.

Oisha AI, Amina AI va Mr.Jon AI har biri oʻz nomidan, kartaga javob qilib yozadi.
Bu faqat tabrik: moliyaviy tasdiq va kirim yozuvi bu yerda qilinmaydi.

Amina va Mr.Jon Bot API orqali AMINA_BOT_TOKEN / MRJON_BOT_TOKEN bilan yuboradi;
token yoʻq boʻlsa oʻsha bot oʻtkazib yuboriladi, qolganlari ishlayveradi.
"""
from __future__ import annotations

import asyncio
import os
import random
import re
from typing import Any, Dict, Optional

import httpx
import structlog

from src.context import app_ctx
from src.settings import settings
from src.time_utils import is_quiet_hours

logger = structlog.get_logger()

_FIELD_RE = re.compile(r"^[^\w]*(?P<label>[^:\n]+?)\s*:\s*(?P<value>.*?)\s*$")
_CARD_MARKER_RE = re.compile(r"to.?lov tasdiqlash")
_SEND_GAP_SECONDS = 2.0
_SEND_TIMEOUT_SECONDS = 15.0

OISHA_TEMPLATES = (
    "{seller}, tabriklayman! 🎉 {project}{amount} toʻlov qabul qilindi. Aniq ish, shu tempda davom etamiz.",
    "{seller}, barakalla! 👏 {project}{amount}. Natija gapirib turibdi.",
)
AMINA_TEMPLATES = (
    "{seller}, muborak boʻlsin! 🌸 {project}{amount} — mehnatingiz samarasi. Omad yor boʻlsin!",
    "{seller}, juda xursand boʻldim! 🌷 {project}{amount}. Shunday yutuqlar koʻpaysin!",
)
MRJON_TEMPLATES = (
    "{seller}, zoʻr savdo! 🔥 {project}{amount}. Keyingisini ham shunday yopamiz!",
    "Ana endi gap boshqa, {seller}! 💪 {project}{amount}. Qoyil!",
)


def parse_payment_card(text: str) -> Optional[Dict[str, Optional[str]]]:
    """Kartani oʻqiydi; karta boʻlmasa yoki summasi boʻsh boʻlsa None qaytaradi."""
    normalized = text or ""
    lowered = normalized.lower()
    if not _CARD_MARKER_RE.search(lowered):
        return None

    card: Dict[str, Optional[str]] = {"amount": None, "project": None, "seller": None}
    for line in normalized.splitlines():
        match = _FIELD_RE.match(line)
        if not match or not match.group("value"):
            continue
        label = match.group("label").lower()
        value = match.group("value")
        if "summa" in label:
            has_currency = re.search(r"so.?m|sum|uzs|usd|\$", value, re.IGNORECASE)
            unit = "USD" if re.search(r"usd|\$|dollar", label) else "soʻm"
            card["amount"] = value if has_currency else f"{value} {unit}"
        elif "mijoz" in label or "loyiha" in label:
            card["project"] = value
        elif "sotuvchi" in label:
            card["seller"] = value

    if not card["amount"] or not re.search(r"\d", card["amount"]):
        return None
    return card


def _seller_label(sender: Any, card: Dict[str, Optional[str]]) -> str:
    username = (getattr(sender, "username", None) or "").lstrip("@")
    if username:
        return f"@{username}"
    return card.get("seller") or getattr(sender, "first_name", None) or "Sotuvchi"


def build_message(templates: tuple[str, ...], seller: str, card: Dict[str, Optional[str]]) -> str:
    project = f"{card['project']}: " if card.get("project") else ""
    return random.choice(templates).format(seller=seller, project=project, amount=card["amount"])


async def _send_as_oisha(chat_id: int, reply_to: int, text: str) -> None:
    if not app_ctx.bot_client:
        raise RuntimeError("bot_client unavailable")
    try:
        await app_ctx.bot_client.send_message(chat_id, text, reply_to=reply_to, link_preview=False)
    except ConnectionError:
        # Telethon mijozi uzilib qolgan boʻlsa bir marta qayta ulanib urinadi.
        await app_ctx.bot_client.connect()
        await app_ctx.bot_client.send_message(chat_id, text, reply_to=reply_to, link_preview=False)


def _topic_id(message: Any) -> Optional[int]:
    """Forum topic ID; General yoki oddiy guruhda None."""
    reply = getattr(message, "reply_to", None)
    if not reply or not getattr(reply, "forum_topic", False):
        return None
    return getattr(reply, "reply_to_top_id", None) or getattr(reply, "reply_to_msg_id", None)


async def _send_via_bot_api(
    token: str, chat_id: int, reply_to: int, text: str, thread_id: Optional[int] = None
) -> None:
    payload: Dict[str, Any] = {
        "chat_id": chat_id,
        "text": text,
        "reply_to_message_id": reply_to,
        "allow_sending_without_reply": True,
    }
    if thread_id:
        payload["message_thread_id"] = thread_id
    async with httpx.AsyncClient(timeout=_SEND_TIMEOUT_SECONDS) as http:
        response = await http.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json=payload,
        )
    if response.status_code != 200:
        raise RuntimeError(f"Bot API HTTP {response.status_code}")


async def _congratulate(
    chat_id: int,
    reply_to: int,
    seller: str,
    card: Dict[str, Optional[str]],
    thread_id: Optional[int] = None,
) -> None:
    """Har bir bot mustaqil: bittasining xatosi qolganlarini toʻxtatmaydi."""
    senders = [("oisha", OISHA_TEMPLATES, None)]
    for name, env_key, templates in (
        ("amina", "AMINA_BOT_TOKEN", AMINA_TEMPLATES),
        ("mrjon", "MRJON_BOT_TOKEN", MRJON_TEMPLATES),
    ):
        token = (os.getenv(env_key) or "").strip()
        if token:
            senders.append((name, templates, token))
        else:
            logger.warning(f"[SALES_CONGRATS] {env_key} sozlanmagan; {name} oʻtkazib yuborildi.")

    for index, (name, templates, token) in enumerate(senders):
        if index:
            await asyncio.sleep(_SEND_GAP_SECONDS)
        text = build_message(templates, seller, card)
        try:
            if token:
                await _send_via_bot_api(token, chat_id, reply_to, text, thread_id)
            else:
                await _send_as_oisha(chat_id, reply_to, text)
        except Exception as exc:
            # Faqat turi va matni tokensiz xato: httpx xatosi URL (token) ni ochishi mumkin.
            detail = str(exc) if isinstance(exc, RuntimeError) else ""
            logger.error(f"[SALES_CONGRATS] {name} yubora olmadi: {type(exc).__name__} {detail}")


async def sales_payment_congrats_handler(event: Any) -> None:
    """Sotuv guruhida toʻlov kartasi chiqsa uch bot alohida tabriklaydi."""
    text = getattr(event.message, "message", None) or ""
    card = parse_payment_card(text)
    if not card:
        return

    sender = await event.get_sender()
    if getattr(sender, "bot", False):
        return
    if is_quiet_hours():
        logger.info(f"[SALES_CONGRATS] Quiet hours; tabrik yuborilmadi msg={event.id}")
        return

    db = app_ctx.msg_controller.db if app_ctx.msg_controller else None
    if not db:
        logger.warning("[SALES_CONGRATS] DB unavailable; dublikatdan himoya yoʻq, oʻtkazib yuborildi.")
        return

    chat_id, message_id = int(event.chat_id), int(event.id)
    state_key = f"sales_payment_congrats:{chat_id}:{message_id}"
    if await db.get_state(state_key):
        return
    await db.set_state(state_key, "sent")

    await _congratulate(
        chat_id, message_id, _seller_label(sender, card), card, _topic_id(event.message)
    )
