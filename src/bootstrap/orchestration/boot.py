"""
Main boot_application coordinating all bootstrap steps.
"""
from __future__ import annotations

import asyncio
import logging
import os
import signal as _signal
from typing import Any

from src.api.routes.state import api_state
from src.bootstrap.helpers import _command_processor, _negotiation_int
from src.bootstrap.orchestration.core_services import init_core_services
from src.bootstrap.orchestration.domain_agents import init_domain_agents
from src.bootstrap.orchestration.drain import graceful_drain
from src.bootstrap.orchestration.events import register_event_handlers
from src.bootstrap.orchestration.schedulers import start_background_schedulers
from src.bootstrap.orchestration.telegram_session import (
    init_bot_client_runtime,
    init_telegram_session,
)
from src.context import app_ctx
from src.services.core.agent_runtime import resolve_runtime_mode
from src.services.core.finance.hisobchi_schema import create_hisobchi_engine
from src.services.core.tool_adapters import configure_userbot_group_fallback
from src.settings import settings

logger = logging.getLogger("OishaBootstrap")


async def boot_application():
    import src.main as m
    import src.api_server as api_module

    runtime_mode = resolve_runtime_mode()
    if not runtime_mode.is_cloud and not runtime_mode.allow_local:
        print("\n" + "!" * 60)
        print("[SECURITY LOCK] Oisha-OS Local Execution is DISABLED.")
        print("Set ALLOW_LOCAL_RUN=1 to override on dev machine.")
        print("!" * 60 + "\n")
        return

    app_ctx.task_semaphore = asyncio.Semaphore(50)
    print("Oisha-OS Tizimi tayyorlanmoqda (Dual-Head Architecture)...")

    health_api_task = None
    if not settings.RUN_USERBOT_ONLY:
        health_api_task = asyncio.create_task(m.run_health_check_api(), name="health_check_api")
    m._restore_cloud_artifacts()

    # 1. Core Services & DB
    api_keys, db, hisobchi_gs_store, msg_controller = await init_core_services()
    app_ctx.msg_controller = msg_controller

    cloud_control_plane_only = runtime_mode.control_plane_only

    # 2. Telegram Session & Bot Runtime
    client, telegram_session_manager = await init_telegram_session(cloud_control_plane_only)
    bot_client, BOT_TOKEN_STR, bot_runtime, bot_ingress_mode = init_bot_client_runtime()

    if telegram_session_manager is not None:
        async def _notify_userbot_owner(message: str) -> None:
            try:
                await bot_runtime.send_message(settings.OWNER_ID, message)
            except Exception as notify_exc:
                logger.warning("[SESSION] Owner reconnect alert failed: %s", notify_exc)

        telegram_session_manager.admin_notifier = _notify_userbot_owner

    # 3. Domain Agents & Services
    agents = init_domain_agents(api_keys, msg_controller, client, bot_client, bot_runtime, m)
    admin_bot = agents["admin_bot"]
    access_manager = agents["access_manager"]
    meeting_scheduler = agents["meeting_scheduler"]

    # 4. Background Schedulers
    start_background_schedulers(bot_runtime)

    # 5. API Server Wiring
    api_module.user_client = client
    api_module.db_instance = msg_controller.db
    api_module.msg_controller = msg_controller
    api_module.action_parser = agents["action_parser"]
    api_state.user_client = client
    api_state.db_instance = msg_controller.db
    api_state.msg_controller = msg_controller
    api_state.action_parser = agents["action_parser"]
    api_module.set_runtime_context(
        service_name=os.getenv("K_SERVICE") or "oisha-main",
        canonical_entrypoint="src/main.py",
        state_backend=db.get_backend_name(),
        state_db_path=msg_controller.db.db_path,
        scheduler_mode="persistent", quiet_hours_enabled=True, userbot_authorized=None,
    )

    async def _heartbeat_task():
        while True:
            try:
                api_module.mark_heartbeat()
            except Exception as e:
                logger.debug(f"[HEARTBEAT] tick error: {e}")
            await asyncio.sleep(15)

    api_module.mark_heartbeat()
    asyncio.create_task(_heartbeat_task(), name="api_heartbeat")

    if cloud_control_plane_only:
        api_module.set_runtime_context(
            state_backend=db.get_backend_name(), state_db_path=msg_controller.db.db_path,
            scheduler_mode="control-plane", userbot_authorized=False,
        )
        api_module.update_api_status("online", "Control plane active; Telegram runtime delegated to VM")
        logger.info("[CLOUD] Control-plane mode active.")
        await asyncio.Event().wait()
        return

    # 6. Userbot Ready Check
    userbot_ready = client is not None and (telegram_session_manager is not None and await telegram_session_manager.health_check())
    api_module.set_runtime_context(
        state_backend=db.get_backend_name(), state_db_path=msg_controller.db.db_path,
        userbot_authorized=userbot_ready,
    )
    if not userbot_ready:
        api_module.user_client = None
        api_state.user_client = None
        logger.warning("[SESSION] Userbot tayyor emas — bot-token mode da ishlaydi")
        if BOT_TOKEN_STR and bot_runtime.backend == "telethon" and bot_ingress_mode == "polling":
            try:
                await bot_client.start(bot_token=BOT_TOKEN_STR)
            except Exception as bot_exc:
                logger.error(f"[AUTH] Bot-token head startup failed: {bot_exc}")
        if admin_bot and bot_client and bot_ingress_mode == "polling":
            try:
                admin_bot.user_client = None
                await admin_bot.start()
            except Exception as admin_exc:
                logger.error(f"[BOT_ONLY] Admin bot startup failed: {admin_exc}", exc_info=True)
        api_module.update_api_status("degraded", "Bot-token mode active; userbot needs re-login")
        asyncio.create_task(m.background_monitor_task(), name="background_monitor_task")
        await asyncio.Event().wait()
        return

    configure_userbot_group_fallback(client)
    asyncio.create_task(m.background_monitor_task(), name="background_monitor_task")

    # 7. Hisobchi Engine & Events
    hisobchi_engine = create_hisobchi_engine(
        db=msg_controller.db,
        gs_store=hisobchi_gs_store,
        tracking_start_date=settings.HISOBCHI_TRACKING_START_DATE,
    )
    m._hisobchi_engine = hisobchi_engine
    app_ctx.hisobchi_engine = hisobchi_engine

    hisobchi_analyst = None
    gemini_key_ = api_keys.get("gemini")
    if gemini_key_:
        try:
            from src.services.core.hisobchi_analyst import HisobchiAnalyst
            from src.services.utils.voice_processor import VoiceProcessor
            v_proc = VoiceProcessor(api_key=gemini_key_)
            hisobchi_analyst = HisobchiAnalyst(gemini_client=v_proc.client, engine=hisobchi_engine)
            app_ctx.hisobchi_analyst = hisobchi_analyst
        except Exception as exc:
            logger.warning("[HISOBCHI] HisobchiAnalyst init failed: %s", exc)

    me = await client.get_me() if client else None
    register_event_handlers(client, bot_client, bot_runtime, hisobchi_engine, hisobchi_analyst, m, me)

    # 8. Moliya & Probe Loops
    from src.schedulers.moliya_hisobotlari import moliya_hisobotlari_loop
    asyncio.create_task(moliya_hisobotlari_loop(), name="oisha_moliya_hisobotlari")

    # 9. Graceful Shutdown Watcher
    _shutdown_event = asyncio.Event()

    def _on_sigterm():
        logger.warning("[SHUTDOWN] SIGTERM received — beginning graceful drain.")
        _shutdown_event.set()

    loop = asyncio.get_running_loop()
    try:
        loop.add_signal_handler(_signal.SIGTERM, _on_sigterm)
        loop.add_signal_handler(_signal.SIGINT, _on_sigterm)
    except NotImplementedError:
        pass

    api_module.update_api_status("online", "Userbot, Telegram bot, and persistent scheduler are active")
    logger.info("Oisha-OS userbot runtime is online and ready.")

    disc_task = asyncio.create_task(client.run_until_disconnected(), name="userbot_disconnect_watcher")
    shutdown_task = asyncio.create_task(_shutdown_event.wait(), name="shutdown_watcher")
    done, pending = await asyncio.wait({disc_task, shutdown_task}, return_when=asyncio.FIRST_COMPLETED)
    if shutdown_task in done:
        await graceful_drain(client, bot_client, msg_controller, health_api_task, m)
        for t in pending:
            t.cancel()
    else:
        logger.warning("[SHUTDOWN] Telegram client disconnected unexpectedly.")
        shutdown_task.cancel()
