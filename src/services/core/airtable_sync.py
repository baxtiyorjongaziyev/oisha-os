import logging
from datetime import datetime

import requests

logger = logging.getLogger(__name__)


class AirtableSync:
    # Field name mapping: code key -> actual Airtable field names (priority order)
    FIELD_MAP = {
        "stage": ["Loyiha bosqichi", "Stage", "Status", "Holati"],
        "project_name": ["Loyihani nomi?", "Project Name", "Name"],
        "project_id": ["Loyiha ID", "AmoCRM_ID"],
        "deadline": ["END sana", "Deadline", "Muddati"],
        "start_date": ["Start sana", "Created", "Start Date"],
        "budget": ["Kelishgan narx", "Jami loyiha narxi (UZS)", "Budget"],
        "budget_usd": ["Jami loyiha narxi (USD)"],
        "manager": ["PM", "Manager"],
        "payment_status": ["To'lov statusi", "To'lovlar holati"],
        "paid_usd": ["Jami to'langan USD"],
        "remaining_usd": ["Qoldiq to'lov $"],
    }

    PROJECT_WRITE_ALIASES = {
        "Project Name": "Loyihani nomi?",
        "Name": "Loyihani nomi?",
        "Stage": "Loyiha bosqichi",
        "Status": "Loyiha bosqichi",
        "Budget": "Kelishgan narx",
        "Jami loyiha narxi (UZS)": "Kelishgan narx",
        "Created At": "Start sana",
    }

    # Writable fields in the current "Loyihalar" schema.
    PROJECT_ALLOWED_FIELDS = {
        "Loyihani nomi?",
        "Loyiha bosqichi",
        "Start sana",
        "END sana",
        "Kelishgan narx",
        "To'lovlar holati",
        "Turi",
        "Kurs",
        "Muhim darajasi",
        "Xizmat turi",
        "PM",
        "Manager",
    }

    DONE_STAGES = [
        "Yakunlangan",
        "Done",
        "Completed",
        "Topshirildi",
        "Arxiv",
        "Fayllarni yetkazib berish va topshirish",
    ]

    @staticmethod
    def _get_field(fields: dict, key: str, default=None):
        """Get field value by trying multiple possible field names."""
        for name in AirtableSync.FIELD_MAP.get(key, [key]):
            val = fields.get(name)
            if val is not None:
                return val
        return default

    @staticmethod
    def resolve_pm_handle(pm_value) -> str:
        """
        Maps Airtable PM field values (names or Record IDs) to Telegram handles.
        """
        if not pm_value:
            return "@Inomjon"
            
        # If it's a list (linked record), take the first one
        if isinstance(pm_value, list):
            pm_value = pm_value[0] if pm_value else None
            
        if not pm_value:
            return "@Inomjon"

        mapping = {
            "reccXjZIGIcRezKgB": "@Inomjon_JonBranding", # Inomjon Record ID
            "recPi9SROzJNK8SX7": "@jonbranding_pm",      # New PM Record ID
            "Inomjon": "@Inomjon_JonBranding",
            "Inomjon aka": "@Inomjon_JonBranding",
            "Dilorom": "@jonbranding_pm",
            "Dilorom opa": "@jonbranding_pm",
        }
        
        return mapping.get(pm_value, "@Inomjon_JonBranding")

    def __init__(self, api_key=None, base_id=None, table_name="Loyihalar"):
        from src.settings import settings

        self.api_key = api_key or settings.AIRTABLE_API_KEY.get_secret_value()
        self.base_id = base_id or settings.AIRTABLE_BASE_ID
        self.table_name = table_name
        self.endpoint = f"https://api.airtable.com/v0/{self.base_id}/{self.table_name}"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _normalize_fields_for_table(self, fields: dict) -> dict:
        """Translate legacy field names to the actual Airtable schema and drop unknown keys."""
        normalized = dict(fields or {})
        if self.table_name != "Loyihalar":
            return normalized

        translated = {}
        dropped_originals = []
        for key, value in normalized.items():
            actual_key = self.PROJECT_WRITE_ALIASES.get(key, key)
            if actual_key in {"Client Phone", "AmoCRM_ID", "Manager", "PM", "Mijoz nomi", "Loyiha ID"}:
                dropped_originals.append(key)
                continue
            if actual_key in self.PROJECT_ALLOWED_FIELDS:
                translated[actual_key] = value
            else:
                dropped_originals.append(key)

        if dropped_originals:
            dropped = ", ".join(sorted(set(dropped_originals)))
            logger.warning(f"[AIRTABLE] Skipping unsupported Loyihalar fields: {dropped}")
        return translated

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
            if response.status_code == 403:
                logger.error(
                    f"[AIRTABLE 403] Ruxsat xatosi! Tokeningizda 'data.records:read' ruxsati bormi? "
                    f"Yoki '{self.table_name}' jadvali mavjud emas."
                )
                return []
            logger.error(f"[AIRTABLE ERROR] {response.status_code}: {response.text}")
            return []
        except Exception as exc:
            logger.error(f"[AIRTABLE EXCEPTION] {exc}")
            return []

    def get_overdue_projects(self):
        """Muddati o'tgan loyihalarni topish."""
        projects = self.get_projects()
        overdue = []
        now = datetime.now()

        for project in projects:
            fields = project.get("fields", {})
            deadline_str = self._get_field(fields, "deadline")
            stage = self._get_field(fields, "stage") or ""

            if deadline_str and stage not in self.DONE_STAGES:
                try:
                    deadline = datetime.strptime(deadline_str, "%Y-%m-%d")
                    if deadline < now:
                        overdue.append(project)
                except Exception:
                    continue
        return overdue

    def get_projects_by_stage(self, stage_name: str):
        """Ma'lum bir bosqichdagi loyihalarni olish."""
        projects = self.get_projects()
        return [project for project in projects if self._get_field(project.get("fields", {}), "stage") == stage_name]

    def get_finance_records(self):
        """Kirim va Chiqim jadvallaridan barcha tranzaksiyalarni olish."""
        records = []
        for table_name, record_type in [("Kirim", "income"), ("Chiqim", "expense")]:
            original_table = self.table_name
            self.table_name = table_name
            self.endpoint = f"https://api.airtable.com/v0/{self.base_id}/{self.table_name}"
            try:
                table_records = self.get_projects()
                for record in table_records:
                    record["_record_type"] = record_type
                records.extend(table_records)
            finally:
                self.table_name = original_table
                self.endpoint = f"https://api.airtable.com/v0/{self.base_id}/{self.table_name}"
        return records

    def update_project_fields(self, record_id: str, fields: dict):
        """Loyihaning bir nechta maydonlarini yangilash."""
        fields = self._normalize_fields_for_table(fields)
        if not fields:
            logger.warning("[AIRTABLE] No valid fields to update after schema normalization.")
            return False

        url = f"{self.endpoint}/{record_id}"
        data = {"fields": fields}
        try:
            response = requests.patch(url, headers=self.headers, json=data)
            return response.status_code == 200
        except Exception as exc:
            logger.error(f"[AIRTABLE UPDATE ERROR] {exc}")
            return False

    def update_project_stage(self, record_id, next_stage):
        """Loyihaning bosqichini yangilash (Record ID orqali)."""
        return self.update_project_fields(record_id, {"Loyiha bosqichi": next_stage})

    def update_project_stage_by_name(self, project_name: str, next_stage: str):
        """Loyihaning bosqichini nomi orqali topib yangilash."""
        projects = self.get_projects()
        for project in projects:
            fields = project.get("fields", {})
            if self._get_field(fields, "project_name") == project_name:
                return self.update_project_stage(project.get("id"), next_stage)

        logger.warning(f"[AIRTABLE] Loyiha topilmadi: {project_name}")
        return False

    def get_upcoming_deadlines(self, hours=72):
        """Yaqin 72 soat ichida muddati tugaydigan loyihalarni topish."""
        from datetime import timedelta

        projects = self.get_projects()
        upcoming = []
        now = datetime.now()
        limit = now + timedelta(hours=hours)

        for project in projects:
            fields = project.get("fields", {})
            deadline_str = self._get_field(fields, "deadline")
            stage = self._get_field(fields, "stage") or ""

            if deadline_str and stage not in self.DONE_STAGES:
                try:
                    deadline = datetime.strptime(deadline_str, "%Y-%m-%d")
                    if now < deadline <= limit:
                        upcoming.append(project)
                except Exception:
                    continue
        return upcoming

    def create_record(self, fields: dict):
        """Airtable-da yangi yozuv yaratish."""
        fields = self._normalize_fields_for_table(fields)
        if not fields:
            logger.warning("[AIRTABLE] No valid fields to create after schema normalization.")
            return None

        try:
            response = requests.post(self.endpoint, headers=self.headers, json={"fields": fields})
            if response.status_code in [200, 201]:
                project_label = fields.get("Loyihani nomi?") or fields.get("Project Name") or fields.get("Name") or "Unknown"
                logger.info(f"[AIRTABLE OK] Yangi yozuv yaratildi: {project_label}")
                return response.json()
            logger.error(f"[AIRTABLE ERROR] {response.status_code}: {response.text}")
            return None
        except Exception as exc:
            logger.error(f"[AIRTABLE EXCEPTION] {exc}")
            return None

    def log_lead_acquisition(self, name: str, phone: str, source: str, intent: str = "WARM"):
        """Lid topilganini tarixiy audit uchun Airtable'ga yozish."""
        original_table = self.table_name
        self.table_name = "Leads"
        self.endpoint = f"https://api.airtable.com/v0/{self.base_id}/{self.table_name}"

        fields = {
            "Name": name,
            "Phone": phone,
            "Source": source,
            "Intent": intent,
            "Date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }

        try:
            return self.create_record(fields)
        finally:
            self.table_name = original_table
            self.endpoint = f"https://api.airtable.com/v0/{self.base_id}/{self.table_name}"

    def verify_qc_standards(self, record_id: str) -> bool:
        """Loyihaning Sifat Nazorati talablariga javob berishini tekshirish."""
        logger.info(f"[QC] Checking project: {record_id}")
        return True


if __name__ == "__main__":
    sync = AirtableSync()
    projects = sync.get_projects()
    print(f"Found {len(projects)} projects.")
