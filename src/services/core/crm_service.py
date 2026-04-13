
import logging
from src.services.amocrm_sync import AmoCRMSync
from src.services.airtable_sync import AirtableSync
import src.config as config

logger = logging.getLogger(__name__)

class CRMService:
    """AmoCRM va Airtable integratsiyasini birlashtirgan xizmat."""
    
    def __init__(self):
        self.amocrm = AmoCRMSync(
            config.AMOCRM_SUBDOMAIN,
            config.AMOCRM_CLIENT_ID,
            config.AMOCRM_CLIENT_SECRET,
            config.AMOCRM_REDIRECT_URL
        )
        self.airtable = AirtableSync() # Config ichidan o'zi oladi

    async def sync_lead(self, user_id: int, name: str, phone: str, **kwargs):
        """Leadni AmoCRM va Airtable-da sinxronizatsiya qilish."""
        try:
            # 1. AmoCRM lead yaratish
            self.amocrm.create_lead(name, phone, **kwargs)
            # 2. Airtable-da qayd etish (ixtiyoriy)
            # self.airtable.add_record(...)
            logger.info(f"[CRM_SERVICE] Lead synced for {name}")
        except Exception as e:
            logger.error(f"[CRM_SERVICE ERROR] {e}")

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
        airtable_tasks = self.airtable.get_projects() # Airtable-da loyihalar vazifa sifatida
        return {"amocrm": amo_tasks, "airtable": airtable_tasks}
