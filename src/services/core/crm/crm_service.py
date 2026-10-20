import logging
from src.services.core.crm.amocrm_sync import AmoCRMSync
from src.services.core.airtable_sync import AirtableSync
import src.config as config

logger = logging.getLogger(__name__)


class CRMService:
    """AmoCRM va Airtable integratsiyasini birlashtirgan xizmat."""

    def __init__(self):
        self.amocrm = AmoCRMSync(
            config.AMOCRM_SUBDOMAIN,
            config.AMOCRM_CLIENT_ID,
            config.AMOCRM_CLIENT_SECRET,
            config.AMOCRM_REDIRECT_URL,
        )
        self.airtable = AirtableSync()  # Config ichidan o'zi oladi

    async def sync_lead(self, user_id: int, name: str, phone: str, **kwargs):
        """Leadni AmoCRM va Airtable-da sinxronizatsiya qilish."""
        # Hunter yagona yozuvchisi: navbat + dedup + Sotuv/Yangi.
        # (Oldin bu yer create_lead(note=..., extra_fields=...) chaqirardi —
        # u argumentlarni qabul qilmagani uchun har safar TypeError bo'lardi.)
        try:
            from src.database_pool import db_pool
            from src.services.core.leads.hunter import Candidate, HunterWriter

            result = await HunterWriter(self.amocrm, db_pool).submit(
                Candidate(
                    source=kwargs.get("source", "telegram_dm"),
                    name=name,
                    phone=phone,
                    external_id=f"tg:{user_id}" if user_id else None,
                    note=kwargs.get("note") or "",
                )
            )
            logger.info(
                f"[CRM_SERVICE] Lead {result.state} for {name} (lead_id={result.lead_id})"
            )
            out = {"success": result.ok, "lead_id": result.lead_id, "state": result.state}
            if result.error:
                out["error"] = result.error
            return out
        except Exception as e:
            logger.error(f"[CRM_SERVICE ERROR] {e}")
            return {"success": False, "error": str(e)}

    async def get_user_context(self, phone: str) -> str:
        """User haqida AmoCRM'dan kontekst olish."""
        try:
            lead = self.amocrm.get_lead_by_phone(phone)
            return self.amocrm.get_lead_status_text(lead)
        except Exception as e:
            logger.error(f"[CRM_SERVICE CONTEXT ERROR] {e}")
            return "Yangi mijoz (kontekst olinmadi)"

    def get_all_tasks(self):
        """Barcha ochiq vazifalarni olish."""
        amo_tasks = self.amocrm.get_tasks()
        airtable_tasks = (
            self.airtable.get_projects()
        )  # Airtable-da loyihalar vazifa sifatida
        return {"amocrm": amo_tasks, "airtable": airtable_tasks}
