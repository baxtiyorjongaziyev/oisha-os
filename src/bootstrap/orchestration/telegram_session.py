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


async def init_telegram_session(cloud_control_plane_only: bool) -> Tuple[Optional[Any], Optional[Any]]:
    telegram_session_manager = None
    if cloud_control_plane_only:
        app_ctx.client = TelegramClient(
            StringSession(), settings.API_ID, settings.API_HASH,
            device_model="Oisha Enterprise Control Plane", system_version="Cloud Run",
        )
    else:
        if platform.system() == "Windows":
            logger.warning("[SESSION] ❌ Windows OS detected! Userbot is FORCED OFF locally to protect the remote session.")
            app_ctx.client = None
        else:
            from src.services.core.telegram_session_manager import TelegramSessionManager
            from src.services.core.session_keeper import (
                get_best_session_string,
                session_keepalive_loop,
            )

            telegram_session_manager = TelegramSessionManager(
                api_id=settings.API_ID,
                api_hash=settings.API_HASH,
                session_file="data/userbot.session",
                session_string=get_best_session_string(),
                admin_notifier=None,
                device_model="Oisha Enterprise v2",
                system_version="Linux Server",
            )
            userbot_ready = await telegram_session_manager.connect()
            if not userbot_ready:
                logger.error("[SESSION] ❌ Userbot session ulanmadi!")
                app_ctx.client = None
            else:
                app_ctx.client = telegram_session_manager.client
                me = await app_ctx.client.get_me()
                logger.info(f"[TELEGRAM] Userbot client initialized and authorized successfully! ✅ (Username: @{me.username or 'None'})")
                await telegram_session_manager.start_reconnect_monitor()
                _keepalive_stop = telegram_session_manager._stop_event
                asyncio.create_task(
                    session_keepalive_loop(
                        app_ctx.client,
                        interval_secs=int(os.getenv("USERBOT_KEEPALIVE_INTERVAL_SECS", "300")),
                        notify_callback=None,
                        stop_event=_keepalive_stop,
                    ),
                    name="userbot_session_keepalive",
                )
                logger.info("[SESSION] Keep-alive loop ishga tushdi")

    return app_ctx.client, telegram_session_manager


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
