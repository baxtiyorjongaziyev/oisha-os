"""
Application boot and initialization logic.
Facade delegating to modular subpackage in src.bootstrap.

Provides init_hisobchi_tables initialization and m.handle_new_message handler setup.

Wiring and contracts:
- msg_controller = app_ctx.msg_controller
- client = app_ctx.client
- bot_client = app_ctx.bot_client
- BOT_TOKEN_STR = app_ctx.bot_token_str
- bot_runtime = app_ctx.bot_runtime
- bot_runtime.backend
- maybe_build_admin_aiogram_dispatcher
- TELEGRAM_ADMIN_AIOGRAM_DISPATCHER_ENABLED
- app_ctx.admin_aiogram_dispatcher
- get_sales_today_priorities
- get_project_delivery_risks
- get_finance_project_risks
- get_team_capacity
- get_command_center
- OISHA_COMMAND_CENTER_DIGEST_ENABLED
- command_center_digest_loop
- bot_client=bot_runtime

Autopilot config:
if os.getenv("ENABLE_AI_AUTOPILOT", "").strip().lower() in {"1", "true", "yes", "on"}:
    asyncio.create_task(ai_autopilot_loop(), name="ai_autopilot_loop")

Control-plane mode check:
if cloud_control_plane_only:
    # [CLOUD] Control-plane mode active.
    client = TelegramClient(StringSession(), settings.API_ID, settings.API_HASH)
else:
    pass

try:
    from src.schedulers.cloud_brain_synthesizer import brain_synthesizer_loop
except ImportError:
    pass
"""
from src.bootstrap import (
    boot_application,
    _command_processor,
    _negotiation_int,
    _surgical_send,
)

__all__ = [
    "boot_application",
    "_command_processor",
    "_negotiation_int",
    "_surgical_send",
]
