import os
import logging
from typing import Any, Dict
from src.time_utils import get_local_now
from src.database import Database
from src.services.core.tool_adapters import build_default_tool_registry
from src.services.core.agent_loop import AgentTask
from src.services.core.client_journey_playbook import (
    assess_project_portfolio,
    assess_sales_pipeline,
    build_department_direct_messages,
    render_excellence_report,
)
from src.services.proactive.formatters import _run_notification_agent
from src.services.proactive.reminders import _execute_telegram_notification
from src.services.core.airtable_sync import AirtableSync
from src.services.core.crm.amocrm_sync import AmoCRMSync
from src.services.core.gdrive import GoogleDriveSync
from src.services.core.crm.crm_file_offloader import CRMFileOffloader
from src.settings import settings
import src.config as config

logger = logging.getLogger(__name__)


async def check_client_journey_excellence() -> bool:
    """Mijoz yo'li bo'yicha wow-service signal va mikromanagement push yuborish."""
    db = Database()
    now = get_local_now()
    today = now.strftime("%Y-%m-%d")
    target_hours = [11, 17]

    if now.hour not in target_hours or now.minute > 10:
        return False

    job_key = f"client_journey_excellence_{now.hour}"
    if await db.is_job_run(job_key, today):
        return False

    bot_token = os.environ.get("BOT_TOKEN") or getattr(config, "BOT_TOKEN", None)
    group_id = (
        getattr(config, "PROJECTS_GROUP_ID", None)
        or getattr(config, "WOW_SERVICE_GROUP_ID", None)
        or -1003114662117
    )
    thread_id = (
        getattr(config, "PROJECTS_TOPIC_ID", None)
        or getattr(config, "WOW_SERVICE_TOPIC_ID", None)
        or 1
    )
    if not (bot_token and group_id):
        return False

    amo = AmoCRMSync(
        config.AMOCRM_SUBDOMAIN,
        config.AMOCRM_CLIENT_ID,
        config.AMOCRM_CLIENT_SECRET,
        config.AMOCRM_REDIRECT_URL,
    )
    airtable = AirtableSync()
    registry = build_default_tool_registry(
        bot_token=bot_token, amocrm=amo, airtable=airtable
    )
    amocrm_tool = registry.get("amocrm_leads")
    airtable_tool = registry.get("airtable_projects")

    leads = await amocrm_tool.fetch_leads(limit=100)
    projects = await airtable_tool.fetch_projects()
    owner_lookup: Dict[int, str] = {}
    responsible_ids = sorted(
        {
            int(lead.get("responsible_user_id") or 0)
            for lead in leads
            if int(lead.get("responsible_user_id") or 0) > 0
        }
    )
    for responsible_id in responsible_ids:
        owner_lookup[responsible_id] = await amocrm_tool.get_user_name(responsible_id)

    sales_signals = assess_sales_pipeline(
        leads,
        owner_lookup=lambda user_id: owner_lookup.get(user_id, "Sales"),
    )
    project_signals = assess_project_portfolio(projects)
    if not sales_signals and not project_signals:
        return False

    team_members = await db.get_team_roles()
    message = render_excellence_report(sales_signals, project_signals)
    direct_messages = build_department_direct_messages(
        team_members, sales_signals, project_signals
    )

    task = AgentTask(
        task_id=f"{job_key}:{today}",
        kind="client_journey_excellence",
        goal="Lead first-touchdan tortib referralgacha wow-service mikromanagementini ushlash",
        payload={
            "group_id": group_id,
            "thread_id": thread_id,
            "sales_signal_count": len(sales_signals),
            "project_signal_count": len(project_signals),
            "direct_message_count": len(direct_messages),
        },
        planner_notes=[
            "AmoCRM lidlari va Airtable loyihalari wow-service risklari bo'yicha baholanadi",
            "Loyihalar guruhiga umumiy excellence report yuboriladi",
            "Sales va PM rollarga mos ravishda alohida DM mikromanagement push beriladi",
        ],
        requested_by="scheduler",
    )

    async def executor(agent_task: AgentTask) -> Dict[str, Any]:
        execution = await _execute_telegram_notification(
            registry,
            group_id=group_id,
            message=message,
            thread_id=thread_id,
            direct_messages=direct_messages,
            disable_web_page_preview=True,
        )
        execution.update(
            {
                "sales_signal_count": agent_task.payload.get("sales_signal_count"),
                "project_signal_count": agent_task.payload.get("project_signal_count"),
            }
        )
        return execution

    result = await _run_notification_agent(db, task, executor)
    if result.success:
        await db.mark_job_run(job_key, today)
        return True
    return False


async def run_crm_offload():
    """CLI orqali AmoCRM fayllarini offload qilish."""
    bot_token = os.environ.get("BOT_TOKEN") or getattr(config, "BOT_TOKEN", None)
    if not bot_token:
        logger.error("BOT_TOKEN not found.")
        return

    amo = AmoCRMSync(
        config.AMOCRM_SUBDOMAIN,
        config.AMOCRM_CLIENT_ID,
        config.AMOCRM_CLIENT_SECRET,
        config.AMOCRM_REDIRECT_URL,
    )
    gdrive = GoogleDriveSync(settings.GSHEET_CREDS_FILE)
    offloader = CRMFileOffloader(amo, gdrive)
    await offloader.run(dry_run=False)
