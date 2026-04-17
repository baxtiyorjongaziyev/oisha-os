import asyncio
import logging
from datetime import datetime

from src.services.core.amocrm_sync import AmoCRMSync
from src.services.core.airtable_sync import AirtableSync

logger = logging.getLogger(__name__)


class WorkflowOrchestrator:
    """
    AmoCRM -> Airtable -> Portfolio zanjirini boshqaradigan markaziy miya.
    """

    def __init__(
        self,
        amocrm: AmoCRMSync,
        airtable: AirtableSync,
        notify_callback=None,
        team_group_id=None,
        advisor_agent=None,
    ):
        self.amocrm = amocrm
        self.airtable = airtable
        self.notify_callback = notify_callback
        self.team_group_id = team_group_id
        self.advisor_agent = advisor_agent

        self.AMO_TRIGGER_STATUS = 142
        self.AIRTABLE_DONE_STAGE = "Done"

        self.TEAM = ["Ali", "Vali", "G'ani"]
        self._last_assigned_index = 0
        self._stage_sync_cache = {}
        self._deadline_alerted_ids = set()
        self._portfolio_requested_ids = set()

    def _get_next_manager(self):
        """Managerlarni navbatma-navbat tayinlash."""
        manager = self.TEAM[self._last_assigned_index]
        self._last_assigned_index = (self._last_assigned_index + 1) % len(self.TEAM)
        return manager

    async def _notify(self, text: str, send_to_team=True):
        """Xabarni owner/admin callback orqali yuborish."""
        if self.notify_callback:
            await self.notify_callback(text)

        if send_to_team and self.team_group_id:
            try:
                # Callback team guruhga yo'naltirishni o'zi hal qiladi.
                pass
            except Exception as exc:
                logger.error(f"[TEAM NOTIFY ERROR] {exc}")

    async def run_systematizer_sync(self, client=None):
        """
        1. AmoCRM'dagi yutilgan bitimlarni tekshiradi.
        2. Airtable'da loyiha yaratadi.
        3. Done loyihalarni portfolio oqimiga tayyorlaydi.
        """
        logger.info("👸 Oisha-OS: 'Order-to-Portfolio' tizimlashtirish tekshiruvi boshlandi... 🛡️")

        leads = await self.amocrm.get_leads(status_id=self.AMO_TRIGGER_STATUS)
        existing_projects = self.airtable.get_projects()

        for lead in leads:
            lead_id = lead.get("id")
            lead_name = lead.get("name")

            matched_project = None
            for project in existing_projects:
                project_name = self.airtable._get_field(project.get("fields", {}), "project_name")
                if project_name == lead_name:
                    matched_project = project
                    break

            if matched_project is None:
                logger.info(f"🚀 Yangi bitim aniqlandi! Airtable-da loyiha yaratilmoqda: {lead_name}")

                manager = self._get_next_manager()
                new_project_fields = {
                    "Loyihani nomi?": lead_name,
                    "Loyiha bosqichi": "Brief (Kelishuv)",
                    "Kelishgan narx": lead.get("price", 0),
                    "Start sana": datetime.now().strftime("%Y-%m-%d"),
                }

                result = self.airtable.create_record(new_project_fields)
                if result:
                    existing_projects.append(result)
                    self._stage_sync_cache[str(lead_id)] = "Brief (Kelishuv)"

                self.amocrm.add_lead_note(lead_id, f"Oisha: Airtable-da loyiha ochildi. Mas'ul: {manager} ✅")
                continue

            fields = matched_project.get("fields", {})
            current_stage = self.airtable._get_field(fields, "stage")
            last_sync = self._stage_sync_cache.get(str(lead_id))

            if current_stage and current_stage != last_sync:
                logger.info(f"🔄 Status Sync: {lead_name} -> {current_stage}")
                self.amocrm.add_lead_note(
                    lead_id,
                    f"Oisha Update: Loyiha bosqichi '{current_stage}' ga o'zgardi. 👸🛡️",
                )
                self._stage_sync_cache[str(lead_id)] = current_stage

                if current_stage == self.AIRTABLE_DONE_STAGE:
                    manager_name = self.airtable._get_field(fields, "manager") or "PM tayinlanmagan"
                    await self._notify(
                        f"🥳 **Muvaffaqiyat!**\n\n"
                        f"'{lead_name}' loyihasi yakunlandi! ✅\n"
                        f"Manager: {manager_name}\n\n"
                        f"Jamoani tabriklayman! 👸👑"
                    )

        upcoming = self.airtable.get_upcoming_deadlines(hours=24)
        for project in upcoming:
            record_id = project.get("id")
            if record_id in self._deadline_alerted_ids:
                continue

            fields = project.get("fields", {})
            project_name = self.airtable._get_field(fields, "project_name") or "Nomsiz loyiha"
            manager_name = self.airtable._get_field(fields, "manager") or "PM tayinlanmagan"
            logger.warning(f"⏰ [ALERT] Loyiha muddati yaqin: {project_name}")
            await self._notify(
                f"⚠️ **DIQQAT!**\n\n"
                f"'{project_name}' loyihasi muddati tugashiga 24 soatdan kam vaqt qoldi! ⏳\n"
                f"Mas'ul: {manager_name}\n\n"
                f"Iltimos, harakatni tezlashtiring! 👸🛡️"
            )
            self._deadline_alerted_ids.add(record_id)

        done_projects = self.airtable.get_projects_by_stage(self.AIRTABLE_DONE_STAGE)
        for project in done_projects:
            record_id = project.get("id")
            if record_id in self._portfolio_requested_ids:
                continue

            fields = project.get("fields", {})
            project_name = self.airtable._get_field(fields, "project_name") or "Nomsiz loyiha"
            logger.info(f"✨ Loyiha '{project_name}' yakunlandi! Portfolio so'rovi yuborilmoqda...")
            self._portfolio_requested_ids.add(record_id)

        logger.info("👸 Oisha-OS: Tizimlashtirish tekshiruvi yakunlandi. 👸🛡️")

    async def background_loop(self, interval_minutes=15):
        """Uzluksiz tekshiruv sikli."""
        while True:
            try:
                await self.run_systematizer_sync()
            except Exception as exc:
                logger.error(f"❌ WorkflowOrchestrator-da xato: {exc}")
            await asyncio.sleep(interval_minutes * 60)
