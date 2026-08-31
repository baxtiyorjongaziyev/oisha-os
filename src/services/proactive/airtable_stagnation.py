"""
Proactive Airtable project stagnation checker.
"""
from __future__ import annotations

import datetime
import html
import logging
import os
from typing import Any, Dict, List, Optional

from src.database import Database
from src.services.core.agent_loop import AgentTask
from src.services.core.airtable_sync import AirtableSync
from src.services.core.tool_adapters import (
    build_default_tool_registry,
    send_group_message_with_fallback,
)
from src.services.proactive.formatters import (
    _mention,
    _project_age_days,
    _project_stage_recommendation,
    _run_notification_agent,
    _safe_text,
)
from src.services.proactive.reminders import _execute_telegram_notification
from src.services.proactive.airtable_deadlines import _resolve
from src.time_utils import get_local_now

logger = logging.getLogger(__name__)


def _filter_stalled_projects(projects: List[Dict[str, Any]], now: datetime.datetime) -> List[Dict[str, Any]]:
    stalled = []
    for project in projects:
        fields = project.get("fields", {})
        stage = _safe_text(AirtableSync._get_field(fields, "stage"), "")
        if stage in AirtableSync.DONE_STAGES:
            continue
        deadline = AirtableSync._get_field(fields, "deadline")
        mgr_raw = AirtableSync._get_field(fields, "manager")
        mgr_name = AirtableSync.resolve_pm_name(mgr_raw) if mgr_raw else "PM"
        age = _project_age_days(project)
        is_overdue = False
        if deadline:
            try:
                is_overdue = datetime.datetime.strptime(str(deadline), "%Y-%m-%d").date() < now.date()
            except ValueError:
                pass
        if age >= 3 or is_overdue:
            next_stg, action = _project_stage_recommendation(stage)
            p_name = _safe_text(AirtableSync._get_field(fields, "project_name"))
            if not p_name or p_name == "Noma'lum":
                p_name = _safe_text(
                    fields.get("Loyiha ID")
                    or fields.get("AmoCRM_ID")
                    or project.get("id"),
                    "Nomsiz loyiha",
                )
            stalled.append({
                "name": p_name, "stage": stage or "Noma'lum", "manager": mgr_name,
                "deadline": deadline or "Belgilanmagan", "age_days": age,
                "is_overdue": is_overdue, "next_stage": next_stg, "action": action,
            })
    return stalled


def _format_stalled_report(stalled: List[Dict[str, Any]]) -> str:
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for p in stalled:
        grouped.setdefault(p["manager"], []).append(p)
    lines = [
        "🏗 <b>PM Stage Push</b>",
        f"Qimirlamay qolgan loyiha: <b>{len(stalled)}</b> ta",
        "Talab: bugun status yangilanadi yoki keyingi etapga o'tish sanasi qo'yiladi.\n",
    ]
    for mgr, projs in sorted(grouped.items(), key=lambda x: len(x[1]), reverse=True):
        lines.append(f"👤 <b>{html.escape(mgr)}</b> — {len(projs)} ta loyiha")
        for p in projs[:4]:
            risk = "deadline o'tgan" if p["is_overdue"] else f"{p['age_days']} kun qimirlamagan"
            lines.append(f"• <b>{html.escape(p['name'])}</b> — {html.escape(p['stage'])}, {risk}. Keyingi: {html.escape(p['next_stage'])}")
            if p.get("action"):
                lines.append(f"  📌 Bugungi qadam: {html.escape(p['action'])}")
        lines.append("")
    return "\n".join(lines).strip()


async def check_airtable_stagnation():
    """Qimirlamay qolgan loyihalarni topib, PMga push yuborish."""
    import src.config as config
    db = _resolve('Database', Database)()
    now = _resolve('get_local_now', get_local_now)()
    today = now.strftime("%Y-%m-%d")
    if now.hour not in [11, 15, 18] or now.minute > 10:
        return

    job_key = f"project_stage_push_{now.hour}"
    if await db.is_job_run(job_key, today):
        return

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
        return

    sync = AirtableSync()
    registry = _resolve('build_default_tool_registry', build_default_tool_registry)(bot_token=bot_token, airtable=sync)
    projects = await registry.get("airtable_projects").fetch_projects()
    stalled = _filter_stalled_projects(projects, now)
    if not stalled:
        return

    message = _format_stalled_report(stalled)
    pm_user = await db.get_user_by_role("pm")
    direct_msgs = [{"user_id": pm_user["user_id"], "text": "🏗 <b>PM Stage Push</b>\nAirtable'da qimirlamay qolgan loyihalar bor.", "parse_mode": "HTML"}] if (pm_user and pm_user.get("user_id")) else []

    task = AgentTask(
        task_id=f"{job_key}:{today}", kind="pm_stage_push",
        goal="Airtabledagi qimirlamay qolgan loyihalarni keyingi stagega surish",
        payload={"group_id": group_id, "thread_id": thread_id, "project_count": len(stalled)},
        planner_notes=["PM threadga status push yuboriladi"], requested_by="scheduler",
    )
    async def executor(t: AgentTask) -> Dict[str, Any]:
        return await _resolve('_execute_telegram_notification', _execute_telegram_notification)(
            registry, group_id=group_id, message=message, thread_id=thread_id, direct_messages=direct_msgs,
        )

    result = await _resolve('_run_notification_agent', _run_notification_agent)(db, task, executor)
    if result.success:
        await db.mark_job_run(job_key, today)
