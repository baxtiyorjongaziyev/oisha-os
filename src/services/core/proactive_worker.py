"""
Facade for proactive worker and scheduler jobs.
Delegates to modular implementations in src.services.proactive.
"""

from aiogram import Bot
from src.database import Database
from src.time_utils import get_local_now
from src.services.core.tool_adapters import (
    build_default_tool_registry,
    send_group_message_with_fallback,
)
import src.services.proactive.stagnation as _stagnation_mod
_DEADLINE_CLAIM_DIR = _stagnation_mod._DEADLINE_CLAIM_DIR
_deadline_sent_keys = _stagnation_mod._deadline_sent_keys

from src.services.proactive import (
    DAILY_PLAN_PHASES,
    PM_STAGE_HINTS,
    ProactiveWorker,
    _claim_on_disk,
    _execute_telegram_notification,
    _format_idle_text,
    _lead_idle_hours,
    _mention,
    _project_age_days,
    _project_stage_recommendation,
    _prune_stale_claims,
    _release_on_disk,
    _run_notification_agent,
    _safe_text,
    _sales_action_for_lead,
    _sales_manager_playbook,
    check_airtable_deadlines,
    check_airtable_stagnation,
    check_amocrm_stagnation,
    check_client_journey_excellence,
    demand_daily_plans,
    distribute_team_tasks,
    generate_ai_message,
    run_crm_offload,
    send_daily_report,
    send_evening_fact_report,
    send_junk_leads_report,
    send_lunch_reminder,
    send_morning_briefing,
    send_overdue_nudges,
    send_proactive_followups,
)

# Deprecated / legacy aliases for backward compatibility
_legacy_check_airtable_stagnation = check_airtable_stagnation
_legacy_check_airtable_stagnation_mixed = check_airtable_stagnation
_deprecated_check_airtable_stagnation_direct = check_airtable_stagnation
_legacy_check_amocrm_stagnation_direct = check_amocrm_stagnation
_legacy_check_amocrm_stagnation_mixed = check_amocrm_stagnation

__all__ = [
    "Bot",
    "Database",
    "get_local_now",
    "build_default_tool_registry",
    "send_group_message_with_fallback",
    "_DEADLINE_CLAIM_DIR",
    "_deadline_sent_keys",
    "DAILY_PLAN_PHASES",
    "PM_STAGE_HINTS",
    "generate_ai_message",
    "_safe_text",
    "_mention",
    "_lead_idle_hours",
    "_format_idle_text",
    "_sales_action_for_lead",
    "_sales_manager_playbook",
    "_project_stage_recommendation",
    "_project_age_days",
    "_run_notification_agent",
    "check_amocrm_stagnation",
    "check_airtable_stagnation",
    "check_airtable_deadlines",
    "_prune_stale_claims",
    "_claim_on_disk",
    "_release_on_disk",
    "demand_daily_plans",
    "send_proactive_followups",
    "distribute_team_tasks",
    "send_daily_report",
    "send_morning_briefing",
    "send_overdue_nudges",
    "send_lunch_reminder",
    "send_evening_fact_report",
    "send_junk_leads_report",
    "_execute_telegram_notification",
    "check_client_journey_excellence",
    "run_crm_offload",
    "ProactiveWorker",
    "_legacy_check_airtable_stagnation",
    "_legacy_check_airtable_stagnation_mixed",
    "_deprecated_check_airtable_stagnation_direct",
    "_legacy_check_amocrm_stagnation_direct",
    "_legacy_check_amocrm_stagnation_mixed",
]
