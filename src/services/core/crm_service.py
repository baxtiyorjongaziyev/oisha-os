import logging
from src.services.core.amocrm_sync import AmoCRMSync
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
        try:
            note = kwargs.get("note")
            lead_id = None

            if hasattr(self.amocrm, "create_lead"):
                lead_id = await self.amocrm.create_lead(
                    name=name,
                    phone=phone,
                    note=note,
                    price=kwargs.get("price", 0),
                    extra_fields=kwargs.get("extra_fields"),
                )
            elif hasattr(self.amocrm, "ensure_lead"):
                lead_id = await self.amocrm.ensure_lead(
                    name=name, phone=phone, note=note
                )
            else:
                raise AttributeError(
                    "AmoCRM client does not expose a supported lead creation method"
                )

            # 2. Airtable-da qayd etish (ixtiyoriy)
            # self.airtable.add_record(...)
            logger.info(f"[CRM_SERVICE] Lead synced for {name} (lead_id={lead_id})")
            return {"success": bool(lead_id), "lead_id": lead_id}
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
