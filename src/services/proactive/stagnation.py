"""
Proactive stagnation worker for AmoCRM and Airtable projects.
"""
from __future__ import annotations

import datetime
import json
import logging
import os
from typing import Any, Dict, List, Optional

from aiogram import Bot
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


async def check_amocrm_stagnation():
    """Qotib qolgan leadlarni topib, menejerlarga conversion push yuborish."""
    import src.config as config
    from src.services.core.crm.amocrm_sync import AmoCRMSync

    db_cls = _resolve('Database', Database)
    db = db_cls()
    get_now_fn = _resolve('get_local_now', get_local_now)
    now = get_now_fn()
    today = now.strftime("%Y-%m-%d")
    target_hours = [12, 16]

    if now.hour not in target_hours or now.minute > 10:
        return

    job_key = f"sales_conversion_push_{now.hour}"
    if await db.is_job_run(job_key, today):
        return

    bot_token = os.environ.get("BOT_TOKEN") or getattr(config, "BOT_TOKEN", None)
    group_id = getattr(config, "STAGNATION_GROUP_ID", None) or getattr(config, "CRM_GROUP_ID", None)
    thread_id = getattr(config, "STAGNATION_TOPIC_ID", None)
    if thread_id is None:
        thread_id = getattr(config, "TOPIC_CRM_ID", None) or getattr(
            config, "TOPIC_REPORTS_ID", None
        )
    if not (bot_token and group_id):
        return

    amo = AmoCRMSync(
        config.AMOCRM_SUBDOMAIN,
        config.AMOCRM_CLIENT_ID,
        config.AMOCRM_CLIENT_SECRET,
        config.AMOCRM_REDIRECT_URL,
    )
    registry_fn = _resolve('build_default_tool_registry', build_default_tool_registry)
    registry = registry_fn(bot_token=bot_token, amocrm=amo)
    amocrm_tool = registry.get("amocrm_leads")
    stagnated = await amocrm_tool.fetch_stagnated_leads(hours=24)
    if not stagnated:
        last_error = (
            amocrm_tool.get_last_error()
            if hasattr(amocrm_tool, "get_last_error")
            else None
        )
        if last_error:
            message = (
                "⚠️ <b>AmoCRM ulanishi ishlamayapti</b>\n\n"
                "Oisha hozir CRMdan leadlarni ishonchli torta olmadi, shuning uchun "
                "<b>pipeline bo'sh</b> deb xulosa chiqarmaydi.\n"
                f"Sabab: <code>{escape(str(last_error))}</code>\n\n"
                "Kerakli ish: AmoCRM OAuth'ni qayta avtorizatsiya qiling; token yangilangach "
                "Oisha qotib qolgan leadlar uchun task/note yaratishni davom ettiradi."
            )
            task = AgentTask(
                task_id=f"{job_key}:amocrm_auth:{today}",
                kind="crm_auth_blocked",
                goal="AmoCRM token nosozligini yolg'on pipeline xulosasisiz xabar qilish",
                payload={
                    "group_id": group_id,
                    "thread_id": thread_id,
                    "crm_error": last_error,
                },
                planner_notes=[
                    "CRM token holati tekshiriladi",
                    "Pipeline bo'sh degan yolg'on xulosa yuborilmaydi",
                    "Jamoaga qayta avtorizatsiya kerakligi aytiladi",
                ],
                requested_by="scheduler",
            )

            async def auth_executor(agent_task: AgentTask) -> Dict[str, Any]:
                return await _resolve('_execute_telegram_notification', _execute_telegram_notification)(
                    registry,
                    group_id=group_id,
                    message=message,
                    thread_id=thread_id,
                    disable_web_page_preview=True,
                )

            result = await _resolve('_run_notification_agent', _run_notification_agent)(db, task, auth_executor)
            if result.success:
                await db.mark_job_run(job_key, today)
        return

    now_ts = int(now.timestamp())
    total_value = sum(int(lead.get("price") or 0) for lead in stagnated)

    from src.services.core.enterprise_reporter import EnterpriseReporter
    from src.services.core.crm.crm_service import CRMService

    crm_service = CRMService()
    reporter = EnterpriseReporter(db, crm_service)
    message = await reporter.get_stagnant_leads_alert(limit=50)

    if not message:
        return
    manager_ids = list(getattr(config, "SALES_MANAGER_IDS", []) or [])
    direct_messages = [
        {
            "user_id": manager_id,
            "text": (
                "ðŸš¨ <b>Sales Conversion Push</b>\n"
                "CRMda qotib qolgan leadlar bo'yicha guruhga report tashlandi.\n"
                "Bugun har bir lead uchun: 1) kontakt, 2) sabab, 3) next step sanasi yozilsin."
            ),
            "parse_mode": "HTML",
        }
        for manager_id in manager_ids
    ]
    task = AgentTask(
        task_id=f"{job_key}:{today}",
        kind="sales_conversion_push",
        goal="CRMdagi qotib qolgan leadlarni conversionga qaytarish",
        payload={
            "group_id": group_id,
            "thread_id": thread_id,
            "manager_ids": manager_ids,
            "lead_count": len(stagnated),
            "risk_sum": total_value,
        },
        planner_notes=[
            "Qotib qolgan leadlar menejer bo'yicha guruhlanadi",
            "CRM threadga conversion push yuboriladi",
            "Sales managerlarga DM orqali follow-up bosimi beriladi",
        ],
        requested_by="scheduler",
    )

    async def executor(agent_task: AgentTask) -> Dict[str, Any]:
        tool_results = []
        complete_till = int((now + datetime.timedelta(hours=6)).timestamp())
        for lead in sorted(
            stagnated,
            key=lambda item: (
                _lead_idle_hours(item, now_ts),
                int(item.get("price") or 0),
            ),
            reverse=True,
        )[:10]:
            lead_id = int(lead.get("id") or 0)
            if not lead_id:
                continue
            responsible_id = int(lead.get("responsible_user_id") or 0) or None
            _safe_text(lead.get("name"), "Lead")
            next_step = _sales_action_for_lead(lead)
            task_text = f"Oisha: qotib qolgan lead. Bugun {next_step}. Natijani CRM izohiga yozing."
            note_text = (
                "Oisha agent signal: lead 24+ soat qimirlamagan. "
                f"Tavsiya: {next_step}. Mas'ul: bugun keyingi sana va sababni CRMga kiritsin."
            )
            task_result = await amocrm_tool.create_followup_task(
                lead_id,
                task_text[:500],
                complete_till,
                responsible_user_id=responsible_id,
            )
            note_result = await amocrm_tool.add_lead_note(lead_id, note_text[:1000])
            tool_results.extend([task_result.to_payload(), note_result.to_payload()])

        execution = await _resolve('_execute_telegram_notification', _execute_telegram_notification)(
            registry,
            group_id=group_id,
            message=message,
            thread_id=thread_id,
            direct_messages=direct_messages,
            disable_web_page_preview=True,
        )
        execution.update(
            {
                "lead_count": agent_task.payload.get("lead_count"),
                "risk_sum": agent_task.payload.get("risk_sum"),
            }
        )
        execution["tool_results"] = tool_results
        failed_actions = [item for item in tool_results if not item.get("success")]
        if failed_actions:
            execution["success"] = False
            execution["reason"] = "crm_action_failed"
            execution["failed_action_count"] = len(failed_actions)
        return execution

    result = await _resolve('_run_notification_agent', _run_notification_agent)(db, task, executor)
    if not result.success:
        logger.error(
            f"[STAGNATION] Conversion push delivery failed: {result.verification}"
        )
        return

    await db.mark_job_run(job_key, today)
    logger.info(f"[STAGNATION] Conversion push sent for hour {now.hour}.")



async def check_airtable_stagnation():
    """Qimirlamay qolgan loyihalarni topib, PMga keyingi stage bo'yicha push yuborish."""
    logger.info("Airtable stagnation check started...")
    from src.services.core.airtable_sync import AirtableSync  # type: ignore
    import src.config as config

    db_cls = _resolve('Database', Database)
    db = db_cls()
    get_now_fn = _resolve('get_local_now', get_local_now)
    now = get_now_fn()
    today = now.strftime("%Y-%m-%d")
    target_hours = [11, 15, 18]

    if now.hour not in target_hours or now.minute > 10:
        return

    job_key = f"project_stage_push_{now.hour}"
    if await db.is_job_run(job_key, today):
        return

    bot_token = os.environ.get("BOT_TOKEN") or getattr(config, "BOT_TOKEN", None)
    group_id = (
        getattr(config, "PROJECTS_GROUP_ID", None)
        or getattr(config, "WOW_SERVICE_GROUP_ID", None)
        or getattr(config, "TEAM_GROUP_ID", None)
    )
    thread_id = (
        getattr(config, "PROJECTS_TOPIC_ID", None)
        or getattr(config, "WOW_SERVICE_TOPIC_ID", None)
        or getattr(config, "TOPIC_TASKS_ID", None)
    )
    if not (bot_token and group_id):
        return

    sync = AirtableSync()
    registry_fn = _resolve('build_default_tool_registry', build_default_tool_registry)
    registry = registry_fn(bot_token=bot_token, airtable=sync)
    airtable_tool = registry.get("airtable_projects")
    projects = await airtable_tool.fetch_projects()
    stalled_projects: List[Dict[str, Any]] = []

    for project in projects:
        fields = project.get("fields", {})
        stage = _safe_text(AirtableSync._get_field(fields, "stage"), "")
        if stage in AirtableSync.DONE_STAGES:
            continue

        deadline = AirtableSync._get_field(fields, "deadline")
        manager_raw = AirtableSync._get_field(fields, "manager")
        manager_name = AirtableSync.resolve_pm_name(manager_raw) if manager_raw else "PM"
        if not manager_name or manager_name == "Mas'ul belgilanmagan":
            manager_name = "PM"
        age_days = _project_age_days(project)
        is_overdue = False
        if deadline:
            try:
                deadline_dt = datetime.datetime.strptime(str(deadline), "%Y-%m-%d")
                is_overdue = deadline_dt.date() < now.date()
            except ValueError:
                is_overdue = False

        if age_days >= 3 or is_overdue:
            next_stage, unblock_action = _project_stage_recommendation(stage)
            p_name = _safe_text(AirtableSync._get_field(fields, "project_name"))
            if not p_name or p_name == "Noma'lum":
                p_name = _safe_text(
                    fields.get("Loyiha ID")
                    or fields.get("AmoCRM_ID")
                    or project.get("id"),
                    "Nomsiz loyiha",
                )
            stalled_projects.append(
                {
                    "name": p_name,
                    "stage": stage or "Noma'lum",
                    "manager": manager_name,
                    "deadline": deadline or "Belgilanmagan",
                    "age_days": age_days,
                    "is_overdue": is_overdue,
                    "next_stage": next_stage,
                    "action": unblock_action,
                }
            )

    if not stalled_projects:
        return

    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for project in stalled_projects:
        grouped.setdefault(project["manager"], []).append(project)

    lines = [
        "🏗 <b>PM Stage Push</b>",
        f"Qimirlamay qolgan loyiha: <b>{len(stalled_projects)}</b> ta",
        "Talab: bugun status yangilanadi yoki keyingi etapga o'tish sanasi qo'yiladi.",
        "",
    ]

    for manager_name, manager_projects in sorted(
        grouped.items(), key=lambda item: len(item[1]), reverse=True
    ):
        lines.append(
            f"👤 <b>{escape(manager_name)}</b> — {len(manager_projects)} ta loyiha"
        )
        for project in sorted(
            manager_projects,
            key=lambda item: (item["is_overdue"], item["age_days"]),
            reverse=True,
        )[:4]:
            risk_text = (
                "deadline o'tgan"
                if project["is_overdue"]
                else f"{project['age_days']} kun qimirlamagan"
            )
            lines.append(
                "• "
                f"<b>{escape(project['name'])}</b> — {escape(project['stage'])}, {risk_text}. "
                f"Keyingi stage: <b>{escape(project['next_stage'])}</b>."
            )
            lines.append(f"  📌 Bugungi qadam: {escape(project['action'])}")
        lines.append("")

    message = "\n".join(lines).strip()
    pm_user = await db.get_user_by_role("pm")
    direct_messages = []
    if pm_user and pm_user.get("user_id"):
        direct_messages.append(
            {
                "user_id": pm_user["user_id"],
                "text": (
                    "🏗 <b>PM Stage Push</b>\n"
                    "Airtable'da qimirlamay qolgan loyihalar bo'yicha report guruhga yuborildi.\n"
                    "Bugun har bir loyiha uchun keyingi stage yoki blocker yozilsin."
                ),
                "parse_mode": "HTML",
            }
        )

    task = AgentTask(
        task_id=f"{job_key}:{today}",
        kind="pm_stage_push",
        goal="Airtabledagi qimirlamay qolgan loyihalarni keyingi stagega surish",
        payload={
            "group_id": group_id,
            "thread_id": thread_id,
            "project_count": len(stalled_projects),
            "pm_user_id": pm_user.get("user_id") if pm_user else None,
        },
        planner_notes=[
            "Stalled loyihalar manager bo'yicha guruhlanadi",
            "PM threadga status push yuboriladi",
            "Mas'ul PMga shaxsiy DM bilan next-step talab qilinadi",
        ],
        requested_by="scheduler",
    )

    async def executor(agent_task: AgentTask) -> Dict[str, Any]:
        execution = await _resolve('_execute_telegram_notification', _execute_telegram_notification)(
            registry,
            group_id=group_id,
            message=message,
            thread_id=thread_id,
            direct_messages=direct_messages,
        )
        execution.update({"project_count": agent_task.payload.get("project_count")})
        return execution

    result = await _resolve('_run_notification_agent', _run_notification_agent)(db, task, executor)
    if not result.success:
        logger.error(
            f"[AIRTABLE STAGNATION] Project stage push delivery failed: {result.verification}"
        )
        return

    await db.mark_job_run(job_key, today)
    logger.info(f"[AIRTABLE STAGNATION] Project stage push sent for hour {now.hour}.")


