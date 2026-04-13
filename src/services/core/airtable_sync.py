import requests
import logging
import os
from datetime import datetime

logger = logging.getLogger(__name__)

class AirtableSync:
    # Field name mapping: code key -> actual Airtable field names (in order of priority)
    FIELD_MAP = {
        "stage": ["Loyiha bosqichi", "Stage", "Status", "Holati"],
        "project_name": ["Loyihani nomi?", "Project Name", "Name"],
        "deadline": ["END sana", "Deadline", "Muddati"],
        "start_date": ["Start sana", "Created", "Start Date"],
        "budget": ["Jami loyiha narxi (UZS)", "Budget"],
        "budget_usd": ["Jami loyiha narxi (USD)"],
        "manager": ["PM", "Manager"],
        "payment_status": ["To'lov statusi", "To'lovlar holati"],
        "paid_usd": ["Jami to'langan USD"],
        "remaining_usd": ["Qoldiq to'lov $"],
    }

    DONE_STAGES = ["Yakunlangan", "Done", "Completed", "Topshirildi", "Arxiv",
                   "Fayllarni yetkazib berish va topshirish"]

    @staticmethod
    def _get_field(fields: dict, key: str, default=None):
        """Get field value by trying multiple possible field names."""
        for name in AirtableSync.FIELD_MAP.get(key, [key]):
            val = fields.get(name)
            if val is not None:
                return val
        return default

    def __init__(self, api_key=None, base_id=None, table_name="Loyihalar"):
        from src.settings import settings
        self.api_key = api_key or settings.AIRTABLE_API_KEY.get_secret_value()
        self.base_id = base_id or settings.AIRTABLE_BASE_ID
        self.table_name = table_name
        self.endpoint = f"https://api.airtable.com/v0/{self.base_id}/{self.table_name}"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    def get_projects(self):
        """Airtable-dan loyihalarni olish."""
        if not self.api_key or not self.base_id:
            logger.error("[AIRTABLE] API key yoki Base ID yetishmayapti.")
            return []

        try:
            response = requests.get(self.endpoint, headers=self.headers)
            if response.status_code == 200:
                data = response.json()
                return data.get("records", [])
            elif response.status_code == 403:
                logger.error(f"[AIRTABLE 403] Ruxsat xatosi! Tokeningizda 'data.records:read' ruxsati bormi? Yoki '{self.table_name}' jadvali mavjud emas.")
                return []
            else:
                logger.error(f"[AIRTABLE ERROR] {response.status_code}: {response.text}")
                return []
        except Exception as e:
            logger.error(f"[AIRTABLE EXCEPTION] {e}")
            return []

    def get_overdue_projects(self):
        """Muddati o'tgan loyihalarni topish."""
        projects = self.get_projects()
        overdue = []
        now = datetime.now()

        for p in projects:
            fields = p.get("fields", {})
            deadline_str = self._get_field(fields, "deadline")
            stage = self._get_field(fields, "stage") or ""

            if deadline_str and stage not in self.DONE_STAGES:
                try:
                    deadline = datetime.strptime(deadline_str, "%Y-%m-%d")
                    if deadline < now:
                        overdue.append(p)
                except Exception:
                    continue
        return overdue

    def get_projects_by_stage(self, stage_name: str):
        """Ma'lum bir bosqichdagi loyihalarni olish."""
        projects = self.get_projects()
        return [p for p in projects if self._get_field(p.get("fields", {}), "stage") == stage_name]

    def get_finance_records(self):
        """Kirim va Chiqim jadvallaridan barcha tranzaksiyalarni olish."""
        records = []
        for table_name, record_type in [("Kirim", "income"), ("Chiqim", "expense")]:
            original_table = self.table_name
            self.table_name = table_name
            self.endpoint = f"https://api.airtable.com/v0/{self.base_id}/{self.table_name}"
            try:
                table_records = self.get_projects()
                for r in table_records:
                    r["_record_type"] = record_type
                records.extend(table_records)
            finally:
                self.table_name = original_table
                self.endpoint = f"https://api.airtable.com/v0/{self.base_id}/{self.table_name}"
        return records

    def update_project_fields(self, record_id: str, fields: dict):
        """Loyihaning bir nechta maydonlarini yangilash."""
        url = f"{self.endpoint}/{record_id}"
        data = {"fields": fields}
        try:
            response = requests.patch(url, headers=self.headers, json=data)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"[AIRTABLE UPDATE ERROR] {e}")
            return False

    def update_project_stage(self, record_id, next_stage):
        """Loyihaning bosqichini yangilash (Record ID orqali)."""
        return self.update_project_fields(record_id, {"Loyiha bosqichi": next_stage})

    def update_project_stage_by_name(self, project_name: str, next_stage: str):
        """Loyihaning bosqichini nomi orqali topib yangilash."""
        projects = self.get_projects()
        for p in projects:
            fields = p.get("fields", {})
            if self._get_field(fields, "project_name") == project_name:
                return self.update_project_stage(p.get("id"), next_stage)
        
        logger.warning(f"[AIRTABLE] Loyiha topilmadi: {project_name}")
        return False

    def get_upcoming_deadlines(self, hours=72):
        """Yaqin 72 soat ichida muddati tugaydigan loyihalarni topish."""
        projects = self.get_projects()
        upcoming = []
        from datetime import timedelta
        now = datetime.now()
        limit = now + timedelta(hours=hours)

        for p in projects:
            fields = p.get("fields", {})
            deadline_str = self._get_field(fields, "deadline")
            stage = self._get_field(fields, "stage") or ""

            if deadline_str and stage not in self.DONE_STAGES:
                try:
                    deadline = datetime.strptime(deadline_str, "%Y-%m-%d")
                    if now < deadline <= limit:
                        upcoming.append(p)
                except Exception:
                    continue
        return upcoming

    def create_record(self, fields: dict):
        """Airtable-da yangi yozuv (Project/Task) yaratish."""
        try:
            response = requests.post(self.endpoint, headers=self.headers, json={"fields": fields})
            if response.status_code in [200, 201]:
                logger.info(f"[AIRTABLE OK] Yangi yozuv yaratildi: {fields.get('Project Name') or fields.get('Name') or 'Unknown'}")
                return response.json()
            else:
                logger.error(f"[AIRTABLE ERROR] {response.status_code}: {response.text}")
                return None
        except Exception as e:
            logger.error(f"[AIRTABLE EXCEPTION] {e}")
            return None

    def log_lead_acquisition(self, name: str, phone: str, source: str, intent: str = "WARM"):
        """Lid topilganini tarixiy audit uchun Airtable'ga yozish."""
        # Agar 'Leads' jadvali bo'lmasa, 'Loyihalar' jadvaliga yozishi mumkin (yoki xato beradi)
        # Biz buni xavfsiz holda 'Leads' jadvaliga yo'naltiramiz
        original_table = self.table_name
        self.table_name = "Leads" # Enterprise standard
        self.endpoint = f"https://api.airtable.com/v0/{self.base_id}/{self.table_name}"
        
        fields = {
            "Name": name,
            "Phone": phone,
            "Source": source,
            "Intent": intent,
            "Date": datetime.now().strftime("%Y-%m-%d %H:%M")
        }
        
        try:
            return self.create_record(fields)
        finally:
            self.table_name = original_table
            self.endpoint = f"https://api.airtable.com/v0/{self.base_id}/{self.table_name}"

    def verify_qc_standards(self, record_id: str) -> bool:
        """Loyihaning Sifat Nazorati (QC) talablariga javob berishini tekshirish."""
        # Hozircha oddiy placeholder, kelajakda AI orqali tekshirishga o'tkaziladi
        # Masalan: Barcha kerakli fayllar havolasi bormi? Stage to'g'rimi?
        logger.info(f"[QC] Checking project: {record_id}")
        return True

if __name__ == "__main__":
    # Test
    sync = AirtableSync()
    projects = sync.get_projects()
    print(f"Found {len(projects)} projects.")
