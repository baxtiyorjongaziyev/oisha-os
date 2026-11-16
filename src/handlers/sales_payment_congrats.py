"""Sotuv guruhidagi "TOʻLOV TASDIQLASH" kartasiga uch botning alohida tabrigi.

Uchta alohida xarakter va texnologiya asosida:
1. Oisha AI: Oisha-OS Surgical COO (operatsion tasdiq va jamoaviy intizom/temp)
2. Amina AI: Hermes Empathetic Sales Coach (mehrli hamroh, insoniy va ruhiy dalda)
3. Mr.Jon AI: OpenClaw Founder Digital Twin (Master Closer, biznes gʻalabasi va motivatsiya)

Har bir agent Telegramda tabiiy insondek ("typing..." effekti va oraliq bilan) harakatlanadi.
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
from src.handlers.sales_won_check import schedule_won_check
from src.time_utils import is_quiet_hours

logger = structlog.get_logger()

_FIELD_RE = re.compile(r"^[^\w]*(?P<label>[^:\n]+?)\s*:\s*(?P<value>.*?)\s*$")
_CARD_MARKER_RE = re.compile(r"to.?lov tasdiqlash")
_SEND_GAP_SECONDS = 2.0
_TYPING_DURATION_SECONDS = 1.5
_SEND_TIMEOUT_SECONDS = 15.0

OISHA_TEMPLATES = (
    "{seller}, toʻlov qabul qilindi va tizimga muhrlandi! 👏 {project}{amount}. Konversiya surʼati aʼlo darajada, bugungi rejani ishonch bilan oldinga suryapmiz. Moliyaga uzatildi, shu tempda davom etamiz.",
    "Ajoyib intizom va aniq natija, {seller}! 🎯 {project}{amount} kassa qaydiga olindi. Jamoaviy ritmda bunday tezkorlik har birimizga kuch beradi. Keyingi bosqichga oʻtamiz.",
    "{seller}, qabul qilindi! ⚡️ {project}{amount}. Har bir aniq qadam va harakat oʻz mevasini beryapti. Tempni tushirmasdan harakatda davom etamiz.",
    "{seller}, barakalla! 👏 {project}{amount} qayd etildi. CRM intizomi va operatsion tezlik joyida. Shu ruhda davom etamiz!",
)

AMINA_TEMPLATES = (
    "{seller_warm}, muborak boʻlsin! 🌸 {project}{amount} — har bir qoʻngʻiroq, sabr va peshona teringiz samarasi. Barakasini bersin, mehnatingiz doim shunday meva beraversin 🌷",
    "{seller_warm}, chin qalbimdan juda quvondim! 🌷 {project}{amount}. Mijoz bilan shunday sabr va samimiyat bilan muloqot qilganingiz oʻz natijasini koʻrsatdi. Omad doim yoringiz boʻlsin!",
    "Peshona teringizga ming bor baraka, {seller_warm}! ✨ {project}{amount}. Har bir yutuq ortida qancha mehnat borligini bilaman. Alloh barakasini bersin, yuzingiz doim shunday yorugʻ boʻlsin 🌸",
    "Goʻzal natija, {seller_warm}! 🌺 {project}{amount}. Qiyinchiliklar ortidan albatta yengillik va quvonch keladi, mana bugun buni yana bir bor koʻrdik. Charchamang!",
)

MRJON_TEMPLATES = (
    "{seller}, zoʻr savdo boʻldi! 🔥 {project}{amount}. Oson boʻlmadi, lekin strategik closing va toʻgʻri pozitsiya oʻz soʻzini aytdi. Bu haqiqiy natija! Keyingi katta chekni ham shunday dadil yopamiz!",
    "Ana endi gap boshqa, {seller}! 🚀 {project}{amount}. Mijoz eʼtirozlarini sindirib, bitimni gʻalaba bilan yakunlash — mana bu haqiqiy mahorat. Qoyil! Tempni tushirmaymiz!",
    "{seller}, qoyilmaqom closing! 💪 {project}{amount}. Brending bozorida natija gapiradi, siz esa bugun yana bir karra buni isbotladingiz. Katta marralar sari olgʻa!",
    "{seller}, mana buni natija desa boʻladi! 🎩 {project}{amount}. Har bir yirik shartnoma agentligimiz brendini yanada balandga koʻtaradi. Keyingi marrani zabt etishga tayyormizmi?",
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


def _warm_seller_name(name: str) -> str:
    """Amina (Hermes) uchun iliq va hurmatli oʻzbekcha murojaat shakli."""
    clean = re.sub(r"^@", "", name or "").strip()
    lowered = clean.lower()
    if "rayxon" in lowered:
        return "Rayxonaxon"
    if "shahnoz" in lowered:
        return "Shahnozaxon"
    if "mumtoz" in lowered:
        return "Mumtozaxon"
    if "hasan" in lowered:
        return "Hasanboy"
    if "baxtiyor" in lowered:
        return "Baxtiyor aka"
    if "jonibek" in lowered:
        return "Jonibek aka"
    if clean and not name.startswith("@"):
        return f"{clean}jon"
    return name


def build_oisha_message(seller: str, card: Dict[str, Optional[str]]) -> str:
    """Oisha-OS Surgical COO uslubidagi rasmiy-operatsion tabrik."""
    project = f"{card['project']}: " if card.get("project") else ""
    return random.choice(OISHA_TEMPLATES).format(seller=seller, project=project, amount=card["amount"])


def build_amina_message(seller: str, card: Dict[str, Optional[str]]) -> str:
    """Hermes Empathetic Coach uslubidagi iliq va qadriyatga yoʻgʻrilgan tabrik."""
    project = f"{card['project']}: " if card.get("project") else ""
    seller_warm = _warm_seller_name(card.get("seller") or seller)
    return random.choice(AMINA_TEMPLATES).format(seller_warm=seller_warm, project=project, amount=card["amount"])


def build_mrjon_message(seller: str, card: Dict[str, Optional[str]]) -> str:
    """OpenClaw Founder Digital Twin uslubidagi dadil, strategik savdo closing tabrigi."""
    project = f"{card['project']}: " if card.get("project") else ""
    return random.choice(MRJON_TEMPLATES).format(seller=seller, project=project, amount=card["amount"])


async def _send_as_oisha(chat_id: int, reply_to: int, text: str) -> None:
    """Oisha nomidan xabar yuborish: bot_client (ConnectionError da reconnect), soʻng userbot fallback."""
    bot_client = getattr(app_ctx, "bot_client", None)
    if bot_client:
        try:
            await bot_client.send_message(chat_id, text, reply_to=reply_to, link_preview=False)
            return
        except ConnectionError:
            try:
                await bot_client.connect()
                await bot_client.send_message(chat_id, text, reply_to=reply_to, link_preview=False)
                return
            except Exception as reconnect_exc:
                logger.warning(
                    f"[SALES_CONGRATS] bot_client reconnect muvaffaqiyatsiz ({type(reconnect_exc).__name__}), userbot fallback..."
                )
        except Exception as exc:
            logger.warning(
                f"[SALES_CONGRATS] bot_client orqali yuborilmadi ({type(exc).__name__}), userbot fallback qoʻllanmoqda..."
            )
    user_client = getattr(app_ctx, "client", None)
    if user_client:
        await user_client.send_message(chat_id, text, reply_to=reply_to, link_preview=False)
    else:
        raise RuntimeError("Neither bot_client nor userbot client available")


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


async def _send_typing_via_bot_api(
    token: str, chat_id: int, thread_id: Optional[int] = None
) -> None:
    """Telegramda xuddi inson yozayotgandek 'typing...' holatini koʻrsatadi."""
    payload: Dict[str, Any] = {"chat_id": chat_id, "action": "typing"}
    if thread_id:
        payload["message_thread_id"] = thread_id
    try:
        async with httpx.AsyncClient(timeout=5.0) as http:
            await http.post(
                f"https://api.telegram.org/bot{token}/sendChatAction",
                json=payload,
            )
    except Exception:
        pass


async def _congratulate(
    chat_id: int,
    reply_to: int,
    seller: str,
    card: Dict[str, Optional[str]],
    thread_id: Optional[int] = None,
) -> None:
    """Har bir bot mustaqil: bittasining xatosi qolganlarini toʻxtatmaydi."""
    senders = [("oisha", "Oisha-OS Surgical COO", None, build_oisha_message(seller, card), _SEND_GAP_SECONDS)]
    for name, role, env_key, builder, delay in (
        ("amina", "Hermes Sales Coach", "AMINA_BOT_TOKEN", build_amina_message, 2.5),
        ("mrjon", "OpenClaw Master Closer", "MRJON_BOT_TOKEN", build_mrjon_message, 3.0),
    ):
        token = (os.getenv(env_key) or "").strip()
        if token:
            senders.append((name, role, token, builder(seller, card), delay))
        else:
            logger.warning(f"[SALES_CONGRATS] {env_key} sozlanmagan; {name} oʻtkazib yuborildi.")

    sent_count = 0
    for index, (name, role, token, text, delay) in enumerate(senders):
        if index and _SEND_GAP_SECONDS > 0:
            await asyncio.sleep(delay)
            if token:
                await _send_typing_via_bot_api(token, chat_id, thread_id)
                await asyncio.sleep(_TYPING_DURATION_SECONDS)
        try:
            if token:
                await _send_via_bot_api(token, chat_id, reply_to, text, thread_id)
            else:
                await _send_as_oisha(chat_id, reply_to, text)
            sent_count += 1
            logger.info(f"[SALES_CONGRATS] {name} ({role}) tabrik yubordi: chat={chat_id} msg={reply_to}")
        except Exception as exc:
            # Faqat turi va matni tokensiz xato: httpx xatosi URL (token) ni ochishi mumkin.
            detail = str(exc) if isinstance(exc, RuntimeError) else ""
            logger.error(f"[SALES_CONGRATS] {name} yubora olmadi: {type(exc).__name__} {detail}")

    logger.info(
        f"[SALES_CONGRATS] Tabrik yakunlandi: msg={reply_to} "
        f"muvaffaqiyatli={sent_count}/{len(senders)}"
    )


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

    seller = _seller_label(sender, card)
    logger.info(
        f"[SALES_CONGRATS] Toʻlov kartasi aniqlandi: msg={message_id} chat={chat_id} "
        f"sotuvchi={seller} summa={card.get('amount')} loyiha={card.get('project')}"
    )
    await _congratulate(chat_id, message_id, seller, card, _topic_id(event.message))
    # Tabrikdan keyin: bitim amoCRM da Won ga oʻtkazilganini tekshiradi.
    schedule_won_check(
        _send_as_oisha, chat_id, message_id, seller,
        sender_id=getattr(sender, "id", None), card_seller=card.get("seller"), db=db,
    )
