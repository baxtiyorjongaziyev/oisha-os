"""
Autonomous Scheduler Runner Mixin for Admin Bot.
"""
from __future__ import annotations

import asyncio

import structlog
from src.services.core.admin_bot.cron_jobs import (
    run_client_journey_job,
    run_daily_missions_job,
    run_daily_plan_job,
    run_evening_fact_job,
    run_funnel_job,
    run_intelligence_audit_job,
    run_juma_job,
    run_junk_audit_job,
    run_lunch_reminder_job,
    run_morning_briefing_job,
    run_night_shift_job,
    run_scorecard_job,
    run_stagnation_job,
)
from src.time_utils import get_local_now, is_quiet_hours

logger = structlog.get_logger()


class AdminCronRunnerMixin:
    async def run_scheduler(self):
        """Fon rejimida vaqtni nazorat qilish va vazifalarni ishga tushirish."""
        import src.api_server as api_server_module

        logger.info("👸 [ADMIN_BOT] Full Autonomous Scheduler v2.0 ishga tushdi! 🛡️")
        while True:
            try:
                now = get_local_now()
                current_time = now.strftime("%H:%M")
                today = now.strftime("%Y-%m-%d")

                if is_quiet_hours(now):
                    logger.debug(
                        "[SCHEDULER] Quiet hours active. Automatic Telegram jobs are paused."
                    )
                    await asyncio.sleep(30)
                    continue

                # 1. Morning Briefing (09:45)
                if current_time == "09:45":
                    job_id = f"morning_briefing_{today}"
                    state = await self.db.get_state(job_id)
                    if state not in ("done", "running"):
                        await self.db.set_state(job_id, "running")
                        await run_morning_briefing_job(self.db, job_id, api_server_module)

                # 1.5 Daily Plan Discipline (10:15, 13:00, 16:30)
                daily_plan_slots = {
                    "10:15": "initial",
                    "13:00": "reminder",
                    "16:30": "escalation",
                }
                if current_time in daily_plan_slots:
                    phase = daily_plan_slots[current_time]
                    job_id = f"daily_plan_{phase}_{today}"
                    state = await self.db.get_state(job_id)
                    if state not in ("done", "running"):
                        await self.db.set_state(job_id, "running")
                        await run_daily_plan_job(self.db, job_id, phase, api_server_module)

                # 2. Daily Missions (10:00 va 14:00)
                if current_time in ["10:00", "14:00"]:
                    job_id = f"daily_{today}_{current_time}"
                    state = await self.db.get_state(job_id)
                    if state not in ("done", "running"):
                        await self.db.set_state(job_id, "running")
                        await run_daily_missions_job(self, self.db, job_id, current_time, api_server_module)

                # 2.25 Client Journey Excellence (11:00 va 17:00)
                if current_time in ["11:00", "17:00"]:
                    job_id = f"client_journey_{today}_{current_time}"
                    state = await self.db.get_state(job_id)
                    if state not in ("done", "running"):
                        await self.db.set_state(job_id, "running")
                        await run_client_journey_job(self.db, job_id, api_server_module)

                # 2.5 Lunch Reminder (13:00)
                if current_time == "13:00":
                    job_id = f"lunch_reminder_{today}"
                    state = await self.db.get_state(job_id)
                    if state not in ("done", "running"):
                        await self.db.set_state(job_id, "running")
                        await run_lunch_reminder_job(self.db, job_id, api_server_module)

                # 3. Evening Fact Report (21:00)
                if current_time == "21:00":
                    job_id = f"evening_fact_{today}"
                    state = await self.db.get_state(job_id)
                    if state not in ("done", "running"):
                        await self.db.set_state(job_id, "running")
                        await run_evening_fact_job(self.db, job_id, api_server_module)

                # 4. Night Shift — CRM Cleanup (01:00)
                if current_time == "01:00":
                    job_id = f"night_shift_{today}"
                    state = await self.db.get_state(job_id)
                    if state not in ("done", "running"):
                        await self.db.set_state(job_id, "running")
                        await run_night_shift_job(self, self.db, job_id, api_server_module)

                # 5. Intelligence Audit (02:00)
                if current_time == "02:00":
                    job_id = f"intelligence_audit_{today}"
                    state = await self.db.get_state(job_id)
                    if state not in ("done", "running"):
                        await self.db.set_state(job_id, "running")
                        await run_intelligence_audit_job(self.db, job_id, api_server_module)

                # 5.5 Junk Audit (02:30)
                if current_time == "02:30":
                    job_id = f"junk_audit_{today}"
                    state = await self.db.get_state(job_id)
                    if state not in ("done", "running"):
                        await self.db.set_state(job_id, "running")
                        await run_junk_audit_job(self.db, job_id, api_server_module)

                # 6. Menejer Scorecard (18:30)
                if current_time == "18:30":
                    job_id = f"scorecard_{today}"
                    state = await self.db.get_state(job_id)
                    if state not in ("done", "running"):
                        await self.db.set_state(job_id, "running")
                        await run_scorecard_job(self.db, job_id, api_server_module)

                # 7. Stagnatsiya Alert (12:00)
                if current_time == "12:00":
                    job_id = f"stagnation_{today}"
                    state = await self.db.get_state(job_id)
                    if state not in ("done", "running"):
                        await self.db.set_state(job_id, "running")
                        await run_stagnation_job(self.db, job_id, api_server_module)

                # 8. Juma Mubarak (Juma 09:00)
                if now.weekday() == 4 and current_time == "09:00":
                    job_id = f"juma_mubarak_{today}"
                    state = await self.db.get_state(job_id)
                    if state not in ("done", "running"):
                        await self.db.set_state(job_id, "running")
                        await run_juma_job(self, self.db, job_id, api_server_module)

                # 9. Pipeline Funnel (Dushanba 09:30)
                if now.weekday() == 0 and current_time == "09:30":
                    job_id = f"funnel_{today}"
                    state = await self.db.get_state(job_id)
                    if state not in ("done", "running"):
                        await self.db.set_state(job_id, "running")
                        await run_funnel_job(self.db, job_id, api_server_module)

                await asyncio.sleep(30)
            except Exception as e:
                logger.error(f"[SCHEDULER ERROR] {e}")
                await asyncio.sleep(60)
