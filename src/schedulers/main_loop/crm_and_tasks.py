"""
CRM stagnation, deadline checking, task alerts, and lead OS cycle execution.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import src.main as m
from src.schedulers.main_loop.helpers import _is_due

logger = logging.getLogger("OishaScheduler")


async def run_stagnation_and_tasks(now: datetime, monitor_fn: Any) -> None:
    from src.services.core.proactive_worker import (
        check_amocrm_stagnation,
        check_airtable_deadlines,
        send_overdue_nudges,
        check_airtable_stagnation,
        check_client_journey_excellence,
    )
    from src.services.core.leads.lead_operating_system import LeadOperatingSystem

    # 1. Stagnatsiya va Deadline tekshirish
    await check_amocrm_stagnation()
    await check_airtable_stagnation()
    await check_client_journey_excellence()
    
    if now.hour in [10, 15] and now.minute < 5:
        await check_airtable_deadlines()

    # AmoCRM task due/overdue alert dispatch (Follow-up topic)
    try:
        from src.services.core.amocrm_task_notifier import AmoCrmTaskNotifier
        from src.context import app_ctx
        from src.main import get_surgical_integration

        amocrm_client = None
        if m.msg_controller and getattr(m.msg_controller, "crm", None):
            amocrm_client = getattr(m.msg_controller.crm, "amocrm", None)
        if not amocrm_client and get_surgical_integration:
            amocrm_client = get_surgical_integration().amocrm

        bot_rt = getattr(app_ctx, "bot_runtime", None) or getattr(m, "bot_runtime", None) or getattr(m, "bot_client", None)
        db_inst = getattr(m.msg_controller, "db", None) if m.msg_controller else None

        if amocrm_client and bot_rt:
            notifier = AmoCrmTaskNotifier(amocrm=amocrm_client, db=db_inst, bot_runtime=bot_rt)
            await notifier.check_and_notify_due_tasks()
    except Exception as task_exc:
        logger.error("[TASK_NOTIFIER] Scheduler task check failed: %s", task_exc)

    if m.msg_controller:
        if not hasattr(monitor_fn, "_lead_os"):
            monitor_fn._lead_os = LeadOperatingSystem(
                m.msg_controller, m.msg_controller.db
            )
        last_cycle_at = getattr(monitor_fn, "_lead_cycle_at", None)
        if not last_cycle_at or (now - last_cycle_at).total_seconds() >= 900:
            await monitor_fn._lead_os.review_recent_active_leads(
                limit=12,
                lookback_hours=72,
                execute_actions=True,
            )
            monitor_fn._lead_cycle_at = now

        if any(_is_due(now, h, 0) for h in [10, 14, 18, 22]):
            today_str = now.strftime("%Y-%m-%d")
            job_key = f"lead_reengagement_{now.hour}_{today_str}"
            if not hasattr(monitor_fn, "_sent_jobs"):
                monitor_fn._sent_jobs = set()
            if job_key not in monitor_fn._sent_jobs:
                await monitor_fn._lead_os.run_reengagement_cycle(
                    limit=8
                )
                monitor_fn._sent_jobs.add(job_key)

    # Overdue tasks
    if now.hour == 11 and now.minute < 5:
        await send_overdue_nudges()
