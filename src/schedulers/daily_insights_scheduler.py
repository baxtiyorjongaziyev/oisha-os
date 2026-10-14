"""Daily CEO insights (top sellers / KPI actions / at-risk clients).

Runs Mon–Sat at DAILY_INSIGHTS_TIME (default 09:15 Tashkent) and sends one
message to ROP_CEO_CHAT_ID. Gated by DAILY_INSIGHTS_ENABLED (default off).

Also hosts the weekly Sales Intel report (amoCRM + Moizvonki + Airtable),
Mondays at SALES_INTEL_TIME (default 10:00), gated by SALES_INTEL_ENABLED.
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
from src.services.core.rop import sales_intel
from src.services.core.rop.insights import collect, render
from src.services.core.rop.targets import load_roster
from src.time_utils import get_local_now, is_quiet_hours

logger = logging.getLogger("DailyInsights")


def _flag(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _enabled() -> bool:
    return _flag("DAILY_INSIGHTS_ENABLED")


def _hhmm(env: str, default: str) -> tuple[int, int]:
    raw = os.getenv(env, default).strip()
    try:
        h, m = raw.split(":")
        return int(h), int(m)
    except ValueError:
        h, m = default.split(":")
        return int(h), int(m)


def _slot_time() -> tuple[int, int]:
    return _hhmm("DAILY_INSIGHTS_TIME", "09:15")


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


def _default_airtable():
    try:
        from src.services.core.airtable import AirtableSync
        return AirtableSync()
    except Exception:  # noqa: BLE001
        logger.warning("[SALES-INTEL] Airtable unavailable; skipping project sections")
        return None


async def run_sales_intel(bot_runtime, *, now_fn=get_local_now, fetcher=None,
                          repo=None, airtable=None) -> bool:
    now = now_fn()
    chat_id = _ceo_chat_id()
    if not _flag("SALES_INTEL_ENABLED") or not chat_id or bot_runtime is None:
        return False
    if is_quiet_hours(now):
        return False
    try:
        roster = await load_roster(repo or get_db().rop)
        fetcher = fetcher or RopFetcher(app_ctx.msg_controller.crm.amocrm)
        airtable = airtable if airtable is not None else _default_airtable()
        text = sales_intel.render(await sales_intel.collect(fetcher, airtable, roster, now))
    except Exception:
        logger.exception("[SALES-INTEL] build failed")
        return False
    try:
        await bot_runtime.send_message(chat_id, text, parse_mode="HTML")
    except Exception as exc:  # noqa: BLE001
        logger.warning("[SALES-INTEL] send failed: %s", exc)
        return False
    logger.info("[SALES-INTEL] weekly report sent")
    return True


async def sales_intel_loop(bot_runtime) -> None:
    rt = _as_bot_runtime(bot_runtime)
    hour, minute = _hhmm("SALES_INTEL_TIME", "10:00")
    await asyncio.sleep(25)
    last_run_date = None
    while True:
        try:
            now = get_local_now()
            today = now.strftime("%Y-%m-%d")
            if (now.weekday() == 0 and now.hour == hour and now.minute == minute
                    and last_run_date != today):
                await run_sales_intel(rt)
                last_run_date = today
        except Exception:
            logger.exception("[SALES-INTEL] loop iteration error")
        await asyncio.sleep(30)
