"""Daily CEO insights (top sellers / KPI actions / at-risk clients).

Runs Mon–Sat at DAILY_INSIGHTS_TIME (default 09:15 Tashkent) and sends one
message to ROP_CEO_CHAT_ID. Gated by DAILY_INSIGHTS_ENABLED (default off).
"""
from __future__ import annotations

import asyncio
import logging
import os

from src.context import app_ctx
from src.database import get_db
from src.schedulers.rop_scheduler import _as_bot_runtime, _ceo_chat_id
from src.services.core.rop.config import load_config, seed_config
from src.services.core.rop.fetchers import RopFetcher
from src.services.core.rop.insights import collect, render
from src.services.core.rop.targets import load_roster
from src.time_utils import get_local_now, is_quiet_hours

logger = logging.getLogger("DailyInsights")


def _enabled() -> bool:
    return os.getenv("DAILY_INSIGHTS_ENABLED", "").strip().lower() in {"1", "true", "yes", "on"}


def _slot_time() -> tuple[int, int]:
    raw = os.getenv("DAILY_INSIGHTS_TIME", "09:15").strip()
    try:
        h, m = raw.split(":")
        return int(h), int(m)
    except ValueError:
        return 9, 15


async def run_daily_insights(bot_runtime, *, now_fn=get_local_now, fetcher=None, repo=None) -> bool:
    now = now_fn()
    chat_id = _ceo_chat_id()
    if not _enabled() or not chat_id or bot_runtime is None:
        return False
    if now.weekday() == 6 or is_quiet_hours(now):
        return False
    try:
        repo = repo or get_db().rop
        await seed_config(repo)
        config = await load_config(repo)
        roster = await load_roster(repo)
        fetcher = fetcher or RopFetcher(app_ctx.msg_controller.crm.amocrm)
        text = render(await collect(fetcher, roster, config, now))
    except Exception:
        logger.exception("[INSIGHTS] build failed")
        return False
    try:
        await bot_runtime.send_message(chat_id, text, parse_mode="HTML")
    except Exception as exc:  # noqa: BLE001
        logger.warning("[INSIGHTS] send failed: %s", exc)
        return False
    logger.info("[INSIGHTS] daily insights sent")
    return True


async def daily_insights_loop(bot_runtime) -> None:
    rt = _as_bot_runtime(bot_runtime)
    hour, minute = _slot_time()
    await asyncio.sleep(20)
    last_run_date = None
    logger.info("[INSIGHTS] loop started (%02d:%02d Tashkent)", hour, minute)
    while True:
        try:
            now = get_local_now()
            today = now.strftime("%Y-%m-%d")
            if now.hour == hour and now.minute == minute and last_run_date != today:
                await run_daily_insights(rt)
                last_run_date = today
        except Exception:
            logger.exception("[INSIGHTS] loop iteration error")
        await asyncio.sleep(30)
