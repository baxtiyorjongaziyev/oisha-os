"""
Proactive stagnation worker for AmoCRM and Airtable projects.
"""
from __future__ import annotations

import datetime
import html
import json
import logging
import os
from typing import Any, Dict, List, Optional

from src import config
from src.database import Database
from src.services.core.agent_loop import AgentTask
from src.services.core.airtable_sync import AirtableSync
from src.services.core.tool_adapters import (
    build_default_tool_registry,
    send_group_message_with_fallback,
)
from src.services.proactive.airtable_deadlines import (
    _DEADLINE_CLAIM_DIR,
    _claim_on_disk,
    _deadline_sent_keys,
    _prune_stale_claims,
    _release_on_disk,
    _resolve,
    check_airtable_deadlines,
)
from src.services.proactive.formatters import (
    _format_idle_text,
    _lead_idle_hours,
    _mention,
    _project_age_days,
    _project_stage_recommendation,
    _run_notification_agent,
    _safe_text,
    _sales_action_for_lead,
    _sales_manager_playbook,
)
from src.services.proactive.reminders import _execute_telegram_notification
from src.time_utils import get_local_now

logger = logging.getLogger(__name__)


async def _handle_amocrm_auth_error(
    db: Any, registry: Any, group_id: Any, thread_id: Any, job_key: str, today: str, last_error: Any
) -> None:
    message = (
        "⚠️ <b>AmoCRM ulanishi ishlamayapti</b>\n\n"
        f"Sabab: <code>{html.escape(str(last_error))}</code>\n\n"
        "Kerakli ish: AmoCRM OAuth'ni qayta avtorizatsiya qiling."
    )
    task = AgentTask(
        task_id=f"{job_key}:amocrm_auth:{today}", kind="crm_auth_blocked",
        goal="AmoCRM token nosozligini xabar qilish",
        payload={"group_id": group_id, "thread_id": thread_id, "crm_error": last_error},
        planner_notes=["CRM token holati tekshiriladi"], requested_by="scheduler",
    )
    async def auth_executor(t: AgentTask) -> Dict[str, Any]:
        return await _resolve('_execute_telegram_notification', _execute_telegram_notification)(
            registry, group_id=group_id, message=message, thread_id=thread_id, disable_web_page_preview=True,
        )
    result = await _resolve('_run_notification_agent', _run_notification_agent)(db, task, auth_executor)
    if result.success:
        await db.mark_job_run(job_key, today)


async def _process_stagnated_leads(
    amocrm_tool: Any, stagnated: List[Dict[str, Any]], now: datetime
) -> List[Dict[str, Any]]:
    tool_results = []
    now_ts = int(now.timestamp())
    complete_till = int((now + datetime.timedelta(hours=6)).timestamp())
    for lead in sorted(stagnated, key=lambda it: (_lead_idle_hours(it, now_ts), int(it.get("price") or 0)), reverse=True)[:10]:
        lead_id = int(lead.get("id") or 0)
        if not lead_id:
            continue
        responsible_id = int(lead.get("responsible_user_id") or 0) or None
        next_step = _sales_action_for_lead(lead)
        task_text = f"Oisha: qotib qolgan lead. Bugun {next_step}. Natijani CRM izohiga yozing."
        note_text = f"Oisha agent signal: lead 24+ soat qimirlamagan. Tavsiya: {next_step}."
        t_res = await amocrm_tool.create_followup_task(lead_id, task_text[:500], complete_till, responsible_user_id=responsible_id)
        n_res = await amocrm_tool.add_lead_note(lead_id, note_text[:1000])
        tool_results.extend([t_res.to_payload(), n_res.to_payload()])
    return tool_results


async def check_amocrm_stagnation():
    """Qotib qolgan leadlarni topib, menejerlarga conversion push yuborish."""
    import src.config as config
    from src.services.core.crm.amocrm_sync import AmoCRMSync

    db = _resolve('Database', Database)()
    now = _resolve('get_local_now', get_local_now)()
    today = now.strftime("%Y-%m-%d")
    if now.hour not in [12, 16] or now.minute > 10:
        return

    job_key = f"sales_conversion_push_{now.hour}"
    if await db.is_job_run(job_key, today):
        return

    bot_token = os.environ.get("BOT_TOKEN") or getattr(config, "BOT_TOKEN", None)
    group_id = getattr(config, "STAGNATION_GROUP_ID", None) or getattr(config, "CRM_GROUP_ID", None)
    thread_id = getattr(config, "STAGNATION_TOPIC_ID", None) or getattr(config, "TOPIC_CRM_ID", None)
    if not (bot_token and group_id):
        return

    amo = AmoCRMSync(config.AMOCRM_SUBDOMAIN, config.AMOCRM_CLIENT_ID, config.AMOCRM_CLIENT_SECRET, config.AMOCRM_REDIRECT_URL)
    registry = _resolve('build_default_tool_registry', build_default_tool_registry)(bot_token=bot_token, amocrm=amo)
    amocrm_tool = registry.get("amocrm_leads")
    stagnated = await amocrm_tool.fetch_stagnated_leads(hours=24)
    if not stagnated:
        last_error = amocrm_tool.get_last_error() if hasattr(amocrm_tool, "get_last_error") else None
        if last_error:
            await _handle_amocrm_auth_error(db, registry, group_id, thread_id, job_key, today, last_error)
        return

    from src.services.core.enterprise_reporter import EnterpriseReporter
    from src.services.core.crm.crm_service import CRMService
    reporter = EnterpriseReporter(db, CRMService())
    message = await reporter.get_stagnant_leads_alert(limit=50)
    if not message:
        return

    manager_ids = list(getattr(config, "SALES_MANAGER_IDS", []) or [])
    total_value = sum(int(lead.get("price") or 0) for lead in stagnated)
    task = AgentTask(
        task_id=f"{job_key}:{today}", kind="sales_conversion_push",
        goal="CRMdagi qotib qolgan leadlarni conversionga qaytarish",
        payload={"group_id": group_id, "thread_id": thread_id, "lead_count": len(stagnated), "risk_sum": total_value},
        planner_notes=["CRM threadga conversion push yuboriladi"], requested_by="scheduler",
    )
    async def executor(agent_task: AgentTask) -> Dict[str, Any]:
        tool_results = await _process_stagnated_leads(amocrm_tool, stagnated, now)
        execution = await _resolve('_execute_telegram_notification', _execute_telegram_notification)(
            registry, group_id=group_id, message=message, thread_id=thread_id, disable_web_page_preview=True,
        )
        execution["tool_results"] = tool_results
        execution["risk_sum"] = total_value
        return execution

    result = await _resolve('_run_notification_agent', _run_notification_agent)(db, task, executor)
    if result.success:
        await db.mark_job_run(job_key, today)
        logger.info(f"[STAGNATION] Conversion push sent for hour {now.hour}.")


from src.services.proactive.airtable_stagnation import check_airtable_stagnation

__all__ = [
    "check_amocrm_stagnation",
    "check_airtable_stagnation",
    "check_airtable_deadlines",
]
