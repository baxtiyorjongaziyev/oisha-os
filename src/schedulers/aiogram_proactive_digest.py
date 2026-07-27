"""Proactive digest schedulers for Aiogram bot head.

Each digest runs on its own schedule and pushes snapshots to the team group
without requiring any manual command.  All loops are fire-and-forget
asyncio tasks created from boot.py.

Schedule defaults (all overridable via settings / env):

  - Command Center digest  : 09:05  (once daily)
  - Sales Today digest     : 09:10  (once daily)
  - Project Risks digest   : 09:15  (once daily)
  - Finance Risks digest   : 09:20  (once daily)
  - Team Capacity digest   : 09:25  (once daily)
  - VPS Status digest      : 09:00  (once daily) + every 6 h if critical
"""

from __future__ import annotations

import asyncio
import logging
import platform
from datetime import datetime
from typing import Any, Awaitable, Callable, Optional

logger = logging.getLogger(__name__)

SnapshotProvider = Callable[[], Awaitable[dict[str, Any]]]


# ─── helpers ──────────────────────────────────────────────────────────────────

def _as_bot_runtime(bot_client: Any) -> Any:
    """Normalise to BotRuntimePort (or anything with .send_message)."""
    if bot_client is None:
        return None
    if hasattr(bot_client, "send_message"):
        return bot_client
    return None


async def _safe_send(
    bot_client: Any,
    chat_id: int | str | None,
    text: str,
    *,
    topic_id: Optional[int] = None,
    parse_mode: str = "markdown",
) -> bool:
    rt = _as_bot_runtime(bot_client)
    if rt is None or not chat_id:
        return False
    try:
        await rt.send_message(
            chat_id,
            text,
            parse_mode=parse_mode,
            message_thread_id=topic_id,
            disable_web_page_preview=True,
        )
        return True
    except Exception:
        logger.error("[PROACTIVE_DIGEST] send failed", exc_info=True)
        return False


def _once_daily_guard(last_run: dict, key: str, now_str: str) -> bool:
    """Return True if we should run today, and record the run."""
    if last_run.get(key) == now_str:
        return False
    last_run[key] = now_str
    return True


# ─── VPS status ───────────────────────────────────────────────────────────────

def _build_vps_text() -> str:
    import psutil
    cpu = psutil.cpu_percent()
    ram = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    return (
        "🖥 **VPS SERVER HOLATI**\n"
        "──────────────────────\n"
        f"🌐 **OS:** `{platform.system()} {platform.release()}`\n"
        f"⚙️ **CPU:** `{cpu}%`\n"
        f"🧠 **RAM:** `{ram.percent}%` ({ram.used // (1024**2)}MB / {ram.total // (1024**2)}MB)\n"
        f"💽 **Disk:** `{disk.percent}%` o'rin band\n"
        f"🛰 **Vaqt:** `{datetime.now().strftime('%H:%M:%S')}`\n"
        "──────────────────────\n"
        "🟢 *Oisha-OS monitoring aktiv.*"
    )


async def vps_status_digest_loop(
    *,
    bot_client: Any,
    target_chat_id: int | str | None,
    hour: int = 9,
    minute: int = 0,
    topic_id: Optional[int] = None,
    critical_cpu_threshold: float = 85.0,
    check_interval_seconds: int = 300,  # 5 min
) -> None:
    """Daily VPS status digest + alert on critical CPU."""
    from src.time_utils import get_local_now

    await asyncio.sleep(15)
    logger.info("[VPS_DIGEST] Loop started.")
    last_run: dict = {}

    while True:
        try:
            now = get_local_now()
            today = now.strftime("%Y-%m-%d")

            # Once daily at scheduled time
            if now.hour == hour and now.minute == minute:
                if _once_daily_guard(last_run, "daily", today):
                    text = _build_vps_text()
                    await _safe_send(bot_client, target_chat_id, text, topic_id=topic_id)
                    logger.info("[VPS_DIGEST] Daily digest sent.")

            # Critical CPU alert (independent of daily gate)
            try:
                import psutil
                if psutil.cpu_percent() >= critical_cpu_threshold:
                    alert_key = f"cpu_alert_{now.strftime('%Y-%m-%d-%H')}"
                    if _once_daily_guard(last_run, alert_key, alert_key):
                        text = (
                            f"⚠️ **VPS CPU YUKLANISHI KRITIK**: `{psutil.cpu_percent()}%`\n"
                            f"RAM: `{psutil.virtual_memory().percent}%`\n"
                            f"Vaqt: `{now.strftime('%H:%M')}`"
                        )
                        await _safe_send(bot_client, target_chat_id, text, topic_id=topic_id)
                        logger.warning("[VPS_DIGEST] Critical CPU alert sent.")
            except Exception:
                pass

        except Exception:
            logger.error("[VPS_DIGEST] Loop error.", exc_info=True)
        await asyncio.sleep(check_interval_seconds)


# ─── Sales today digest ───────────────────────────────────────────────────────

async def sales_today_digest_loop(
    *,
    bot_client: Any,
    target_chat_id: int | str | None,
    snapshot_provider: SnapshotProvider,
    hour: int = 9,
    minute: int = 10,
    topic_id: Optional[int] = None,
) -> None:
    """Daily sales priorities digest."""
    from src.time_utils import get_local_now
    from src.services.core.admin_command_router import build_sales_priorities_response

    await asyncio.sleep(20)
    logger.info("[SALES_DIGEST] Loop started.")
    last_run: dict = {}

    while True:
        try:
            now = get_local_now()
            today = now.strftime("%Y-%m-%d")
            if now.hour == hour and now.minute == minute:
                if _once_daily_guard(last_run, "daily", today):
                    payload = await snapshot_provider()
                    response = build_sales_priorities_response(payload, max_items=7)
                    await _safe_send(
                        bot_client, target_chat_id, response.text,
                        topic_id=topic_id, parse_mode=response.parse_mode or "html",
                    )
                    logger.info("[SALES_DIGEST] Sent.")
        except Exception:
            logger.error("[SALES_DIGEST] Loop error.", exc_info=True)
        await asyncio.sleep(30)


# ─── Project risks digest ─────────────────────────────────────────────────────

async def project_risks_digest_loop(
    *,
    bot_client: Any,
    target_chat_id: int | str | None,
    snapshot_provider: SnapshotProvider,
    hour: int = 9,
    minute: int = 15,
    topic_id: Optional[int] = None,
) -> None:
    """Daily project delivery risks digest."""
    from src.time_utils import get_local_now
    from src.services.core.admin_command_router import build_project_risks_response

    await asyncio.sleep(25)
    logger.info("[PROJECT_RISKS_DIGEST] Loop started.")
    last_run: dict = {}

    while True:
        try:
            now = get_local_now()
            today = now.strftime("%Y-%m-%d")
            if now.hour == hour and now.minute == minute:
                if _once_daily_guard(last_run, "daily", today):
                    payload = await snapshot_provider()
                    response = build_project_risks_response(payload, max_items=7)
                    await _safe_send(
                        bot_client, target_chat_id, response.text,
                        topic_id=topic_id, parse_mode=response.parse_mode or "html",
                    )
                    logger.info("[PROJECT_RISKS_DIGEST] Sent.")
        except Exception:
            logger.error("[PROJECT_RISKS_DIGEST] Loop error.", exc_info=True)
        await asyncio.sleep(30)


# ─── Finance risks digest ─────────────────────────────────────────────────────

async def finance_risks_digest_loop(
    *,
    bot_client: Any,
    target_chat_id: int | str | None,
    snapshot_provider: SnapshotProvider,
    hour: int = 9,
    minute: int = 20,
    topic_id: Optional[int] = None,
) -> None:
    """Daily finance risks digest."""
    from src.time_utils import get_local_now
    from src.services.core.admin_command_router import build_finance_risks_response

    await asyncio.sleep(30)
    logger.info("[FINANCE_RISKS_DIGEST] Loop started.")
    last_run: dict = {}

    while True:
        try:
            now = get_local_now()
            today = now.strftime("%Y-%m-%d")
            if now.hour == hour and now.minute == minute:
                if _once_daily_guard(last_run, "daily", today):
                    payload = await snapshot_provider()
                    response = build_finance_risks_response(payload, max_items=7)
                    await _safe_send(
                        bot_client, target_chat_id, response.text,
                        topic_id=topic_id, parse_mode=response.parse_mode or "html",
                    )
                    logger.info("[FINANCE_RISKS_DIGEST] Sent.")
        except Exception:
            logger.error("[FINANCE_RISKS_DIGEST] Loop error.", exc_info=True)
        await asyncio.sleep(30)


# ─── Team capacity digest ─────────────────────────────────────────────────────

async def team_capacity_digest_loop(
    *,
    bot_client: Any,
    target_chat_id: int | str | None,
    snapshot_provider: SnapshotProvider,
    hour: int = 9,
    minute: int = 25,
    topic_id: Optional[int] = None,
) -> None:
    """Daily team capacity digest."""
    from src.time_utils import get_local_now
    from src.services.core.admin_command_router import build_team_capacity_response

    await asyncio.sleep(35)
    logger.info("[TEAM_CAPACITY_DIGEST] Loop started.")
    last_run: dict = {}

    while True:
        try:
            now = get_local_now()
            today = now.strftime("%Y-%m-%d")
            if now.hour == hour and now.minute == minute:
                if _once_daily_guard(last_run, "daily", today):
                    payload = await snapshot_provider()
                    response = build_team_capacity_response(payload, max_items=7)
                    await _safe_send(
                        bot_client, target_chat_id, response.text,
                        topic_id=topic_id, parse_mode=response.parse_mode or "html",
                    )
                    logger.info("[TEAM_CAPACITY_DIGEST] Sent.")
        except Exception:
            logger.error("[TEAM_CAPACITY_DIGEST] Loop error.", exc_info=True)
        await asyncio.sleep(30)


# ─── Boot helper ──────────────────────────────────────────────────────────────

def start_proactive_digest_loops(
    *,
    bot_client: Any,
    target_chat_id: int | str | None,
    get_sales_today_priorities: SnapshotProvider,
    get_project_delivery_risks: SnapshotProvider,
    get_finance_project_risks: SnapshotProvider,
    get_team_capacity: SnapshotProvider,
    topic_id: Optional[int] = None,
    # Time overrides (hour, minute per digest)
    vps_hour: int = 9,
    vps_minute: int = 0,
    sales_hour: int = 9,
    sales_minute: int = 10,
    project_hour: int = 9,
    project_minute: int = 15,
    finance_hour: int = 9,
    finance_minute: int = 20,
    team_hour: int = 9,
    team_minute: int = 25,
) -> list[asyncio.Task]:
    """Create and register all proactive digest tasks. Call once from boot.py."""
    tasks = [
        asyncio.create_task(
            vps_status_digest_loop(
                bot_client=bot_client,
                target_chat_id=target_chat_id,
                hour=vps_hour,
                minute=vps_minute,
                topic_id=topic_id,
            ),
            name="vps_status_digest_loop",
        ),
        asyncio.create_task(
            sales_today_digest_loop(
                bot_client=bot_client,
                target_chat_id=target_chat_id,
                snapshot_provider=get_sales_today_priorities,
                hour=sales_hour,
                minute=sales_minute,
                topic_id=topic_id,
            ),
            name="sales_today_digest_loop",
        ),
        asyncio.create_task(
            project_risks_digest_loop(
                bot_client=bot_client,
                target_chat_id=target_chat_id,
                snapshot_provider=get_project_delivery_risks,
                hour=project_hour,
                minute=project_minute,
                topic_id=topic_id,
            ),
            name="project_risks_digest_loop",
        ),
        asyncio.create_task(
            finance_risks_digest_loop(
                bot_client=bot_client,
                target_chat_id=target_chat_id,
                snapshot_provider=get_finance_project_risks,
                hour=finance_hour,
                minute=finance_minute,
                topic_id=topic_id,
            ),
            name="finance_risks_digest_loop",
        ),
        asyncio.create_task(
            team_capacity_digest_loop(
                bot_client=bot_client,
                target_chat_id=target_chat_id,
                snapshot_provider=get_team_capacity,
                hour=team_hour,
                minute=team_minute,
                topic_id=topic_id,
            ),
            name="team_capacity_digest_loop",
        ),
    ]
    logger.info("[PROACTIVE_DIGEST] %d digest loops started.", len(tasks))
    return tasks
