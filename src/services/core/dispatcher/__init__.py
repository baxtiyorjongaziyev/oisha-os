from src.services.core.dispatcher.adapter import AiogramCallbackEventAdapter
from src.services.core.dispatcher.callbacks import (
    register_hisobchi_aiogram_callbacks,
    register_salescoach_aiogram_callbacks,
)
from src.services.core.dispatcher.handlers_admin import (
    handle_aiogram_auto_status,
    handle_aiogram_chatid,
    handle_aiogram_command_center,
    handle_aiogram_finance_risks,
    handle_aiogram_oisha_stats,
    handle_aiogram_pause_auto,
    handle_aiogram_project_risks,
    handle_aiogram_resume_auto,
    handle_aiogram_sales_today,
    handle_aiogram_set_mode,
    handle_aiogram_team_capacity,
    handle_aiogram_vps_status,
)
from src.services.core.dispatcher.handlers_crm_coach import (
    handle_aiogram_crm_history,
    handle_aiogram_crm_report,
    handle_aiogram_crm_stats,
    handle_aiogram_fear_message,
    handle_aiogram_psychological_coach,
    handle_aiogram_sparring,
)
from src.services.core.dispatcher.builder import (
    build_admin_aiogram_dispatcher,
    maybe_build_admin_aiogram_dispatcher,
)

__all__ = [
    "AiogramCallbackEventAdapter",
    "register_hisobchi_aiogram_callbacks",
    "register_salescoach_aiogram_callbacks",
    "handle_aiogram_chatid",
    "handle_aiogram_oisha_stats",
    "handle_aiogram_sales_today",
    "handle_aiogram_project_risks",
    "handle_aiogram_finance_risks",
    "handle_aiogram_team_capacity",
    "handle_aiogram_command_center",
    "handle_aiogram_vps_status",
    "handle_aiogram_auto_status",
    "handle_aiogram_pause_auto",
    "handle_aiogram_resume_auto",
    "handle_aiogram_set_mode",
    "handle_aiogram_crm_report",
    "handle_aiogram_crm_stats",
    "handle_aiogram_crm_history",
    "handle_aiogram_psychological_coach",
    "handle_aiogram_sparring",
    "handle_aiogram_fear_message",
    "build_admin_aiogram_dispatcher",
    "maybe_build_admin_aiogram_dispatcher",
]
