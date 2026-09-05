"""
Proactive Airtable project stagnation checker.
"""
from __future__ import annotations

import datetime
import html
import logging
import os
from typing import Any, Dict, List

from src.database import Database
from src.services.core.agent_loop import AgentTask
from src.services.core.airtable_sync import AirtableSync
from src.services.core.tool_adapters import (
    build_default_tool_registry,
)
from src.services.proactive.formatters import (
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
        if not mgr_raw or str(mgr_raw).strip() in ("", "None", "null", "[]"):
            mgr_raw = (
                fields.get("PM")
                or fields.get("Mas'ul")
                or fields.get("Masul")
                or fields.get("Responsible")
                or fields.get("Dizayner")
                or fields.get("Designer")
            )
        mgr_name = AirtableSync.resolve_pm_handle(mgr_raw) if mgr_raw else "@Inomjon_JonBranding"
        if not mgr_name or mgr_name == "Mas'ul belgilanmagan":
            mgr_name = "@Inomjon_JonBranding"

        age = _project_age_days(project)
        is_overdue = False
        if deadline:
            try:
                is_overdue = datetime.datetime.strptime(str(deadline), "%Y-%m-%d").date() < now.date()
            except ValueError:
                pass
        if age >= 3 or is_overdue:
            next_stg, action = _project_stage_recommendation(stage)
            raw_p_name = AirtableSync._get_field(fields, "project_name")
            if not raw_p_name or str(raw_p_name).strip() in ("", "Noma'lum", "None", "null", "[]"):
                raw_p_name = (
                    fields.get("Loyihani nomi?")
                    or fields.get("Loyiha nomi")
                    or fields.get("Project Name")
                    or fields.get("Name")
                    or fields.get("Mijoz")
                    or fields.get("Mijoz nomi")
                    or fields.get("Client")
                    or fields.get("Client Name")
                    or fields.get("Title")
                    or fields.get("Loyiha")
                    or fields.get("Loyiha ID")
                    or fields.get("AmoCRM_ID")
                )
            if not raw_p_name or str(raw_p_name).strip() in ("", "Noma'lum", "None", "null", "[]"):
                pid_str = str(project.get("id") or "")
                raw_p_name = f"Loyiha #{pid_str[-6:]}" if pid_str else "Loyiha"
            p_name = _safe_text(raw_p_name, "Loyiha")

            stalled.append({
                "name": p_name, "stage": stage or "Jarayonda", "manager": mgr_name,
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
    if now.hour not in [11, 15, 18]:
        return

    # Kunlik kalit (soat emas). Ilgari "_{now.hour}" edi — 11/15/18 = kuniga
    # 3 marta PM Stage Push. Endi kuniga bitta yetarli.
    job_key = f"project_stage_push_{today}"
    if await db.is_job_run(job_key, today):
        return
    # Atomik claim: yuborishdan OLDIN band qilamiz. Aks holda 11:00–11:10
    # oynasida ikki loop (bg_monitor + main_loop) parallel yuboradi —
    # mark_job_run faqat agent tugagach yozilardi, oradagi run'lar spam qilardi.
    _claimed = False
    if hasattr(db, "claim_job_run"):
        _claimed = await db.claim_job_run(job_key, today)
        if not _claimed:
            return

    bot_token = os.environ.get("BOT_TOKEN") or getattr(config, "BOT_TOKEN", None)
    group_id = -1003114662117
    thread_id = 1
    if not (bot_token and group_id):
        if _claimed and hasattr(db, "release_job_run"):
            await db.release_job_run(job_key, today)
        return

    sync = AirtableSync()
    registry = _resolve('build_default_tool_registry', build_default_tool_registry)(bot_token=bot_token, airtable=sync)
    projects = await registry.get("airtable_projects").fetch_projects()
    stalled = _filter_stalled_projects(projects, now)
    if not stalled:
        # Yuboriladigan narsa yo'q — claim'ni bo'shatamiz, keyingi oynada
        # (masalan 15:00) qayta tekshirilsin.
        if _claimed and hasattr(db, "release_job_run"):
            await db.release_job_run(job_key, today)
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
    elif _claimed and hasattr(db, "release_job_run"):
        # Yuborilmadi — claim'ni bo'shatamiz, keyingi oynada qayta urinsin.
        await db.release_job_run(job_key, today)
