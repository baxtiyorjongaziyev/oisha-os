"""
Oisha-OS Main Entry Point.
Modular entrypoint facade delegating to src.entrypoint.
"""
import asyncio
import logging
import os
import sys
from dotenv import load_dotenv

load_dotenv()

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

# Global variables mirrored to app_ctx for legacy backward compatibility
from src.context import app_ctx
from src.settings import settings

client = None
bot_client = None
msg_controller = None
safe_responder = None
action_parser = None
lead_scraper = None
advisor_agent = None
auto_lead_agent = None
activity_monitor = None
audit_agent = None
sales_coach = None
crm_guard = None
admin_bot = None
amocrm_alert_forwarder = None
access_manager = None
telegram_meeting_scheduler = None
hisobchi_analyst = None
hisobchi_gsheets = None
smart_task_creator = None
lead_pipeline_sync = None
salescoach_bridge = None
docusign_bridge = None
apollo_bridge = None

from src.entrypoint import (
    _brain_evolution_loop,
    _connect_user_client,
    _dialog_filter_title,
    _env_enabled,
    _excluded_folder_keywords,
    _excluded_folder_user_ids,
    _folder_exclusion_enabled,
    _is_personal_folder_sender,
    _is_private_userbot_event,
    _is_shutdown_daemon_task,
    _negotiation_int,
    _peer_user_id,
    _restore_cloud_artifacts,
    _should_block_private_userbot_reply,
    _shutdown_task_label,
    _userbot_private_replies_disabled,
    background_monitor_task,
    global_phone_lookup,
    handle_new_message,
    main,
    notify_admin,
    push_block_to_amocrm,
    run_autonomous_advice,
    run_health_check_api,
    self_command_handler,
    spawn_task,
    stop_health_check_api,
    sync_single_lead,
)

__all__ = [
    "client",
    "bot_client",
    "msg_controller",
    "safe_responder",
    "action_parser",
    "lead_scraper",
    "advisor_agent",
    "auto_lead_agent",
    "activity_monitor",
    "audit_agent",
    "sales_coach",
    "crm_guard",
    "admin_bot",
    "amocrm_alert_forwarder",
    "access_manager",
    "telegram_meeting_scheduler",
    "hisobchi_analyst",
    "hisobchi_gsheets",
    "smart_task_creator",
    "lead_pipeline_sync",
    "salescoach_bridge",
    "docusign_bridge",
    "apollo_bridge",
    "_is_shutdown_daemon_task",
    "_shutdown_task_label",
    "_env_enabled",
    "spawn_task",
    "_restore_cloud_artifacts",
    "background_monitor_task",
    "run_health_check_api",
    "stop_health_check_api",
    "_brain_evolution_loop",
    "_userbot_private_replies_disabled",
    "_is_private_userbot_event",
    "_should_block_private_userbot_reply",
    "_folder_exclusion_enabled",
    "_excluded_folder_keywords",
    "_dialog_filter_title",
    "_peer_user_id",
    "_excluded_folder_user_ids",
    "_is_personal_folder_sender",
    "push_block_to_amocrm",
    "global_phone_lookup",
    "notify_admin",
    "sync_single_lead",
    "run_autonomous_advice",
    "handle_new_message",
    "self_command_handler",
    "_negotiation_int",
    "_connect_user_client",
    "main",
]

if __name__ == "__main__":
    asyncio.run(main())
