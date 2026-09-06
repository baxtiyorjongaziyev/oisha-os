"""
Telegram userbot session and bot runtime initialization.
"""
from __future__ import annotations

import asyncio
import logging
import os
import platform
from typing import Any, Optional, Tuple

from telethon import TelegramClient
from telethon.sessions import StringSession

from src.context import app_ctx
from src.settings import settings

logger = logging.getLogger("OishaBootstrap")


def _make_owner_notifier():
    """Auth-xatolik ogohlantirishlarini ishga tushirilgan bot runtime orqali
    Owner'ga yuboradigan async callback qaytaradi.

    ``app_ctx.bot_runtime`` hali tayyor bo'lmasa (init tartibi) yoki
    ``OWNER_ID`` sozlanmagan bo'lsa — log bilan cheklanadi. Callback har doim
    awaitable coroutine qaytaradi, shunda chaqiruvchilar xavfsiz ``await``
    qila oladi.
    """
    async def _notify(msg: str) -> None:
        owner_id = getattr(settings, "OWNER_ID", None)
        runtime = getattr(app_ctx, "bot_runtime", None)
        if runtime is not None and owner_id:
            try:
                await runtime.send_message(int(owner_id), f"🚨 [SESSION] {msg}")
                return
            except Exception:
                logger.warning("[SESSION] Owner alert yuborilmadi", exc_info=True)
        logger.warning("[SESSION][ADMIN-ALERT] %s", msg)

    return _notify


async def _acquire_userbot_ownership() -> bool:
    """Atomik yagona-egalik lock. True -> davom etamiz, False -> userbot ochilmaydi."""
    from src.services.core.telegram.session_store import acquire_session_ownership

    force = os.getenv("USERBOT_OWNER_FORCE", "").strip() in {"1", "true", "yes"}
    if acquire_session_ownership(force=force):
        return True
    logger.critical(
        "[SESSION] ❌ Boshqa instance userbot egasi — bu yerda userbot OCHILMAYDI. "
        "Egalik bo'shasa heartbeat/reconnect keyingi restartsiz tiklaydi. "
        "Majburan olish: USERBOT_OWNER_FORCE=1."
    )
    return False


async def _start_userbot_background_tasks(manager: Any, notifier) -> None:
    """Reconnect monitor + keepalive + egalik heartbeat + egalikni tiklash loop."""
    from src.services.core.session_keeper import session_keepalive_loop
    from src.services.core.telegram.session_store import (
        start_owner_heartbeat,
        start_owner_reacquire_watch,
    )

    await manager.start_reconnect_monitor()
    stop_event = manager._stop_event
    asyncio.create_task(
        session_keepalive_loop(
            app_ctx.client,
            interval_secs=int(os.getenv("USERBOT_KEEPALIVE_INTERVAL_SECS", "300")),
            notify_callback=notifier,
            stop_event=stop_event,
        ),
        name="userbot_session_keepalive",
    )
    start_owner_heartbeat(stop_event)
    start_owner_reacquire_watch(stop_event)
    logger.info("[SESSION] Keep-alive + egalik heartbeat + reacquire watch ishga tushdi")


async def _init_userbot_with_manager() -> Optional[Any]:
    """Userbot sessiyasini egalik lock + manager orqali ishga tushiradi."""
    from src.services.core.telegram_session_manager import TelegramSessionManager
    from src.services.core.session_keeper import get_best_session_string

    if not await _acquire_userbot_ownership():
        app_ctx.client = None
        return None

    notifier = _make_owner_notifier()
    manager = TelegramSessionManager(
        api_id=settings.API_ID,
        api_hash=settings.API_HASH,
        session_file="data/userbot.session",
        session_string=get_best_session_string(),
        admin_notifier=notifier,
        device_model="Oisha Enterprise v2",
        system_version="Linux Server",
    )
    if not await manager.connect():
        logger.error("[SESSION] ❌ Userbot session ulanmadi!")
        app_ctx.client = None
        return manager

    app_ctx.client = manager.client
    me = await app_ctx.client.get_me()
    logger.info(
        "[TELEGRAM] Userbot client initialized and authorized successfully! ✅ (Username: @%s)",
        me.username or "None",
    )
    await _start_userbot_background_tasks(manager, notifier)
    return manager


async def init_telegram_session(cloud_control_plane_only: bool) -> Tuple[Optional[Any], Optional[Any]]:
    if cloud_control_plane_only:
        app_ctx.client = TelegramClient(
            StringSession(), settings.API_ID, settings.API_HASH,
            device_model="Oisha Enterprise Control Plane", system_version="Cloud Run",
        )
        return app_ctx.client, None

    if platform.system() == "Windows":
        logger.warning(
            "[SESSION] ❌ Windows OS detected! Userbot is FORCED OFF locally to protect the remote session."
        )
        app_ctx.client = None
        return app_ctx.client, None

    manager = await _init_userbot_with_manager()
    return app_ctx.client, manager


def init_bot_client_runtime() -> Tuple[Any, str, Any, str]:
    BOT_TOKEN = settings.BOT_TOKEN.get_secret_value()
    _bot_session_string = os.environ.get("BOT_SESSION_STRING", "").strip()
    _bot_session = StringSession(_bot_session_string) if _bot_session_string else StringSession()
    app_ctx.bot_client = TelegramClient(_bot_session, settings.API_ID, settings.API_HASH)
    app_ctx.bot_token_str = BOT_TOKEN
    from src.services.core.telegram.bot_runtime import build_outbound_bot_runtime
    app_ctx.bot_runtime = build_outbound_bot_runtime(
        backend=getattr(settings, "TELEGRAM_BOT_RUNTIME_BACKEND", "telethon"),
        bot_token=app_ctx.bot_token_str,
        telethon_client=app_ctx.bot_client,
    )
    bot_ingress_mode = str(
        getattr(settings, "TELEGRAM_BOT_INGRESS_MODE", "polling") or "polling"
    ).strip().lower()
    if bot_ingress_mode not in {"polling", "webhook", "disabled"}:
        raise RuntimeError("TELEGRAM_BOT_INGRESS_MODE must be polling, webhook, or disabled")
    app_ctx.aiogram_bot_head = None
    return app_ctx.bot_client, app_ctx.bot_token_str, app_ctx.bot_runtime, bot_ingress_mode
