"""
Call quality, psychological coaching, and heartbeat jobs mixin for background monitor.
"""
from __future__ import annotations

import logging
from datetime import datetime


logger = logging.getLogger("BackgroundMonitor")


class JobsAnalyticsMixin:
    """Call quality, conversion analytics, and psychological mindset jobs."""

    async def _job_call_quality_daily(self, now: datetime) -> None:
        """Kunlik savdo sifati: eng yaxshi sotuvchi + o'sish nuqtalari."""
        key = self._job_key("call_quality_daily", now)
        if self._already_sent(key):
            return

        try:
            from src.services.core.sales_quality_coach import SalesQualityCoach

            db = self._get_db()
            if db is None:
                logger.warning("[COACH] DB ulanmagan — kunlik hisobot o'tkazildi")
                return

            coach = SalesQualityCoach(db=db)
            report = await coach.generate_daily_report(now.strftime("%Y-%m-%d"))
            if report:
                send_kwargs = {}
                if self.settings and getattr(self.settings, "TOPIC_REPORTS_ID", None):
                    send_kwargs["reply_to"] = self.settings.TOPIC_REPORTS_ID
                await self._send_to_group_or_admin(report, **send_kwargs)
                logger.info("[COACH] Kunlik sifat hisoboti yuborildi.")
            else:
                logger.info("[COACH] Bugun baholangan qo'ng'iroq yo'q.")
        except Exception as exc:
            logger.error("[COACH][DAILY] Error: %s", exc)
        self._mark_sent(key)

    async def _job_call_quality_weekly(self, now: datetime) -> None:
        """Haftalik: tarixdan ideal skript + playbook takliflari.

        Ikkalasi ham TAKLIF — playbook avtomatik o'zgarmaydi.
        """
        key = self._job_key("call_quality_weekly", now)
        if self._already_sent(key):
            return

        try:
            from src.services.core.sales_quality_coach import SalesQualityCoach

            db = self._get_db()
            if db is None:
                logger.warning("[COACH] DB ulanmagan — haftalik tahlil o'tkazildi")
                return

            coach = SalesQualityCoach(db=db)

            script = await coach.generate_ideal_script()
            if script:
                await self._notify_admin(
                    "📘 IDEAL SKRIPT (eng yaxshi qo'ng'iroqlardan sintez qilindi)\n"
                    "Tasdiqlashingiz uchun taklif:\n\n" + script
                )
                logger.info("[COACH] Ideal skript yuborildi.")

            suggestions = await coach.suggest_playbook_improvements()
            if suggestions:
                await self._notify_admin(
                    "🧭 PLAYBOOK TAKLIFLARI (oxirgi 7 kun tahlili)\n\n" + suggestions
                )
                logger.info("[COACH] Playbook takliflari yuborildi.")
        except Exception as exc:
            logger.error("[COACH][WEEKLY] Error: %s", exc)
        self._mark_sent(key)

    async def _job_conversion_weekly(self, now: datetime) -> None:
        """Haftalik konversiya tahlili: jamoa hisoboti + sotuvchi kartochkalari.

        Kunlik hisobot BALL bo'yicha saflaydi; bu esa KONVERSIYA bo'yicha va
        har bir sotuvchiga shu hafta tuzatishi kerak bo'lgan BITTA bosqichni
        beradi. Kartochkalar rahbarga yuboriladi — sotuvchiga qanday
        yetkazish rahbar qaroriga qoladi.
        """
        key = self._job_key("conversion_weekly", now)
        if self._already_sent(key):
            return

        try:
            from src.services.core.metasell_conversion import MetaSellConversionEngine

            db = self._get_db()
            if db is None:
                logger.warning("[METASELL] DB ulanmagan — konversiya tahlili o'tkazildi")
                return

            # Pul ko'rsatkichlari eskirmasligi uchun AVVAL AmoCRM'dan
            # bitim narxi va yakunini yangilaymiz — hisobot shundan keyin.
            amocrm_client = self._get_amocrm_client()
            if amocrm_client:
                from src.services.core.metasell_revenue import MetaSellRevenueSync

                try:
                    sync_result = await MetaSellRevenueSync(
                        db=db, amocrm=amocrm_client
                    ).sync(days=90)
                    logger.info("[METASELL] Daromad sinxroni: %s", sync_result.to_dict())
                except Exception as exc:
                    # Pul yangilanmasa ham hisobot chiqishi kerak — eski
                    # raqamlar hisobotsiz qolishdan yaxshiroq.
                    logger.error("[METASELL] Daromad sinxroni yiqildi: %s", exc)
            else:
                logger.info("[METASELL] AmoCRM ulanmagan — pul yangilanmadi")

            engine = MetaSellConversionEngine(db=db)
            diagnoses = await engine.diagnose_all(days=30)
            trend = await engine.conversion_trend(days=30)
            volumes = await engine.fetch_volumes(days=30)

            team_report = engine.build_team_report(diagnoses, trend, volumes)
            if team_report:
                send_kwargs = {}
                if self.settings and getattr(self.settings, "TOPIC_REPORTS_ID", None):
                    send_kwargs["reply_to"] = self.settings.TOPIC_REPORTS_ID
                await self._send_to_group_or_admin(team_report, **send_kwargs)
                logger.info("[METASELL] Jamoa konversiya hisoboti yuborildi.")
            else:
                logger.info("[METASELL] Konversiya hisoboti uchun ma'lumot yetarli emas.")

            sent = 0
            for diagnosis in diagnoses:
                if not diagnosis.has_diagnosis:
                    continue
                await self._notify_admin(
                    engine.build_seller_card(
                        diagnosis, volumes.get(diagnosis.manager_name)
                    )
                )
                sent += 1
            if sent:
                logger.info("[METASELL] %s ta sotuvchi kartochkasi yuborildi.", sent)
        except Exception as exc:
            logger.error("[METASELL][WEEKLY] Error: %s", exc)
        self._mark_sent(key)

    async def _job_heartbeat(self) -> None:
        if self.client:
            try:
                from telethon import functions
                await self.client(functions.account.UpdateStatusRequest(offline=False))
                logger.debug("[HEARTBEAT] Account status set to ONLINE")
            except Exception as exc:
                logger.warning("[HEARTBEAT] Failed to update status: %s", exc)

    async def _job_auto_tasks(self, now: datetime) -> None:
        """CRM leadlarni AI tahlili asosida smart task yaratish."""
        key = self._job_key("auto_tasks", now)
        if self._already_sent(key):
            return

        try:
            from src.services.core.smart_task_creator import run_smart_task_creation

            stats = await run_smart_task_creation(dry_run=False)
            if stats["tasks_created"] > 0:
                logger.info(
                    "[SMART_TASKS] Created %d smart tasks (analyzed %d leads)",
                    stats["tasks_created"],
                    stats["analyzed"],
                )
            self._mark_sent(key)
        except Exception as exc:
            logger.error("[SMART_TASKS] Error: %s", exc)

    async def _job_psychological_mindset_boost(self, now: datetime) -> None:
        """Ertalabki 09:15 jamoaviy psixologik impuls."""
        key = self._job_key("psych_mindset_boost", now)
        if self._already_sent(key):
            return

        try:
            from src.services.core.psychological_automation import PsychologicalAutomationService

            service = PsychologicalAutomationService(bot_client=self.bot_client)
            boost_text = service.generate_morning_boost()
            send_kwargs = {}
            if self.settings and getattr(self.settings, "TOPIC_REPORTS_ID", None):
                send_kwargs["reply_to"] = self.settings.TOPIC_REPORTS_ID
            await self._send_to_group_or_admin(boost_text, **send_kwargs)
            logger.info("[PSYCH_AUTO] Morning mindset boost sent.")
        except Exception as exc:
            logger.error("[PSYCH_AUTO][MINDSET] Error: %s", exc)
        self._mark_sent(key)

    async def _job_sales_reluctance_automation(self, now: datetime) -> None:
        """Sotuvchilarning qo'ng'iroqdan qochishini avtomatik aniqlash va kouching (11:30, 15:30)."""
        key = self._job_key("sales_reluctance_auto", now, suffix=str(now.hour))
        if self._already_sent(key):
            return

        try:
            from src.services.core.psychological_automation import PsychologicalAutomationService

            amocrm_client = self._get_amocrm_client()
            service = PsychologicalAutomationService(
                db=self._get_db(),
                amocrm=amocrm_client,
                bot_client=self.bot_client,
            )
            interventions = await service.scan_and_generate_sales_reluctance_interventions(limit=3)
            if interventions:
                target_group = (
                    getattr(self.settings, "CRM_GROUP_ID", None)
                    or getattr(self.settings, "TEAM_GROUP_ID", None)
                    or self.TN5_GROUP_ID
                )
                topic_id = getattr(self.settings, "TOPIC_CRM_ID", None)
                sent = await service.deliver_interventions(interventions, target_group, topic_id=topic_id)
                logger.info("[PSYCH_AUTO] Sent %d sales reluctance interventions.", sent)
        except Exception as exc:
            logger.error("[PSYCH_AUTO][SALES] Error: %s", exc)
        self._mark_sent(key)

    async def _job_pm_conflict_automation(self, now: datetime) -> None:
        """PM loyiha kechikishi va konflikt himoyasi (11:45, 16:30)."""
        key = self._job_key("pm_conflict_auto", now, suffix=str(now.hour))
        if self._already_sent(key):
            return

        try:
            from src.services.core.psychological_automation import PsychologicalAutomationService

            service = PsychologicalAutomationService(
                db=self._get_db(),
                bot_client=self.bot_client,
            )
            interventions = await service.scan_and_generate_pm_interventions(limit=3)
            if interventions:
                target_group = (
                    getattr(self.settings, "TEAM_GROUP_ID", None)
                    or getattr(self.settings, "CRM_GROUP_ID", None)
                    or self.TN5_GROUP_ID
                )
                topic_id = getattr(self.settings, "TOPIC_REPORTS_ID", None)
                sent = await service.deliver_interventions(interventions, target_group, topic_id=topic_id)
                logger.info("[PSYCH_AUTO] Sent %d PM conflict interventions.", sent)
        except Exception as exc:
            logger.error("[PSYCH_AUTO][PM] Error: %s", exc)
        self._mark_sent(key)
