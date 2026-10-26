"""Jamoa ritmi: jamoa guruhiga jadval bo'yicha xabarlar (Toshkent vaqti, ``get_local_now``).

  Dushanba            09:00  haftalik start (1–3 maqsad)
  Seshanba–Juma       09:00  ertalabki start (vazifa, to'siq, yordam)
  Dushanba–Payshanba  17:30  kun yakuni (bir qatorda natija)
  Juma                16:00  haftalik retro (AI, haftalik suhbatdan)
  Juma                17:00  egaga shaxsiy o'z-o'zini tahlil (AI)

Har bir slot kuniga bir marta yuboriladi: ``jamoa_ritm_log`` jadvali qayta ishga tushganda
ham takrorlanishning oldini oladi. Slot vaqtidan keyin ``GRACE_MINUTES`` ichida yuborilmasa,
o'sha kun o'tkazib yuboriladi (kechikkan xabar yubormaslik uchun).
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Callable, Optional

from src.services.core.jamoa_ritm import texts
from src.services.core.jamoa_ritm.brain import HamrohBrain
from src.services.core.jamoa_ritm.config import JamoaConfig, load_config
from src.services.core.jamoa_ritm.store import ROLE_RITM, JamoaStore

logger = logging.getLogger(__name__)

GRACE_MINUTES = 30
WEEK_SECONDS = 7 * 24 * 3600
RETENTION_DAYS = 35


@dataclass(frozen=True)
class Slot:
    key: str
    days: frozenset  # 0 = Dushanba … 6 = Yakshanba
    hour: int
    minute: int
    target: str  # "group" yoki "owner"


SLOTS: tuple[Slot, ...] = (
    Slot("haftalik_start", frozenset({0}), 9, 0, "group"),
    Slot("ertalabki_start", frozenset({1, 2, 3, 4}), 9, 0, "group"),
    Slot("kun_yakuni", frozenset({0, 1, 2, 3}), 17, 30, "group"),
    Slot("haftalik_retro", frozenset({4}), 16, 0, "group"),
    Slot("ozini_tahlil", frozenset({4}), 17, 0, "owner"),
)


def slot_due(slot: Slot, now: datetime, grace_minutes: int = GRACE_MINUTES) -> bool:
    if now.weekday() not in slot.days:
        return False
    start = now.replace(hour=slot.hour, minute=slot.minute, second=0, microsecond=0)
    return start <= now < start + timedelta(minutes=grace_minutes)


async def build_text(
    slot: Slot,
    now: datetime,
    *,
    cfg: JamoaConfig,
    store: JamoaStore,
    brain: HamrohBrain,
    bot_username: Optional[str] = None,
) -> str:
    day = now.date()
    if slot.key == "haftalik_start":
        return texts.haftalik_start(day, bot_username)
    if slot.key == "ertalabki_start":
        return texts.ertalabki_start(day, bot_username)
    if slot.key == "kun_yakuni":
        return texts.kun_yakuni(day, bot_username)
    week_ago = int(now.timestamp()) - WEEK_SECONDS
    messages = await store.recent_messages(cfg.group_id, week_ago, limit=400)
    if slot.key == "haftalik_retro":
        return await brain.weekly_retro(messages)
    return await brain.self_review(messages)


async def _send(bot: Any, chat_id: int, text: str) -> bool:
    try:
        await bot.send_message(chat_id, text, disable_web_page_preview=True)
        return True
    except Exception:
        logger.error("[JAMOA-RITM] Xabar yuborilmadi chat=%s", chat_id, exc_info=True)
        return False


async def run_due_slots(
    now: datetime,
    *,
    cfg: JamoaConfig,
    store: JamoaStore,
    brain: HamrohBrain,
    bot: Any,
    bot_username: Optional[str] = None,
) -> list[str]:
    """Hozir vaqti kelgan va bugun yuborilmagan slotlarni yuboradi. Yuborilganlar ro'yxati."""
    sent: list[str] = []
    sana = now.date().isoformat()
    for slot in SLOTS:
        if not slot_due(slot, now) or await store.was_sent(slot.key, sana):
            continue
        chat_id = cfg.group_id if slot.target == "group" else cfg.owner_id
        if not chat_id:
            logger.warning("[JAMOA-RITM] %s uchun manzil yo'q (JAMOA_OWNER_ID/OWNER_ID).", slot.key)
            continue
        text = await build_text(slot, now, cfg=cfg, store=store, brain=brain, bot_username=bot_username)
        if not await _send(bot, chat_id, text):
            continue
        await store.mark_sent(slot.key, sana)
        if slot.target == "group":
            await store.save_message(chat_id=chat_id, text=text, user_name="Oisha", role=ROLE_RITM)
        logger.info("[JAMOA-RITM] %s yuborildi.", slot.key)
        sent.append(slot.key)
    return sent


async def _bot_username(bot_runtime: Any) -> Optional[str]:
    try:
        raw_bot = getattr(bot_runtime, "bot", None)
        if raw_bot is not None and hasattr(raw_bot, "me"):
            return (await raw_bot.me()).username
        client = getattr(bot_runtime, "client", None)
        if client is not None and hasattr(client, "get_me"):
            return (await client.get_me()).username
    except Exception:
        logger.warning("[JAMOA-RITM] Bot username aniqlanmadi.", exc_info=True)
    return None


async def jamoa_ritm_loop(
    bot_runtime: Any,
    *,
    interval_seconds: int = 30,
    config_loader: Callable[[], JamoaConfig] = load_config,
    store: Optional[JamoaStore] = None,
    brain: Optional[HamrohBrain] = None,
    clock: Optional[Callable[[], datetime]] = None,
) -> None:
    from src.time_utils import get_local_now

    clock = clock or get_local_now
    store = store or JamoaStore()
    brain = brain or HamrohBrain()
    username: Optional[str] = None
    last_prune = None
    await asyncio.sleep(20)
    logger.info("[JAMOA-RITM] Loop ishga tushdi.")
    while True:
        try:
            cfg = config_loader()
            now = clock()
            if cfg.ritm_active and bot_runtime is not None:
                username = username or await _bot_username(bot_runtime)
                await run_due_slots(
                    now, cfg=cfg, store=store, brain=brain, bot=bot_runtime, bot_username=username
                )
            if cfg.group_id and last_prune != now.date():
                await store.prune(int(now.timestamp()) - RETENTION_DAYS * 86400)
                last_prune = now.date()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.error("[JAMOA-RITM] Loop xatosi.", exc_info=True)
        await asyncio.sleep(interval_seconds)
