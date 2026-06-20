"""
Hisobchi AI — Telethon userbot handlers.

Flow:
  1. Card bot message arrives (private from @HUMOcardbot / @CardXabarBot)
  2. Parse transaction
  3. Auto-categorize if merchant known, else ask finance group (correct topic)
  4. Finance group member replies → learn + save category

Entry points:
  handle_card_bot_message(event, client, engine)
  handle_finance_group_reply(event, client, engine)
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
import html
import logging
import os
import json
import re
from typing import Optional

from src.services.core.hisobchi_card_parser import (
    CARD_BOT_USERNAMES,
    parse_card_notification,
)
from src.services.core.hisobchi_engine import HisobchiEngine
from src.services.utils.gemini_fallback import generate_content_with_fallback
from src.settings import settings
from src.time_utils import get_local_now

logger = logging.getLogger(__name__)

_MAX_CATEGORY_LEN = 100
_MAX_REPLY_LEN = 500

# Cache: group_id → (kirim_topic_id, chiqim_topic_id) discovered at runtime
_topic_cache: dict[int, tuple[Optional[int], Optional[int]]] = {}
_finance_group_cache: Optional[int] = None
_FINANCE_GROUP_WORDS = frozenset(
    {"moliya", "finance", "buxgalter", "accounting", "hisobchi"}
)


def _get_finance_config() -> tuple[Optional[int], Optional[int], Optional[int]]:
    """Returns (group_id, kirim_topic_id, chiqim_topic_id)."""
    try:
        from src.settings import settings
        return (
            getattr(settings, "HISOBCHI_FINANCE_GROUP_ID", None),
            getattr(settings, "HISOBCHI_KIRIM_TOPIC_ID", None),
            getattr(settings, "HISOBCHI_CHIQIM_TOPIC_ID", None),
        )
    except Exception:
        return None, None, None


async def _discover_topics(
    client, group_id: int
) -> tuple[Optional[int], Optional[int]]:
    """Discover Kirim/Chiqim topic IDs via GetForumTopicsRequest (cached per process)."""
    if group_id in _topic_cache:
        return _topic_cache[group_id]

    kirim_id: Optional[int] = None
    chiqim_id: Optional[int] = None
    try:
        from telethon.tl.functions.messages import GetForumTopicsRequest

        result = await client(
            GetForumTopicsRequest(
                channel=group_id,
                q="",
                offset_date=0,
                offset_id=0,
                offset_topic=0,
                limit=100,
            )
        )
        for topic in getattr(result, "topics", []):
            title = (getattr(topic, "title", "") or "").strip().lower()
            tid = getattr(topic, "id", None)
            if title == "kirim":
                kirim_id = tid
            elif title == "chiqim":
                chiqim_id = tid
        logger.info(
            "[HISOBCHI] Topics discovered — Kirim: %s, Chiqim: %s", kirim_id, chiqim_id
        )
    except Exception as exc:
        logger.warning("[HISOBCHI] Topic auto-discovery failed: %s", exc)

    _topic_cache[group_id] = (kirim_id, chiqim_id)
    return kirim_id, chiqim_id


async def _resolve_topics(
    client, group_id: int, kirim_cfg: Optional[int], chiqim_cfg: Optional[int]
) -> tuple[Optional[int], Optional[int]]:
    """Use .env values if set; otherwise auto-discover from the group."""
    if kirim_cfg is not None and chiqim_cfg is not None:
        return kirim_cfg, chiqim_cfg
    disc_kirim, disc_chiqim = await _discover_topics(client, group_id)
    return (
        kirim_cfg if kirim_cfg is not None else disc_kirim,
        chiqim_cfg if chiqim_cfg is not None else disc_chiqim,
    )


async def _discover_finance_group(client) -> Optional[int]:
    """Find the finance group without mistaking generic report groups for it."""
    global _finance_group_cache
    if _finance_group_cache is not None:
        return _finance_group_cache

    try:
        dialogs = await client.get_dialogs(limit=500)
        for dialog in dialogs:
            title = (
                getattr(dialog, "name", None)
                or getattr(getattr(dialog, "entity", None), "title", None)
                or ""
            )
            words = set(re.findall(r"[\w'’]+", title.casefold(), flags=re.UNICODE))
            if words & _FINANCE_GROUP_WORDS:
                group_id = getattr(dialog, "id", None)
                if group_id is not None:
                    _finance_group_cache = int(group_id)
                    logger.info(
                        "[HISOBCHI] Finance group discovered: %s (%s)",
                        title,
                        _finance_group_cache,
                    )
                    return _finance_group_cache
    except Exception as exc:
        logger.warning("[HISOBCHI] Finance group discovery failed: %s", exc)
    return None


async def resolve_finance_destination(
    client,
) -> tuple[Optional[int], Optional[int], Optional[int]]:
    """Resolve group and Kirim/Chiqim topics from config, Telegram, or safe fallback."""
    configured_group, kirim_cfg, chiqim_cfg = _get_finance_config()
    group_id = configured_group or await _discover_finance_group(client)
    if group_id is None:
        team_group_id = getattr(settings, "TEAM_GROUP_ID", None)
        if team_group_id:
            team_kirim, team_chiqim = await _resolve_topics(
                client, int(team_group_id), kirim_cfg, chiqim_cfg
            )
            if team_kirim is not None or team_chiqim is not None:
                logger.info(
                    "[HISOBCHI] Finance topics found in TEAM_GROUP_ID: %s",
                    team_group_id,
                )
                return int(team_group_id), team_kirim, team_chiqim
        logger.error(
            "[HISOBCHI] Finance destination is not configured or discoverable; "
            "card details will not be sent to a generic group."
        )
        return None, None, None

    kirim_topic, chiqim_topic = await _resolve_topics(
        client, int(group_id), kirim_cfg, chiqim_cfg
    )
    return int(group_id), kirim_topic, chiqim_topic


def _pick_topic(direction: str, kirim_topic: Optional[int], chiqim_topic: Optional[int]) -> Optional[int]:
    if direction == "in":
        return kirim_topic
    return chiqim_topic


async def handle_card_bot_message(event, client, engine: HisobchiEngine) -> bool:
    """Called when @HUMOcardbot or @CardXabarBot sends a message."""
    sender = await event.get_sender()
    username = (getattr(sender, "username", None) or "").lower()
    if username not in CARD_BOT_USERNAMES:
        return False

    text = event.message.message or ""
    tx = parse_card_notification(username, text)
    if not tx:
        logger.warning("[HISOBCHI] Could not parse card message from @%s", username)
        return False

    finance_group_id, kirim_topic_id, chiqim_topic_id = (
        await resolve_finance_destination(client)
    )

    topic_id = _pick_topic(tx.direction, kirim_topic_id, chiqim_topic_id)

    known_rule = await engine.get_known_rule(
        tx.merchant, tx.card_suffix, tx.direction, tx.amount
    )
    category = known_rule["category"] if known_rule else None
    ownership = known_rule["ownership"] if known_rule else "business"
    tx_id, created = await engine.save_transaction_once(
        source_bot=tx.source_bot,
        direction=tx.direction,
        amount=tx.amount,
        merchant=tx.merchant,
        card_suffix=tx.card_suffix,
        tx_time=tx.tx_time,
        balance=tx.balance,
        raw_text=text,
        category=category,
        ownership=ownership,
        status="categorized" if known_rule else "pending",
        source_message_id=getattr(getattr(event, "message", None), "id", None),
    )
    if not created:
        logger.info("[HISOBCHI] Duplicate transaction ignored: #%s", tx_id)
        return True

    if known_rule:
        logger.info("[HISOBCHI] Auto-categorized tx #%s → %s", tx_id, category)

        if finance_group_id:
            try:
                await client.send_message(
                    finance_group_id,
                    engine.build_auto_msg(tx, category, ownership),
                    parse_mode="html",
                    reply_to=topic_id,
                )
            except Exception as exc:
                logger.error("[HISOBCHI] Failed to notify finance group: %s", exc)
    else:
        logger.info("[HISOBCHI] New tx #%s, asking finance group", tx_id)

        if finance_group_id:
            try:
                sent = await client.send_message(
                    finance_group_id,
                    engine.build_finance_question(tx, tx_id),
                    parse_mode="html",
                    reply_to=topic_id,
                )
                await engine.update_finance_msg(
                    tx_id,
                    finance_msg_id=sent.id,
                    finance_chat_id=finance_group_id,
                )
            except Exception as exc:
                logger.error("[HISOBCHI] Failed to send question to finance group: %s", exc)
        else:
            logger.warning(
                "[HISOBCHI] Finance group not found — question not sent"
            )
    return True


async def handle_finance_group_reply(event, client, engine: HisobchiEngine) -> bool:
    """
    Called for messages in the finance group.
    Returns True if this was a hisobchi reply (so caller can skip other processing).
    """
    finance_group_id, _, _ = await resolve_finance_destination(client)
    if not finance_group_id:
        return False

    if event.chat_id != finance_group_id:
        return False

    msg = event.message
    reply_to = getattr(msg, "reply_to", None)
    if not reply_to:
        return False

    replied_msg_id = getattr(reply_to, "reply_to_msg_id", None)
    if not replied_msg_id:
        return False

    # First find the linked transaction so /skip without ID also works
    tx = await engine.get_pending_by_finance_msg(
        finance_chat_id=finance_group_id,
        finance_msg_id=replied_msg_id,
    )
    if not tx:
        return False  # Not a hisobchi question reply

    text = (msg.message or "").strip()

    # /skip — with or without explicit tx ID
    if text.lower().startswith("/skip"):
        await engine.skip(tx["id"])
        await event.reply("⏭ O'tkazib yuborildi.")
        return True

    if not text or text.startswith("/"):
        return False

    if len(text) > _MAX_REPLY_LEN:
        await event.reply(
            f"⚠️ Izoh juda uzun (maksimal {_MAX_REPLY_LEN} belgi). "
            "Iltimos, qisqaroq yozing."
        )
        return True

    reason = text
    ownership = "business"
    lower_text = text.casefold()
    if any(w in lower_text for w in ["shaxsiy", "personal", "shaxsy"]):
        ownership = "personal"

    # "Kategoriya | batafsil sabab" is the explicit format. A plain answer
    # remains useful too: it becomes both the category label and audit reason.
    category = re.split(r"\s*\|\s*|\r?\n", text, maxsplit=1)[0].strip()
    category = re.sub(
        r"\s*,?\s*(shaxsiy|personal|shaxsy)\s*$",
        "",
        category,
        flags=re.IGNORECASE,
    ).strip()
    if not category:
        await event.reply("⚠️ Toifa yoki sabab matnini yozing.")
        return True
    if len(category) > _MAX_CATEGORY_LEN:
        category = category[:_MAX_CATEGORY_LEN].rstrip()

    tx_id = tx["id"]
    merchant = tx["merchant"]

    await engine.categorize(tx_id, category, ownership, reason=reason)
    await engine.learn_rule(
        merchant=merchant,
        card_suffix=tx.get("card_suffix", ""),
        direction=tx["direction"],
        amount=int(tx["amount"]),
        category=category,
        ownership=ownership,
    )

    amount_str = f"{tx['amount']:,}".replace(",", " ")
    direction_icon = "➖" if tx["direction"] == "out" else "➕"
    own_label = "Biznes" if ownership == "business" else "Shaxsiy"
    await event.reply(
        f"✅ Saqlandi!\n"
        f"{direction_icon} {amount_str} UZS — <b>{html.escape(category)} ({own_label})</b>\n"
        f"📍 {html.escape(merchant)}\n"
        f"🧠 Keyingi safar avtomatik qo'yiladi.",
        parse_mode="html",
    )
    logger.info("[HISOBCHI] tx #%s categorized as '%s' (%s), exact rule learned", tx_id, category, ownership)
    return True


def is_card_bot_sender(sender) -> bool:
    username = (getattr(sender, "username", None) or "").lower()
    return username in CARD_BOT_USERNAMES


class _CardBackfillEvent:
    """Small event adapter used only for card-bot history replay."""

    def __init__(self, message, sender) -> None:
        self.message = message
        self.id = getattr(message, "id", None)
        self.is_private = True
        self.out = False
        self._sender = sender

    async def get_sender(self):
        return self._sender


async def backfill_card_bot_messages(
    client,
    engine: HisobchiEngine,
    *,
    limit: int = 50,
    max_age_hours: int = 72,
    delay_seconds: float = 0.05,
) -> dict[str, int]:
    """Replay recent card notifications once after boot, with deduplication."""
    stats = {"scanned": 0, "created": 0, "duplicates": 0, "errors": 0}
    cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)

    for username in sorted(CARD_BOT_USERNAMES):
        try:
            entity = await client.get_entity(username)
            messages = []
            async for message in client.iter_messages(entity, limit=limit):
                message_date = getattr(message, "date", None)
                if message_date is not None:
                    if message_date.tzinfo is None:
                        message_date = message_date.replace(tzinfo=timezone.utc)
                    if message_date < cutoff:
                        break
                messages.append(message)

            for message in reversed(messages):
                stats["scanned"] += 1
                try:
                    text = getattr(message, "message", None) or ""
                    tx = parse_card_notification(username, text)
                    if tx is None:
                        continue
                    existed = await engine.transaction_exists(
                        source_bot=tx.source_bot,
                        direction=tx.direction,
                        amount=tx.amount,
                        merchant=tx.merchant,
                        card_suffix=tx.card_suffix,
                        tx_time=tx.tx_time,
                        source_message_id=getattr(message, "id", None),
                    )
                    if existed:
                        stats["duplicates"] += 1
                        continue
                    await handle_card_bot_message(
                        _CardBackfillEvent(message, entity), client, engine
                    )
                    stats["created"] += 1
                except Exception as exc:
                    stats["errors"] += 1
                    logger.warning(
                        "[HISOBCHI] Backfill message failed bot=%s id=%s: %s",
                        username,
                        getattr(message, "id", None),
                        exc,
                    )
                if delay_seconds:
                    await asyncio.sleep(delay_seconds)
        except Exception as exc:
            stats["errors"] += 1
            logger.warning("[HISOBCHI] Backfill source @%s failed: %s", username, exc)

    logger.info("[HISOBCHI] Backfill finished: %s", stats)
    return stats


# ── VOICE PROCESSING & TRANSACTION EXTRACTION ─────────────────────────────

async def parse_transaction_text_with_llm(client, model_name: str, text: str) -> Optional[dict]:
    """Uses Gemini to parse transaction parameters from Uzbek natural language text."""
    system_prompt = """
    Foydalanuvchining o'zbek tilidagi ovozli xabar matnini (transkript) tahlil qiling va undan quyidagi ma'lumotlarni JSON formatida ajratib oling:
    - is_transaction (boolean): Matnda moliyaviy tranzaksiya (xarajat, kirim, to'lov, avans, ish haqi, tushum va hk) haqida gap ketganmi?
    - amount (integer): Tranzaksiya summasi (so'mda, faqat butun son). Agar aniq aytilmagan bo'lsa 0. (Masalan: "ellik ming" -> 50000, "bir yarim million" -> 1500000)
    - direction (string): 'out' (chiqim/xarajat/to'lov/avans bo'lsa) yoki 'in' (kirim/tushum/avans tushishi bo'lsa). Default: 'out'.
    - merchant (string): To'lov qilingan joy, do'kon, shaxs yoki xizmat nomi (masalan: "Korzinka", "Yandex Taxi", "Paynet", "Mijoz", "Ofis"). Maksimal 50 ta belgi. Agar aniq aytilmagan bo'lsa, xarajat yo'nalishiga qarab o'zingiz nom bering.
    - category (string): Xarajat/kirim toifasi (masalan: "Taksi", "Tushlik", "Ofis xarajati", "Marketing", "Dizayn xizmati", "Shaxsiy xarajat"). Maksimal 50 ta belgi.
    - ownership (string): 'business' (biznes/agentlik moliyasi bo'lsa) yoki 'personal' (shaxsiy/ro'zg'or moliyasi bo'lsa). Agar matnda "shaxsiy", "o'zimniki", "uyga", "ro'zg'orga", "shaxsiy xarajat", "shaxsiy ehtiyoj" kabi so'zlar bo'lsa yoki shaxsiy moliya ekani aniq aytilgan bo'lsa, 'personal' deb belgilang. Aks holda default: 'business'.
    - reason (string): Tranzaksiyaning batafsil sababi yoki izohi.

    Faqat va faqat JSON formatida javob bering, hech qanday markdown formatlashsiz (```json kabi taglarsiz), faqat toza JSON satri bo'lsin.
    Misol:
    {
      "is_transaction": true,
      "amount": 50000,
      "direction": "out",
      "merchant": "Paynet",
      "category": "Kantselyariya",
      "ownership": "business",
      "reason": "ofis uchun qog'oz"
    }
    """
    try:
        response, _ = await generate_content_with_fallback(
            client=client,
            primary_model=model_name,
            contents=[system_prompt, f"Tahlil qilinadigan matn:\n\"{text}\""],
            env_name="GEMINI_VOICE_FALLBACK_MODELS",
            log_prefix="[HISOBCHI-LLM]",
        )
        if response and response.text:
            cleaned_text = response.text.strip().replace("```json", "").replace("```", "").strip()
            return json.loads(cleaned_text)
    except Exception as exc:
        logger.error("[HISOBCHI] LLM parse transaction failed: %s", exc)
    return None


async def process_finance_voice_message(
    event, client, engine: HisobchiEngine, voice_processor
) -> bool:
    """
    Downloads, transcribes, and processes a voice message for finance tracking.
    Can be a reply to a transaction question, or a standalone transaction log.
    Returns True if processed successfully, False otherwise.
    """
    msg = event.message
    if not getattr(msg, "voice", None):
        return False

    temp_path = f"temp_hisobchi_voice_{event.id}.ogg"
    try:
        # 1. Download
        await client.download_media(msg, file=temp_path)

        # 2. Transcribe
        transcript = await voice_processor.transcribe(temp_path, mode="voice")
        if not transcript:
            logger.warning("[HISOBCHI-VOICE] Transcription returned empty result")
            return False

        text_to_parse = transcript
        if "Matn:" in transcript:
            parts = transcript.split("|")
            for part in parts:
                if "Matn:" in part:
                    text_to_parse = part.replace("Matn:", "").strip()
                    break

        logger.info("[HISOBCHI-VOICE] Transcribed: %s", text_to_parse)

        # 3. Parse with LLM
        parsed = await parse_transaction_text_with_llm(
            client=voice_processor.client,
            model_name=voice_processor.model_name,
            text=text_to_parse,
        )
        if not parsed:
            logger.warning("[HISOBCHI-VOICE] LLM failed to parse transcript: %s", text_to_parse)
            return False

        if not parsed.get("is_transaction"):
            logger.info("[HISOBCHI-VOICE] Not a transaction voice message: %s", text_to_parse)
            return False

        amount = parsed.get("amount", 0)
        direction = parsed.get("direction", "out")
        merchant = parsed.get("merchant", "Noma'lum")
        category = parsed.get("category", "Boshqa")
        ownership = parsed.get("ownership", "business")
        reason = parsed.get("reason", "")

        # 4. Check if it is a reply to a question
        reply_to = getattr(msg, "reply_to", None)
        replied_msg_id = getattr(reply_to, "reply_to_msg_id", None) if reply_to else None

        tx = None
        finance_group_id, _, _ = await resolve_finance_destination(client)
        if replied_msg_id and finance_group_id:
            tx = await engine.get_pending_by_finance_msg(
                finance_chat_id=finance_group_id,
                finance_msg_id=replied_msg_id,
            )

        if tx:
            # Reply flow: update the pending transaction
            tx_id = tx["id"]
            merchant = tx["merchant"]  # use original merchant from card notification

            await engine.categorize(tx_id, category, ownership, reason=reason)
            await engine.learn_rule(
                merchant=merchant,
                card_suffix=tx.get("card_suffix", ""),
                direction=tx["direction"],
                amount=int(tx["amount"]),
                category=category,
                ownership=ownership,
            )

            amount_str = f"{tx['amount']:,}".replace(",", " ")
            direction_icon = "➖" if tx["direction"] == "out" else "➕"
            own_label = "Biznes" if ownership == "business" else "Shaxsiy"

            await event.reply(
                f"🎙️ <b>Ovozli javob saqlandi!</b>\n"
                f"{direction_icon} {amount_str} UZS — <b>{html.escape(category)} ({own_label})</b>\n"
                f"📍 {html.escape(merchant)}\n"
                f"🧠 Keyingi safar avtomatik toifalanadi.",
                parse_mode="html",
            )
            logger.info("[HISOBCHI-VOICE] tx #%s categorized as '%s' (%s) from voice reply", tx_id, category, ownership)
            return True
        else:
            # Standalone flow: create a new manual transaction
            if amount <= 0:
                await event.reply("⚠️ Ovozli xabardan tranzaksiya summasini aniqlab bo'lmadi. Iltimos, summani aniqroq ayting.")
                return True

            tx_time_str = get_local_now().strftime("%H:%M %d.%m.%Y")

            tx_id = await engine.save_transaction(
                source_bot="voice",
                direction=direction,
                amount=amount,
                merchant=merchant,
                card_suffix="",
                tx_time=tx_time_str,
                balance=None,
                raw_text=text_to_parse,
                category=category,
                ownership=ownership,
                status="categorized",
                reason=reason,
            )

            amount_str = f"{amount:,}".replace(",", " ")
            direction_icon = "➖ Chiqim" if direction == "out" else "➕ Kirim"
            own_label = "Biznes" if ownership == "business" else "Shaxsiy"
            reason_line = f"\n📝 Izoh: {reason}" if reason else ""

            await event.reply(
                f"🎙️ <b>Ovozli to'lov #{tx_id} saqlandi!</b>\n\n"
                f"{direction_icon}: <b>{amount_str} UZS</b> ({own_label})\n"
                f"📍 {html.escape(merchant)}\n"
                f"🗂 Toifa: <b>{html.escape(category)}</b>"
                f"{html.escape(reason_line)}",
                parse_mode="html",
            )
            logger.info("[HISOBCHI-VOICE] Manual tx #%s saved as '%s' (%s) from standalone voice", tx_id, category, ownership)
            return True

    except Exception as exc:
        logger.error("[HISOBCHI-VOICE] Error processing voice transaction: %s", exc, exc_info=True)
    finally:
        if os.path.exists(temp_path):
            await voice_processor.cleanup(temp_path)

    return False

