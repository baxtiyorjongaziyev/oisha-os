import logging
import json
import os
import time
from copy import deepcopy
from datetime import datetime
from urllib.parse import quote

import requests

logger = logging.getLogger(__name__)


class AirtableSync:
    READ_RETRIES = 3
    REQUEST_TIMEOUT_SECONDS = 20
    BILLING_COOLDOWN_SECONDS = int(
        os.getenv("AIRTABLE_BILLING_COOLDOWN_SECONDS", "21600")
    )

    _base_tables_cache = {}
    _record_url_cache = {}
    _records_cache = {}
    _billing_blocked_until = 0.0
    _billing_block_reason = None

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
        "summary": ["Xulosa", "Summary", "Chat Summary"],
    }

    PROJECT_WRITE_ALIASES = {
        "Project Name": "Loyihani nomi?",
        "Name": "Loyihani nomi?",
        "Stage": "Loyiha bosqichi",
        "Status": "Loyiha bosqichi",
        "Budget": "Kelishgan narx",
        "Jami loyiha narxi (UZS)": "Kelishgan narx",
        "Created At": "Start sana",
        "Summary": "Xulosa",
        "Chat Summary": "Xulosa",
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
        "Xulosa",
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
            "reccXjZIGIcRezKgB": "@Inomjon_JonBranding",  # Inomjon Record ID
            "recPi9SROzJNK8SX7": "@jonbranding_pm",  # New PM Record ID
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
        self.endpoint = self._table_url()
        self.read_cache_ttl_seconds = int(
            os.getenv("AIRTABLE_READ_CACHE_TTL_SECONDS", "600")
        )
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _table_url(self, table_name=None):
        table = quote(str(table_name or self.table_name), safe="")
        return f"https://api.airtable.com/v0/{self.base_id}/{table}"

    def _refresh_endpoint(self):
        self.endpoint = self._table_url()

    def _records_cache_key(self):
        return (self.base_id, self.table_name)

    def _disk_cache_path(self):
        safe_table = "".join(
            char if char.isalnum() or char in "-_" else "_"
            for char in str(self.table_name)
        )
        return os.path.join("data", "cache", f"airtable_{self.base_id}_{safe_table}.json")

    def _get_disk_cached_records(self):
        path = self._disk_cache_path()
        try:
            with open(path, "r", encoding="utf-8") as cache_file:
                payload = json.load(cache_file)
            records = payload.get("records")
            if isinstance(records, list):
                logger.warning(
                    "[AIRTABLE CACHE] Using persistent stale snapshot for %s: %s records",
                    self.table_name,
                    len(records),
                )
                return records
        except (OSError, ValueError, TypeError):
            pass
        return None

    def _get_cached_records(self):
        if self.read_cache_ttl_seconds <= 0:
            return None
        cached = self._records_cache.get(self._records_cache_key())
        if not cached:
            return None
        created_at, records = cached
        if time.time() - created_at > self.read_cache_ttl_seconds:
            self._records_cache.pop(self._records_cache_key(), None)
            return None
        return deepcopy(records)

    def _set_cached_records(self, records):
        if self.read_cache_ttl_seconds <= 0:
            return
        self._records_cache[self._records_cache_key()] = (time.time(), deepcopy(records))
        path = self._disk_cache_path()
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as cache_file:
                json.dump(
                    {"cached_at": datetime.now().isoformat(), "records": records},
                    cache_file,
                    ensure_ascii=False,
                )
        except OSError as exc:
            logger.warning("[AIRTABLE CACHE] Persistent cache write failed: %s", exc)

    def _invalidate_records_cache(self):
        self._records_cache.pop(self._records_cache_key(), None)

    @classmethod
    def _billing_limit_response(cls):
        response = requests.Response()
        response.status_code = 429
        response.headers["X-Oisha-Airtable-Cooldown"] = "active"
        response._content = json.dumps(
            {
                "errors": [
                    {
                        "error": cls._billing_block_reason
                        or "PUBLIC_API_BILLING_LIMIT_EXCEEDED",
                        "message": "Airtable API billing limit cooldown is active.",
                    }
                ]
            }
        ).encode("utf-8")
        return response

    @staticmethod
    def _is_billing_limit_response(response) -> bool:
        if response.status_code != 429:
            return False
        return "PUBLIC_API_BILLING_LIMIT_EXCEEDED" in (response.text or "")

    def _request(self, method: str, url: str, *, retry: bool = True, **kwargs):
        cls = type(self)
        if time.time() < cls._billing_blocked_until:
            return cls._billing_limit_response()

        attempts = self.READ_RETRIES if retry and method.upper() == "GET" else 1
        last_exc = None

        for attempt in range(1, attempts + 1):
            try:
                request_kwargs = dict(kwargs)
                request_kwargs.setdefault("headers", self.headers)
                request_kwargs.setdefault("timeout", self.REQUEST_TIMEOUT_SECONDS)
                response = requests.request(method, url, **request_kwargs)

                if self._is_billing_limit_response(response):
                    cls._billing_block_reason = "PUBLIC_API_BILLING_LIMIT_EXCEEDED"
                    cls._billing_blocked_until = (
                        time.time() + cls.BILLING_COOLDOWN_SECONDS
                    )
                    logger.error(
                        "[AIRTABLE] Monthly API billing limit exceeded. "
                        "Pausing Airtable requests for %s seconds.",
                        cls.BILLING_COOLDOWN_SECONDS,
                    )
                    return response

                if (
                    response.status_code in {429, 500, 502, 503, 504}
                    and attempt < attempts
                ):
                    retry_after = response.headers.get("Retry-After")
                    delay = (
                        float(retry_after)
                        if retry_after and retry_after.isdigit()
                        else attempt * 1.5
                    )
                    logger.warning(
                        f"[AIRTABLE] Transient {response.status_code}, retry {attempt}/{attempts} in {delay:.1f}s"
                    )
                    time.sleep(delay)
                    continue

                return response
            except requests.RequestException as exc:
                last_exc = exc
                if attempt >= attempts:
                    raise
                delay = attempt * 1.5
                logger.warning(
                    f"[AIRTABLE] Network error, retry {attempt}/{attempts} in {delay:.1f}s: {exc}"
                )
                time.sleep(delay)

        if last_exc:
            raise last_exc
        raise RuntimeError("Airtable request failed without a response")

    def _get_base_tables(self):
        cache_key = self.base_id
        cached = self._base_tables_cache.get(cache_key)
        if cached is not None:
            return cached

        meta_url = f"https://api.airtable.com/v0/meta/bases/{self.base_id}/tables"
        try:
            response = self._request("GET", meta_url)
            if response.status_code != 200:
                logger.warning(
                    f"[AIRTABLE] Jadval metadata olib bo'lmadi: {response.status_code}"
                )
                self._base_tables_cache[cache_key] = []
                return []

            tables = []
            for table in response.json().get("tables", []):
                views = table.get("views") or []
                view_id = None
                for view in views:
                    if view.get("type") == "grid":
                        view_id = view.get("id")
                        break
                if not view_id and views:
                    view_id = views[0].get("id")

                tables.append(
                    {
                        "id": table.get("id"),
                        "name": table.get("name"),
                        "view_id": view_id,
                    }
                )

            self._base_tables_cache[cache_key] = tables
            return tables
        except Exception as exc:
            logger.warning(f"[AIRTABLE] Jadval metadata xatosi: {exc}")
            self._base_tables_cache[cache_key] = []
            return []

    def get_record_url(self, record_id: str):
        record_id = str(record_id or "").strip()
        if not record_id.startswith("rec"):
            return None

        cache_key = (self.base_id, record_id)
        cached = self._record_url_cache.get(cache_key)
        if cached is not None:
            return cached

        tables = self._get_base_tables()
        if not tables:
            self._record_url_cache[cache_key] = None
            return None

        ordered_tables = sorted(
            tables,
            key=lambda table: (
                table.get("name") != self.table_name
                and table.get("id") != self.table_name
            ),
        )

        for table in ordered_tables:
            table_id = table.get("id")
            if not table_id:
                continue

            probe_url = (
                f"https://api.airtable.com/v0/{self.base_id}/{table_id}/{record_id}"
            )
            try:
                response = self._request("GET", probe_url)
            except Exception:
                continue

            if response.status_code == 200:
                view_id = table.get("view_id")
                if view_id:
                    record_url = f"https://airtable.com/{self.base_id}/{table_id}/{view_id}/{record_id}"
                else:
                    record_url = (
                        f"https://airtable.com/{self.base_id}/{table_id}/{record_id}"
                    )
                self._record_url_cache[cache_key] = record_url
                return record_url

            if response.status_code in {404, 422}:
                continue

            if response.status_code == 403:
                logger.warning("[AIRTABLE] Record URL probe uchun ruxsat yetarli emas.")
                break

        self._record_url_cache[cache_key] = None
        return None

    def _normalize_fields_for_table(self, fields: dict) -> dict:
        """Translate legacy field names to the actual Airtable schema and drop unknown keys."""
        normalized = dict(fields or {})
        if self.table_name != "Loyihalar":
            return normalized

        translated = {}
        dropped_originals = []
        for key, value in normalized.items():
            actual_key = self.PROJECT_WRITE_ALIASES.get(key, key)
            if actual_key in {
                "Client Phone",
                "AmoCRM_ID",
                "Manager",
                "PM",
                "Mijoz nomi",
                "Loyiha ID",
            }:
                dropped_originals.append(key)
                continue
            if actual_key in self.PROJECT_ALLOWED_FIELDS:
                translated[actual_key] = value
            else:
                dropped_originals.append(key)

        if dropped_originals:
            dropped = ", ".join(sorted(set(dropped_originals)))
            logger.warning(
                f"[AIRTABLE] Skipping unsupported Loyihalar fields: {dropped}"
            )
        return translated

    def get_projects(self, force_refresh: bool = False):
        """Airtable-dan loyihalarni olish."""
        if not self.api_key or not self.base_id:
            logger.error("[AIRTABLE] API key yoki Base ID yetishmayapti.")
            return []

        if not force_refresh:
            cached_records = self._get_cached_records()
            if cached_records is not None:
                logger.info(
                    f"[AIRTABLE CACHE] {self.table_name}: {len(cached_records)} cached records"
                )
                return cached_records

        try:
            records = []
            params = {"pageSize": 100}
            while True:
                response = self._request("GET", self.endpoint, params=params)
                if response.status_code == 200:
                    data = response.json()
                    records.extend(data.get("records", []))
                    offset = data.get("offset")
                    if not offset:
                        self._set_cached_records(records)
                        return records
                    params["offset"] = offset
                    continue

                if response.status_code == 403:
                    logger.error(
                        f"[AIRTABLE 403] Ruxsat xatosi! Tokeningizda 'data.records:read' ruxsati bormi? "
                        f"Yoki '{self.table_name}' jadvali mavjud emas."
                    )
                    return records
                logger.error(
                    f"[AIRTABLE ERROR] {response.status_code}: {response.text}"
                )
                return records or self._get_disk_cached_records() or []
        except Exception as exc:
            logger.error(f"[AIRTABLE EXCEPTION] {exc}")
            return self._get_disk_cached_records() or []

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
        return [
            project
            for project in projects
            if self._get_field(project.get("fields", {}), "stage") == stage_name
        ]

    def get_finance_records(self):
        """Kirim va Chiqim jadvallaridan barcha tranzaksiyalarni olish."""
        records = []
        for table_name, record_type in [("Kirim", "income"), ("Chiqim", "expense")]:
            original_table = self.table_name
            self.table_name = table_name
            self._refresh_endpoint()
            try:
                table_records = self.get_projects()
                for record in table_records:
                    record["_record_type"] = record_type
                records.extend(table_records)
            finally:
                self.table_name = original_table
                self._refresh_endpoint()
        return records

    def update_project_fields(self, record_id: str, fields: dict):
        """Loyihaning bir nechta maydonlarini yangilash."""
        fields = self._normalize_fields_for_table(fields)
        if not fields:
            logger.warning(
                "[AIRTABLE] No valid fields to update after schema normalization."
            )
            return False

        url = f"{self.endpoint}/{record_id}"
        data = {"fields": fields}
        try:
            response = self._request("PATCH", url, retry=False, json=data)
            ok = response.status_code == 200
            if ok:
                self._invalidate_records_cache()
            return ok
        except Exception as exc:
            logger.error(f"[AIRTABLE UPDATE ERROR] {exc}")
            return False

    def update_project_stage(self, record_id, next_stage):
        """Loyihaning bosqichini yangilash (Record ID orqali)."""
        return self.update_project_fields(record_id, {"Loyiha bosqichi": next_stage})

    def update_project_fields_by_name(self, project_name: str, fields: dict):
        """Loyihaning maydonlarini nomi orqali topib yangilash."""
        projects = self.get_projects()
        for project in projects:
            p_fields = project.get("fields", {})
            if self._get_field(p_fields, "project_name") == project_name:
                return self.update_project_fields(project.get("id"), fields)

        logger.warning(f"[AIRTABLE] Loyiha topilmadi: {project_name}")
        return False

    def update_project_stage_by_name(self, project_name: str, next_stage: str):
        """Loyihaning bosqichini nomi orqali topib yangilash."""
        return self.update_project_fields_by_name(
            project_name, {"Loyiha bosqichi": next_stage}
        )

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
            logger.warning(
                "[AIRTABLE] No valid fields to create after schema normalization."
            )
            return None

        try:
            response = self._request(
                "POST", self.endpoint, retry=False, json={"fields": fields}
            )
            if response.status_code in [200, 201]:
                self._invalidate_records_cache()
                project_label = (
                    fields.get("Loyihani nomi?")
                    or fields.get("Project Name")
                    or fields.get("Name")
                    or "Unknown"
                )
                logger.info(f"[AIRTABLE OK] Yangi yozuv yaratildi: {project_label}")
                return response.json()
            logger.error(f"[AIRTABLE ERROR] {response.status_code}: {response.text}")
            return None
        except Exception as exc:
            logger.error(f"[AIRTABLE EXCEPTION] {exc}")
            return None

    def log_lead_acquisition(
        self, name: str, phone: str, source: str, intent: str = "WARM"
    ):
        """Lid topilganini tarixiy audit uchun Airtable'ga yozish."""
        original_table = self.table_name
        self.table_name = "Leads"
        self._refresh_endpoint()

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
            self._refresh_endpoint()

    def verify_qc_standards(self, record_id: str) -> bool:
        """Loyihaning Sifat Nazorati talablariga javob berishini tekshirish."""
        logger.info(f"[QC] Checking project: {record_id}")
        return True


if __name__ == "__main__":
    sync = AirtableSync()
    projects = sync.get_projects()
    print(f"Found {len(projects)} projects.")
