"""Sotuv guruhidagi "TOʻLOV TASDIQLASH" kartasiga uch botning alohida tabrigi.

Uchta alohida xarakter va texnologiya asosida:
1. Oisha AI: Oisha-OS Surgical COO (operatsion tasdiq va jamoaviy intizom/temp)
2. Amina AI: Hermes Empathetic Sales Coach (mehrli hamroh, insoniy va ruhiy dalda)
3. Mr.Jon AI: OpenClaw Founder Digital Twin (Master Closer, biznes gʻalabasi va motivatsiya)

Har bir agent Telegramda tabiiy insondek ("typing..." effekti va oraliq bilan) harakatlanadi.
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
    if clean and clean.endswith("a") and not clean.endswith("xon"):
        return f"{clean}xon"
    return clean or "Aziz jamoadoshim"


def build_oisha_message(seller: str, card: Dict[str, Optional[str]]) -> str:
    """Oisha-OS Surgical COO uslubidagi operatsion eʼtirof va temp bildirishnomasi."""
    project = f"{card['project']}: " if card.get("project") else ""
    return random.choice(OISHA_TEMPLATES).format(seller=seller, project=project, amount=card["amount"])


def build_amina_message(seller: str, card: Dict[str, Optional[str]]) -> str:
    """Hermes Sales Coach uslubidagi samimiy, mehrli va ruhiy quvvat tabrigi."""
    project = f"{card['project']}: " if card.get("project") else ""
    warm_name = _warm_seller_name(seller)
    return random.choice(AMINA_TEMPLATES).format(seller_warm=warm_name, project=project, amount=card["amount"])


def build_mrjon_message(seller: str, card: Dict[str, Optional[str]]) -> str:
    """OpenClaw Founder Digital Twin uslubidagi dadil, strategik savdo closing tabrigi."""
    project = f"{card['project']}: " if card.get("project") else ""
    return random.choice(MRJON_TEMPLATES).format(seller=seller, project=project, amount=card["amount"])


async def _send_as_oisha(chat_id: int, reply_to: int, text: str) -> None:
    """Oisha nomidan xabar yuborish: bot_client, ishlamasa userbot fallback."""
    if app_ctx.bot_client:
        try:
            await app_ctx.bot_client.send_message(chat_id, text, reply_to=reply_to, link_preview=False)
            return
        except Exception as exc:
            logger.warning(
                f"[SALES_CONGRATS] bot_client orqali yuborilmadi ({type(exc).__name__}), userbot fallback qoʻllanmoqda..."
            )
    if app_ctx.client:
        await app_ctx.client.send_message(chat_id, text, reply_to=reply_to, link_preview=False)
    else:
        raise RuntimeError("Neither bot_client nor userbot client available")


async def _send_via_bot_api(token: str, chat_id: int, reply_to: int, text: str) -> None:
    async with httpx.AsyncClient(timeout=_SEND_TIMEOUT_SECONDS) as http:
        response = await http.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": text,
                "reply_to_message_id": reply_to,
                "allow_sending_without_reply": True,
            },
        )
    if response.status_code != 200:
        raise RuntimeError(f"Bot API HTTP {response.status_code}")


async def _send_typing_via_bot_api(token: str, chat_id: int) -> None:
    """Telegramda xuddi inson yozayotgandek 'typing...' holatini koʻrsatadi."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as http:
            await http.post(
                f"https://api.telegram.org/bot{token}/sendChatAction",
                json={"chat_id": chat_id, "action": "typing"},
            )
    except Exception:
        pass


async def _congratulate(chat_id: int, reply_to: int, seller: str, card: Dict[str, Optional[str]]) -> None:
    """Har bir bot oʻz texnologiyasi, xarakteri va insoniy ritmi bilan javob beradi."""
    senders = [
        ("oisha", "Oisha-OS Surgical COO", None, build_oisha_message(seller, card), 1.2),
    ]

    amina_token = (os.getenv("AMINA_BOT_TOKEN") or "").strip()
    if amina_token:
        senders.append(("amina", "Hermes Sales Coach", amina_token, build_amina_message(seller, card), 2.5))
    else:
        logger.warning("[SALES_CONGRATS] AMINA_BOT_TOKEN sozlanmagan; Amina oʻtkazib yuborildi.")

    mrjon_token = (os.getenv("MRJON_BOT_TOKEN") or "").strip()
    if mrjon_token:
        senders.append(("mrjon", "OpenClaw Master Closer", mrjon_token, build_mrjon_message(seller, card), 3.0))
    else:
        logger.warning("[SALES_CONGRATS] MRJON_BOT_TOKEN sozlanmagan; Mr.Jon oʻtkazib yuborildi.")

    sent_count = 0
    for index, (name, role, token, text, delay) in enumerate(senders):
        if index:
            # Haqiqiy inson kabi oʻqish va yozish oraligʻi
            await asyncio.sleep(delay)
            if token:
                await _send_typing_via_bot_api(token, chat_id)
                await asyncio.sleep(1.5)

        try:
            if token:
                await _send_via_bot_api(token, chat_id, reply_to, text)
            else:
                await _send_as_oisha(chat_id, reply_to, text)
            sent_count += 1
            logger.info(f"[SALES_CONGRATS] {name} ({role}) tabrik yubordi: chat={chat_id} msg={reply_to}")
        except Exception as exc:
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

    chat_id, message_id = int(event.chat_id), int(event.id)
    sender = await event.get_sender()
    if getattr(sender, "bot", False):
        logger.debug(f"[SALES_CONGRATS] Bot xabari eʼtiborsiz qoldirildi: msg={message_id}")
        return
    if is_quiet_hours():
        logger.info(f"[SALES_CONGRATS] Quiet hours; tabrik yuborilmadi msg={message_id}")
        return

    db = app_ctx.msg_controller.db if app_ctx.msg_controller else None
    if not db:
        logger.warning("[SALES_CONGRATS] DB unavailable; dublikatdan himoya yoʻq, oʻtkazib yuborildi.")
        return

    state_key = f"sales_payment_congrats:{chat_id}:{message_id}"
    if await db.get_state(state_key):
        logger.info(f"[SALES_CONGRATS] Karta allaqachon tabriklangan, oʻtkazib yuborildi: msg={message_id}")
        return
    await db.set_state(state_key, "sent")

    seller = _seller_label(sender, card)
    logger.info(
        f"[SALES_CONGRATS] Toʻlov kartasi aniqlandi: msg={message_id} chat={chat_id} "
        f"sotuvchi={seller} summa={card.get('amount')} loyiha={card.get('project')}"
    )
    await _congratulate(chat_id, message_id, seller, card)
