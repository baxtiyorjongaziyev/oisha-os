import logging
import datetime
from typing import Dict, Any, Optional
from src.database import Database
from src.services.core.airtable_sync import AirtableSync
from src.services.core.crm_service import CRMService
from src.services.core.persona_hub import EXTERNAL_CONCIERGE_PROMPT

logger = logging.getLogger(__name__)


class WowServiceEngine:
    """Oisha-OS Wow-Service Engine: Mikromenajment va mijoz ko'nglini olish (concierge)."""

    def __init__(self, db: Database, bot_client=None):
        self.db = db
        self.bot_client = bot_client
        self.crm = CRMService()
        self.airtable = AirtableSync()
        self.external_prompt = EXTERNAL_CONCIERGE_PROMPT

    async def process_active_journeys(self):
        """Hozirgi barcha aktiv lid va loyihalarni servis sifati bo'yicha audit qilish."""
        logger.info("[WOW-ENGINE] Starting service audit...")

        # 1. AmoCRM Lids (Sales Journey)
        leads = await self.crm.amocrm.get_leads()
        for lead in leads:
            await self._audit_lead_journey(lead)

        # 2. Airtable Projects (PM Journey)
        projects = await self.airtable.get_projects()
        for project in projects:
            await self._audit_project_journey(project)

    async def _audit_lead_journey(self, lead: Dict[str, Any]):
        lead_id = lead.get("id")
        status_id = int(lead.get("status_id") or 0)

        # Checkpoint: First Contact Quality
        if status_id == 142:  # Masalan: 'Yangi lid' statusi
            await self._trigger_checkpoint(
                external_id=lead_id,
                key="lead_welcome_audit",
                delay_hours=1,
                target_user_id=int(lead.get("responsible_user_id") or 0),
                message=f"🚀 <b>Yangi lid: {lead.get('name')}</b>\nWelcome-pack va mini-audit yubordingizmi? Birinchi 1 soat ichidagi 'Wow' taassurot eng muhimi!",
                wow_action="Mijozga 3 ta foydali ideya va discovery savollarini yuboring.",
            )

    async def _audit_project_journey(self, project: Dict[str, Any]):
        fields = project.get("fields", {})
        project_id = project.get("id")
        stage = str(AirtableSync._get_field(fields, "stage")).lower()
        pm_handle = AirtableSync.resolve_pm_handle(
            AirtableSync._get_field(fields, "manager")
        )

        # PM Telegram ID sini topish
        pm_user = await self.db.get_user_by_username(pm_handle.replace("@", ""))
        pm_id = pm_user["user_id"] if pm_user else None

        # Checkpoint: Kickoff Recap (Project Start)
        if any(token in stage for token in ("brief", "brif", "start")):
            await self._trigger_checkpoint(
                external_id=project_id,
                key="project_kickoff_recap",
                delay_hours=24,
                target_user_id=pm_id,
                message=f"📂 <b>Loyiha: {fields.get('Loyihani nomi?')}</b>\nKickoff summary va 7 kunlik plan yuborildimi? Mijoz keyingi 1 haftada nima bo'lishini bilishi shart.",
                wow_action="Telegram guruhga kickoff summary va mas'ullar xaritasini tashlang.",
            )

        # Checkpoint: Design Micro-Update (Middle)
        if any(token in stage for token in ("design", "dizayn", "maket")):
            await self._trigger_checkpoint(
                external_id=project_id,
                key="design_daily_update",
                delay_hours=48,  # Har 48 soatda "jimlik"ni tekshirish
                target_user_id=pm_id,
                message=f"🎨 <b>Dizayn: {fields.get('Loyihani nomi?')}</b>\n2 kundan beri yangilik yo'q. Draft tayyor bo'lmasa ham, 'biz ishlayapmiz' deb micro-update bering.",
                wow_action="Mijozga ish jarayonidan bitta 'behind the scenes' skrinshot yuboring.",
            )

        # Checkpoint: Handoff Success Kit (End)
        if any(token in stage for token in ("done", "topshirish")):
            await self._trigger_checkpoint(
                external_id=project_id,
                key="handoff_success_kit",
                delay_hours=0,
                target_user_id=pm_id,
                message=f"🎁 <b>Topshirish: {fields.get('Loyihani nomi?')}</b>\nFaqat fayllar emas, Success-kit va 'qanday foydalanish' bo'yicha guide yuboring.",
                wow_action="Mijozga barcha fayllar, shriftlar va qo'llanmani bitta chiroyli paketda bering.",
            )

    async def _trigger_checkpoint(
        self,
        external_id: str,
        key: str,
        delay_hours: int,
        target_user_id: Optional[int],
        message: str,
        wow_action: str,
    ):
        checkpoint = await self.db.get_checkpoint(external_id, key)

        if checkpoint and checkpoint["status"] == "Done":
            return

        created_at = (
            checkpoint["created_at"]
            if checkpoint
            else datetime.datetime.now().isoformat()
        )
        if not checkpoint:
            # Birinchi marta yaratish (wait period boshlanadi)
            await self.db.mark_checkpoint_notified(external_id, key)  # Upsert
            return

        # Tekshirish: delay vaqti o'tdimi?
        created_dt = datetime.datetime.fromisoformat(created_at)
        if datetime.datetime.now() - created_dt < datetime.timedelta(hours=delay_hours):
            return

        # Nudge yuborish (faqat bir marta yoki ma'lum vaqtda)
        last_notified = checkpoint["last_notified_at"]
        if last_notified:
            last_dt = datetime.datetime.fromisoformat(last_notified)
            if datetime.datetime.now() - last_dt < datetime.timedelta(hours=12):
                return  # Har 12 soatda bir marta nudge

        if target_user_id and self.bot_client:
            full_msg = f"{message}\n\n💡 <b>WOW MOMENT:</b>\n{wow_action}"
            try:
                await self.bot_client.send_message(
                    target_user_id, full_msg, parse_mode="html"
                )
                await self.db.mark_checkpoint_notified(external_id, key)
                logger.info(f"[WOW-ENGINE] Nudge sent to {target_user_id} for {key}")
            except Exception as e:
                logger.error(
                    f"[WOW-ENGINE ERROR] Failed to nudge {target_user_id}: {e}"
                )
