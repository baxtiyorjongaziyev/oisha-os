"""AI ROP daily scheduler — 3 timed slots (09:00 / 14:00 / 18:30 Tashkent),
Mon–Sat, seller DMs + CEO + Sales Group (-1003854308552 topic 115)."""
from __future__ import annotations

import asyncio
import logging
import os

from src.context import app_ctx
from src.database import get_db
from src.services.core.rop.fetchers import RopFetcher
from src.services.core.rop.service import RopService
from src.services.core.rop.targets import ensure_ssot_roster
from src.services.core.telegram.bot_runtime import TelethonBotRuntime
from src.time_utils import get_local_now, is_quiet_hours

logger = logging.getLogger("RopScheduler")

_SLOT_TIMES = {"morning": (9, 0), "midday": (14, 0), "evening": (18, 30)}
DEFAULT_SALES_GROUP_ID = -1003854308552
DEFAULT_SALES_TOPIC_ID = 115


def _as_bot_runtime(bot_client):
    if bot_client is None:
        return None
    if hasattr(bot_client, "backend") and hasattr(bot_client, "send_message"):
        return bot_client
    return TelethonBotRuntime(bot_client)


def _enabled() -> bool:
    return os.getenv("ROP_ENABLED", "").strip().lower() in {"1", "true", "yes", "on"}


def _ceo_chat_id() -> int | None:
    raw = os.getenv("ROP_CEO_CHAT_ID", "").strip()
    try:
        return int(raw) if raw else None
    except ValueError:
        return None


def _sales_group_destination() -> tuple[int | None, int | None]:
    raw_grp = os.getenv("ROP_SALES_GROUP_ID", "").strip()
    if not raw_grp:
        return None, None
    try:
        grp_id = int(raw_grp)
    except ValueError:
        return None, None

    raw_topic = os.getenv("ROP_SALES_TOPIC_ID", str(DEFAULT_SALES_TOPIC_ID)).strip()
    try:
        topic_id = int(raw_topic) if raw_topic else None
    except ValueError:
        topic_id = DEFAULT_SALES_TOPIC_ID
    return grp_id, topic_id


def _build_service(bot_runtime, now_fn) -> RopService:
    amocrm = app_ctx.msg_controller.crm.amocrm
    db = get_db()
    return RopService(
        db.rop,
        RopFetcher(amocrm),
        ceo_chat_id=_ceo_chat_id(),
        now_fn=now_fn,
    )


async def _send_with_retry(bot_runtime, chat_id: int, text: str, topic_id: int | None = None) -> bool:
    for attempt in (1, 2):
        try:
            if topic_id is not None:
                try:
                    await bot_runtime.send_message(
                        chat_id, text, parse_mode="HTML", message_thread_id=topic_id
                    )
                except TypeError:
                    await bot_runtime.send_message(chat_id, text, parse_mode="HTML")
            else:
                await bot_runtime.send_message(chat_id, text, parse_mode="HTML")
            return True
        except Exception as exc:  # noqa: BLE001
            if attempt == 2:
                logger.warning("[ROP] send to %s dropped: %s", chat_id, exc)
    return False


async def run_rop_slot(slot: str, bot_runtime, *, now_fn=get_local_now) -> int:
    now = now_fn()
    if not _enabled():
        return 0
    if os.getenv("DISABLE_UNSOLICITED_REPORTS", "").strip() == "1":
        return 0
    if now.weekday() == 6:  # Sunday
        return 0
    if is_quiet_hours(now):
        return 0

    try:
        service = _build_service(bot_runtime, now_fn)
        if hasattr(service, "_repo") and hasattr(service._repo, "upsert_target"):
            try:
                await ensure_ssot_roster(service._repo)
            except Exception as exc:  # noqa: BLE001
                logger.debug("[ROP] ensure_ssot_roster notice: %s", exc)
        plan = await service.run(slot)
    except Exception:
        logger.exception("[ROP] %s slot failed to build plan", slot)
        return 0

    sent = 0
    ceo_id = _ceo_chat_id()
    ceo_summary_text: str | None = None

    for chat_id, text in plan:
        if ceo_id and chat_id == ceo_id:
            ceo_summary_text = text
        if await _send_with_retry(bot_runtime, chat_id, text):
            sent += 1

    # Mirror consolidated ROP summary to Sales Group topic when configured
    grp_id, topic_id = _sales_group_destination()
    if grp_id and ceo_summary_text and grp_id != ceo_id:
        if await _send_with_retry(bot_runtime, grp_id, ceo_summary_text, topic_id=topic_id):
            sent += 1

    logger.info("[ROP] %s slot: %s messages sent", slot, sent)
    return sent


async def _slot_loop(slot: str, bot_runtime) -> None:
    hour, minute = _SLOT_TIMES[slot]
    await asyncio.sleep(15)
    last_run_date = None
    logger.info("[ROP] %s loop started (%02d:%02d Tashkent)", slot, hour, minute)
    while True:
        try:
            now = get_local_now()
            today = now.strftime("%Y-%m-%d")
            if now.hour == hour and now.minute == minute and last_run_date != today:
                await run_rop_slot(slot, bot_runtime)
                last_run_date = today
        except Exception:
            logger.exception("[ROP] %s loop iteration error", slot)
        await asyncio.sleep(30)


async def morning_loop(bot_runtime) -> None:
    await _slot_loop("morning", bot_runtime)


async def midday_loop(bot_runtime) -> None:
    await _slot_loop("midday", bot_runtime)


async def evening_loop(bot_runtime) -> None:
    await _slot_loop("evening", bot_runtime)


def start_rop_schedulers(bot_runtime) -> None:
    rt = _as_bot_runtime(bot_runtime)
    asyncio.create_task(morning_loop(rt), name="rop_morning_loop")
    asyncio.create_task(midday_loop(rt), name="rop_midday_loop")
    asyncio.create_task(evening_loop(rt), name="rop_evening_loop")
