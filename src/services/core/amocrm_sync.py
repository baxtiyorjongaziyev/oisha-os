import os
import time
import json
import logging
import requests  # type: ignore
from typing import Optional, Dict, Any, List
from functools import wraps

logger = logging.getLogger(__name__)


def retry_with_backoff(max_retries=3, initial_delay=1, backoff_factor=2, exceptions=(requests.RequestException,)):
    """Decorator to retry API calls with exponential backoff."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            delay = initial_delay
            last_exception = None
            
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    logger.warning(f"[AMOCRM RETRY] {func.__name__} attempt {attempt + 1}/{max_retries} failed: {e}")
                    if attempt < max_retries - 1:
                        time.sleep(delay)
                        delay *= backoff_factor
            
            logger.error(f"[AMOCRM RETRY] {func.__name__} failed after {max_retries} attempts: {last_exception}")
            raise last_exception
        return wrapper
    return decorator

class AmoCRMSync:
    def __init__(self, subdomain, client_id, client_secret, redirect_url, token_file="data/amocrm_token.json"):
        self.subdomain = subdomain
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_url = redirect_url
        self.token_file = token_file
        self.base_url = f"https://{subdomain}.amocrm.ru"
        self.access_token: Optional[str] = None
        self.token_data: Dict[str, Any] = {}
        self.last_error: Optional[str] = None
        
        # Security: Masked log for safety
        logger.info(f"[AMOCRM INIT] Subdomain: {subdomain}")

    def _load_token(self):
        """Tokenni fayldan o'qish."""
        env_token_json = os.environ.get("AMOCRM_TOKEN_JSON")
        if env_token_json:
            try:
                data = json.loads(env_token_json)
                if isinstance(data, dict):
                    self.token_data = data
                    self.access_token = str(data.get("access_token", "")) if data.get("access_token") else None
                    return
            except Exception as e:
                self.last_error = "token_env_parse_failed"
                logger.error(f"[AMOCRM] Env token parse xatosi: {type(e).__name__}")

        if os.path.exists(self.token_file):
            for encoding in ("utf-8-sig", "utf-16"):
                try:
                    with open(self.token_file, "r", encoding=encoding) as f:
                        data = json.load(f)
                    if isinstance(data, dict):
                        self.token_data = data
                        self.access_token = str(data.get("access_token", "")) if data.get("access_token") else None
                        return
                except UnicodeError:
                    continue
                except Exception as e:
                    self.last_error = "token_file_load_failed"
                    logger.error(f"[AMOCRM] Token yuklashda xato: {type(e).__name__}")
                    return

    def _save_token(self, token_data):
        """Tokenni faylga saqlash."""
        try:
            with open(self.token_file, "w") as f:
                json.dump(token_data, f)
            self.token_data = token_data
            self.access_token = token_data.get("access_token")
        except Exception as e:
            logger.error(f"[AMOCRM] Token saqlashda xato: {e}")

    def refresh_token(self):
        """Refresh token yordamida yangi access token olish."""
        if not self.token_data.get("refresh_token"):
            self.last_error = "refresh_token_missing"
            logger.error("[AMOCRM] Refresh token topilmadi.")
            return False

        url = f"{self.base_url}/oauth2/access_token"
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "grant_type": "refresh_token",
            "refresh_token": self.token_data.get("refresh_token", ""),
            "redirect_uri": self.redirect_url,
        }

        try:
            response = requests.post(url, json=data, timeout=30)
            if response.status_code == 400:
                response = requests.post(url, data=data, timeout=30)

            if response.status_code == 200:
                self._save_token(response.json())
                self.last_error = None
                logger.info("[AMOCRM OK] Access token refreshed successfully.")
                return True

            resp_json = {}
            try:
                resp_json = response.json()
            except Exception:
                pass

            error_msg = resp_json.get("detail") or resp_json.get("title") or response.text
            self.last_error = f"refresh_failed_http_{response.status_code}"
            logger.error(f"[AMOCRM ERROR] Token yangilashda xato: {error_msg}")
            if response.status_code == 401:
                logger.critical("[AMOCRM AUTH EXPIRED] Yangi authorization code kerak.")
            return False
        except Exception as e:
            self.last_error = "refresh_request_failed"
            logger.error(f"[AMOCRM ERROR] Request yuborishda xato: {e}")
            return False
    def authorize_initial(self, auth_code):
        """Birinchi marta kod yordamida token olish."""
        url = f"{self.base_url}/oauth2/access_token"
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "grant_type": "authorization_code",
            "code": auth_code,
            "redirect_uri": self.redirect_url,
        }
        
        try:
            response = requests.post(url, data=data)
            if response.status_code == 200:
                self._save_token(response.json())
                logger.info("[AMOCRM OK] Dastlabki avtorizatsiya muvaffaqiyatli.")
                return True
            else:
                logger.error(f"[AMOCRM ERROR] Avtorizatsiyada xato: {response.text}")
                return False
        except Exception as e:
            logger.error(f"[AMOCRM ERROR] Request yuborishda xato: {e}")
            return False

    async def delete_leads(self, lead_ids: list):
        """Lidlarni o'chirish (agar integratsiya ruxsat bersa)."""
        if not lead_ids: return False
        url = f"{self.base_url}/api/v4/leads"
        # AmoCRM API specifically doesn't allow bulk DELETE via standard DELETE verb in some versions.
        # But we can try the PATCH to 'is_deleted: true' if available, or individual DELETE calls.
        # However, standard practice is DELETE /api/v4/leads/{id}
        headers = self._get_headers()
        success_count = 0
        for lid in lead_ids:
            try:
                resp = requests.delete(f"{url}/{lid}", headers=headers)
                if resp.status_code in [200, 204]:
                    success_count += 1
            except Exception as e:
                logger.error(f"Error deleting lead {lid}: {e}")
        return success_count

    async def get_account_status(self):
        """Akkaunt limitlarini tekshirish."""
        url = f"{self.base_url}/api/v4/account"
        resp = requests.get(url, headers=self._get_headers())
        if resp.status_code == 200:
            return resp.json()
        return None

    async def check_connection(self) -> bool:
        """AmoCRM OAuth tokenini real account endpoint orqali tekshiradi."""
        if not self.access_token:
            self._load_token()

        if not self.access_token:
            self.last_error = "access_token_missing"
            return False

        url = f"{self.base_url}/api/v4/account"
        try:
            response = requests.get(url, headers=self._get_headers(), timeout=15)
            if response.status_code == 200:
                self.last_error = None
                return True

            if response.status_code == 401 and self.refresh_token():
                response = requests.get(url, headers=self._get_headers(), timeout=15)
                if response.status_code == 200:
                    self.last_error = None
                    return True

            self.last_error = f"check_connection_http_{response.status_code}"
            return False
        except Exception as e:
            self.last_error = "check_connection_exception"
            logger.error(f"[AMOCRM CHECK ERROR] {type(e).__name__}")
            return False

    def _get_headers(self):
        token = str(self.access_token or "")
        if not token:
            logger.warning("[AMOCRM] Access token is missing, requests will likely fail.")
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

    @retry_with_backoff(max_retries=3, initial_delay=1)
    def create_lead_for_contact(self, contact_id: int, name: str, price: int = 0, extra_fields: dict = None):
        """Mavjud kontakt uchun yangi bitim (Lead) yarating."""
        if not self.access_token:
            self._load_token()

        url = f"{self.base_url}/api/v4/leads"
        
        lead_entry = {
            "name": f"Loyiha: {name}",
            "price": price,
            "_embedded": {
                "contacts": [{"id": int(contact_id)}]
            }
        }
        
        if extra_fields:
            cf_values = []
            for f_id, f_val in extra_fields.items():
                if f_id and f_val:
                    cf_values.append({
                        "field_id": int(f_id), 
                        "values": [{"value": str(f_val)}]
                    })
            if cf_values:
                lead_entry["custom_fields_values"] = cf_values
            
        data = [lead_entry]

        try:
            response = requests.post(url, headers=self._get_headers(), json=data)
            if response.status_code == 200:
                result = response.json()
                return result.get("_embedded", {}).get("leads", [{}])[0].get("id")
            elif response.status_code == 403:
                err_msg = "[AMOCRM 403] Permission denied. Check if the widget is installed or token has data.records:read scope."
                logger.error(err_msg)
                # Auto-Alert for Owner
                try:
                    from src.main import client as telethon_client
                    if telethon_client:
                        import asyncio
                        asyncio.create_task(telethon_client.send_message('me', f"🆘 **AMOCRM CRITICAL: 403 Forbidden**\n\n{err_msg}"))
                except: pass
            elif response.status_code == 401:
                logger.warning("[AMOCRM 401] Token expired. Attempting refresh...")
                if self.refresh_token():
                    return self.create_lead_for_contact(contact_id, name, price, extra_fields)
            return False
        except Exception as e:
            logger.error(f"[AMOCRM ERROR] create_lead_for_contact error: {e}")
            return False

    @retry_with_backoff(max_retries=3, initial_delay=1)
    def create_contact(self, name: str, phone: str) -> Optional[int]:
        """Yangi kontakt yaratish."""
        self._load_token()
        url = f"{self.base_url}/api/v4/contacts"
        data = [
            {
                "name": name,
                "custom_fields_values": [
                    {
                        "field_code": "PHONE",
                        "values": [{"value": phone, "enum_code": "MOB"}]
                    }
                ]
            }
        ]
        try:
            response = requests.post(url, headers=self._get_headers(), json=data)
            if response.status_code in [200, 201]:
                return response.json().get("_embedded", {}).get("contacts", [{}])[0].get("id")
            return None
        except Exception as e:
            logger.error(f"[AMOCRM CONTACT CREATE ERROR] {e}")
            return None

    async def ensure_lead(self, name: str, phone: str, note: str = None) -> Optional[int]:
        """
        Kontaktni qidiradi yoki yaratadi, so'ngra unga yangi Bitim (Lead) bog'laydi.
        'Hunter bosqichlari' (10117998) -> 'Yangi so'rov' (80178230).
        """
        try:
            # 1. Kontaktni qidirish
            contact = self.get_contact_by_phone(phone)
            contact_id = contact.get("id") if contact else None

            # 2. Agar yo'q bo'lsa, yaratish
            if not contact_id:
                contact_id = self.create_contact(name, phone)
                if not contact_id:
                    logger.error(f"[AMOCRM SYNC] Kontaktni yaratib bo'lmadi: {name}")
                    return None

            # 3. Yangi Lead yaratish (Hunter bosqichlari)
            url = f"{self.base_url}/api/v4/leads"
            lead_data = [
                {
                    "name": f"Telegram Lead: {name}",
                    "status_id": 80178230,
                    "pipeline_id": 10117998,
                    "_embedded": {
                        "contacts": [{"id": int(contact_id)}]
                    }
                }
            ]
            
            response = requests.post(url, headers=self._get_headers(), json=lead_data)
            if response.status_code in [200, 201]:
                lead_id = response.json().get("_embedded", {}).get("leads", [{}])[0].get("id")
                
                # 4. Izoh qo'shish (agar bo'lsa)
                if lead_id and note:
                    self.add_lead_note(lead_id, note)
                
                return lead_id
            
            return None
        except Exception as e:
            logger.error(f"[AMOCRM ENSURE LEAD ERROR] {e}")
            return None

    @retry_with_backoff(max_retries=3, initial_delay=1)
    def get_contact_by_phone(self, phone: str) -> Optional[dict]:
        """Suhbatdoshni telefon raqami orqali qidirish (Robust normalization bilan)."""
        if not phone or phone == "Raqam yo'q":
            return None
            
        # Normalizatsiya: + olib tashlash, faqat raqamlarni qoldirish
        clean_phone = "".join(filter(str.isdigit, phone))
        # Oxirgi 9 ta raqamni olish (O'zbekiston formatida ishonchliroq)
        short_phone = clean_phone[-9:] if len(clean_phone) >= 9 else clean_phone

        self._load_token()
        url = f"{self.base_url}/api/v4/contacts"
        # Birinchi marta to'liq raqam bilan qidirish
        params = {"query": clean_phone}
        
        try:
            response = requests.get(url, headers=self._get_headers(), params=params)
            if response.status_code == 200:
                contacts = response.json().get("_embedded", {}).get("contacts", [])
                if contacts: return contacts[0]
            
            # Ikkinchi marta qisqa raqam bilan qidirish (agar birinchi marta topilmasa)
            params = {"query": short_phone}
            response = requests.get(url, headers=self._get_headers(), params=params)
            if response.status_code == 200:
                contacts = response.json().get("_embedded", {}).get("contacts", [])
                if contacts: return contacts[0]

            return None
        except Exception as e:
            logger.error(f"[AMOCRM SEARCH PHONE ERROR] {e}")
            return None

    def get_active_leads_for_contact(self, contact_id: int) -> List[Dict[str, Any]]:
        """Kontaktga biriktirilgan AKTIV (ochiq) bitimlarni olish."""
        self._load_token()
        # Kontakt tafsilotlarini 'leads' bilan birga olish
        url = f"{self.base_url}/api/v4/contacts/{contact_id}"
        params = {"with": "leads"}
        
        try:
            response = requests.get(url, headers=self._get_headers(), params=params)
            if response.status_code == 200:
                leads_refs = response.json().get("_embedded", {}).get("leads", [])
                if not leads_refs: return []
                
                active_leads = []
                for ref in leads_refs:
                    l_id = ref.get("id")
                    # Bitim statusini tekshirish
                    l_url = f"{self.base_url}/api/v4/leads/{l_id}"
                    l_resp = requests.get(l_url, headers=self._get_headers())
                    if l_resp.status_code == 200:
                        lead = l_resp.json()
                        # 142 (Won) va 143 (Lost) bo'lmagan barcha statuslar AKTIV hisoblanadi
                        if lead.get("status_id") not in [142, 143]:
                            active_leads.append(lead)
                return active_leads
            return []
        except Exception as e:
            logger.error(f"[AMOCRM ACTIVE LEADS ERROR] {e}")
            return []

    def get_lead_by_phone(self, phone: str) -> Optional[Dict[str, Any]]:
        """Telefon raqami orqali bitimni qidirish."""
        if not self.access_token:
            self._load_token()
        
        url = f"{self.base_url}/api/v4/contacts"
        params = {"query": phone}
        try:
            response = requests.get(url, headers=self._get_headers(), params=params)
            if response.status_code == 200:
                data = response.json()
                if not data: return None
                contacts = data.get("_embedded", {}).get("contacts", [])
                if contacts:
                    contact = contacts[0]
                    leads = contact.get("_embedded", {}).get("leads", [])
                    if leads:
                        lead_id = leads[0].get("id")
                        lead_url = f"{self.base_url}/api/v4/leads/{lead_id}"
                        lead_resp = requests.get(lead_url, headers=self._get_headers())
                        if lead_resp.status_code == 200:
                            return lead_resp.json()
            return None
        except Exception as e:
            logger.error(f"[AMOCRM FIND ERROR] {e}")
            return None

    def get_lead_status_text(self, lead: Dict[str, Any]) -> str:
        """Bitim holatini matn ko'rinishida qaytarish."""
        if not lead: return "Yangi mijoz"
        price = lead.get("price", 0)
        status_id = lead.get("status_id")
        return f"Mavjud mijoz. Bitim narxi: {price}. Status ID: {status_id}"

    async def get_user_context(self, phone: str) -> str:
        """User uchun kontekstni (lead statusini) olish."""
        lead = self.get_lead_by_phone(phone)
        return self.get_lead_status_text(lead) if lead else "Yangi mijoz"

    async def create_lead(
        self,
        name: str,
        phone: str,
        note: str = None,
        price: int = 0,
        extra_fields: dict = None,
    ) -> Optional[int]:
        """
        Backward-compatible async lead creation used by the userbot and scrapers.
        Ensures a contact exists, then creates a lead for that contact and appends a note.
        """
        try:
            contact = self.get_contact_by_phone(phone) if phone and phone != "Raqam yo'q" else None
            contact_id = contact.get("id") if contact else None

            if not contact_id and phone and phone != "Raqam yo'q":
                contact_id = self.create_contact(name, phone)

            if not contact_id:
                logger.error(f"[AMOCRM CREATE LEAD] Contact yaratilmadi: {name}")
                return None

            lead_id = self.create_lead_for_contact(contact_id, name, price=price, extra_fields=extra_fields)
            if lead_id and note:
                self.add_lead_note(lead_id, note)
            return lead_id
        except Exception as e:
            logger.error(f"[AMOCRM CREATE LEAD ERROR] {e}")
            return None

    async def get_leads(self, status_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Bitimlarni (Leads) olish. Basic plan uchun sodda so'rovlar."""
        if not self.access_token:
            self._load_token()
        
        url = f"{self.base_url}/api/v4/leads"
        params = {"limit": 50}
        if status_id:
            params["filter[status]"] = status_id
            
        try:
            response = requests.get(url, headers=self._get_headers(), params=params)
            if response.status_code == 401:
                if self.refresh_token():
                    response = requests.get(url, headers=self._get_headers(), params=params)
            
            if response.status_code == 200:
                data = response.json()
                return data.get("_embedded", {}).get("leads", [])
            return []
        except Exception as e:
            logger.error(f"[AMOCRM GET LEADS ERROR] {e}")
            return []

    async def create_task(
        self,
        element_id: int,
        text: str,
        complete_till: int,
        responsible_user_id: Optional[int] = None,
    ):
        """Lid uchun vazifa yaratish."""
        if not self.access_token:
            self._load_token()
            
        url = f"{self.base_url}/api/v4/tasks"
        task_payload = {
            "task_type_id": 1, # Call or generic task
            "text": text,
            "complete_till": complete_till,
            "entity_id": element_id,
            "entity_type": "leads"
        }
        if responsible_user_id:
            task_payload["responsible_user_id"] = int(responsible_user_id)

        data = [task_payload]
        
        try:
            response = requests.post(url, headers=self._get_headers(), json=data)
            if response.status_code == 401 and self.refresh_token():
                response = requests.post(url, headers=self._get_headers(), json=data)
            if response.status_code == 201:
                self.last_error = None
                logger.info(f"[AMOCRM OK] Vazifa yaratildi: {element_id}")
                return response.json()
            self.last_error = f"create_task_http_{response.status_code}"
            return False
        except Exception as e:
            self.last_error = "create_task_exception"
            logger.error(f"[AMOCRM TASK ERROR] {e}")
            return False

    async def get_tasks(self, is_completed: bool = False) -> List[Dict[str, Any]]:
        """AmoCRM dan vazifalarni olish."""
        if not self.access_token:
            self._load_token()
            
        url = f"{self.base_url}/api/v4/tasks"
        params = {"filter[is_completed]": 1 if is_completed else 0}
        
        try:
            response = requests.get(url, headers=self._get_headers(), params=params)
            if response.status_code == 200:
                data = response.json()
                return data.get("_embedded", {}).get("tasks", [])
            return []
        except Exception as e:
            logger.error(f"[AMOCRM GET TASKS ERROR] {e}")
            return []

    async def get_leads_detailed(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Bitimlarni batafsil ma'lumotlari bilan olish. Basic plan uchun order olib tashlandi."""
        if not self.access_token:
            self._load_token()
            
        url = f"{self.base_url}/api/v4/leads"
        # 'order' parametri Basic planda 402/501 berishi mumkin
        params = {"limit": min(limit, 50)} 
        
        try:
            response = requests.get(url, headers=self._get_headers(), params=params)
            if response.status_code == 401:
                if self.refresh_token():
                    response = requests.get(url, headers=self._get_headers(), params=params)
                else:
                    self.last_error = "amocrm_unauthorized"
                    return []

            if response.status_code == 200:
                self.last_error = None
                data = response.json()
                return data.get("_embedded", {}).get("leads", [])
            elif response.status_code == 402:
                self.last_error = "amocrm_payment_required"
                logger.error("[AMOCRM 402] Payment Required. Basic tarifda limitlar bor.")
            elif response.status_code == 401:
                self.last_error = "amocrm_unauthorized"
            else:
                self.last_error = f"get_leads_http_{response.status_code}"
            return []
        except Exception as e:
            self.last_error = "get_leads_exception"
            logger.error(f"[AMOCRM DETAILED LEADS ERROR] {e}")
            return []

    async def get_lead(self, lead_id: int) -> Optional[Dict[str, Any]]:
        """Bitta lid (status_id, pipeline_id va hokazo)."""
        if not self.access_token:
            self._load_token()
        url = f"{self.base_url}/api/v4/leads/{lead_id}"
        try:
            response = requests.get(url, headers=self._get_headers())
            if response.status_code == 401 and self.refresh_token():
                response = requests.get(url, headers=self._get_headers())
            if response.status_code == 200:
                return response.json()
            logger.warning(f"[AMOCRM GET LEAD] {lead_id} -> HTTP {response.status_code}")
            return None
        except Exception as e:
            logger.error(f"[AMOCRM GET LEAD ERROR] {e}")
            return None

    async def update_lead_status(self, lead_id: int, status_id: int, pipeline_id: int = None):
        """Bitim statusini (va ixtiyoriy ravishda pipelineni) yangilash."""
        url = f"{self.base_url}/api/v4/leads/{lead_id}"
        data = {"status_id": status_id}
        if pipeline_id:
            data["pipeline_id"] = pipeline_id
        
        try:
            response = requests.patch(url, headers=self._get_headers(), json=data)
            if response.status_code == 401 and self.refresh_token():
                response = requests.patch(url, headers=self._get_headers(), json=data)
            if response.status_code == 200:
                self.last_error = None
                logger.info(f"[AMOCRM OK] Status yangilandi: {lead_id} -> {status_id} (P:{pipeline_id})")
                return response.json()
            self.last_error = f"update_lead_status_http_{response.status_code}"
            return False
        except Exception as e:
            self.last_error = "update_lead_status_exception"
            logger.error(f"[AMOCRM UPDATE ERROR] {e}")
            return False

    async def update_lead_custom_fields(self, lead_id: int, fields_dict: dict):
        """Custom fieldlarni yangilash. fields_dict: {field_id: enum_id_yoki_text}"""
        url = f"{self.base_url}/api/v4/leads/{lead_id}"
        
        custom_fields = []
        for f_id, f_val in fields_dict.items():
            if isinstance(f_val, int):
                custom_fields.append({"field_id": int(f_id), "values": [{"enum_id": f_val}]})
            else:
                custom_fields.append({"field_id": int(f_id), "values": [{"value": str(f_val)}]})

        data = {"custom_fields_values": custom_fields}
        try:
            response = requests.patch(url, headers=self._get_headers(), json=data)
            if response.status_code == 200:
                logger.info(f"[AMOCRM OK] Custom fields yangilandi: {lead_id}")
                return True
            return False
        except Exception as e:
            logger.error(f"[AMOCRM FIELDS ERROR] {e}")
            return False

    async def add_lead_tag(self, lead_id: int, tag_name: str):
        """Lidga teg qo'shish."""
        url = f"{self.base_url}/api/v4/leads/{lead_id}"
        data = {"_embedded": {"tags": [{"name": tag_name}]}}
        
        try:
            response = requests.patch(url, headers=self._get_headers(), json=data)
            if response.status_code == 200:
                logger.info(f"[AMOCRM OK] Teg qo'shildi: {lead_id} -> {tag_name}")
                return True
            return False
        except Exception as e:
            logger.error(f"[AMOCRM TAG ERROR] {e}")
            return False

    def get_all_leads(self, limit: int = 250) -> List[Dict[str, Any]]:
        """Barcha lidlarni olish (re-engagement uchun)."""
        url = f"{self.base_url}/api/v4/leads"
        params = {"limit": limit, "order[updated_at]": "desc"}
        
        try:
            response = requests.get(url, headers=self._get_headers(), params=params)
            if response.status_code == 200:
                return response.json().get("_embedded", {}).get("leads", [])
            return []
        except Exception as e:
            logger.error(f"[AMOCRM GET ALL LEADS ERROR] {e}")
            return []

    def get_lead_phone(self, lead_id: int) -> Optional[str]:
        """Lidga biriktirilgan birinchi telefon raqamini olish."""
        url = f"{self.base_url}/api/v4/leads/{lead_id}"
        params = {"with": "contacts"}
        
        try:
            response = requests.get(url, headers=self._get_headers(), params=params)
            if response.status_code == 200:
                contacts = response.json().get("_embedded", {}).get("contacts", [])
                if not contacts:
                    return None
                
                # Kontakt ID orqali telefonni olish
                contact_id = contacts[0].get("id")
                c_url = f"{self.base_url}/api/v4/contacts/{contact_id}"
                c_resp = requests.get(c_url, headers=self._get_headers())
                if c_resp.status_code == 200:
                    fields = c_resp.json().get("custom_fields_values", [])
                    for field in fields:
                        if field.get("field_code") == "PHONE":
                            return field.get("values", [{}])[0].get("value")
            return None
        except Exception as e:
            logger.error(f"[AMOCRM GET PHONE ERROR] {e}")
            return None
    def update_lead_responsible(self, lead_id: int, responsible_user_id: int):
        """
        Lidning mas'ul shaxsini yangilash.
        """
        self._load_token()
        url = f"{self.base_url}/api/v4/leads/{lead_id}"
        headers = self._get_headers()
        data = {
            "responsible_user_id": int(responsible_user_id)
        }
        
        try:
            response = requests.patch(url, headers=headers, json=data)
            if response.status_code == 200:
                logger.info(f"[AMOCRM UPDATE] Lead {lead_id} assigned to user {responsible_user_id}")
                return True
            else:
                logger.error(f"[AMOCRM UPDATE ERROR] {response.status_code}: {response.text}")
                return False
        except Exception as e:
            logger.error(f"[AMOCRM UPDATE EXCEPTION] {e}")
            return False

    def get_user_name(self, user_id: int) -> str:
        """User ID orqali xodimning ismini olish."""
        if not user_id:
            return "Sotuv menejeri"
            
        url = f"{self.base_url}/api/v4/users/{user_id}"
        try:
            response = requests.get(url, headers=self._get_headers())
            if response.status_code == 200:
                user_data = response.json()
                return user_data.get("name", "Sotuv menejeri")
            return "Sotuv menejeri"
        except Exception as e:
            logger.error(f"[AMOCRM GET USER NAME ERROR] {e}")
            return "Sotuv menejeri"

    def update_contact_phone(self, name, phone):
        """Kontaktning telefon raqamini yangilash."""
        self._load_token()
        # 1. Kontaktni qidirish
        search_url = f"{self.base_url}/api/v4/contacts"
        params = {"query": name}
        headers = self._get_headers()
        
        try:
            resp = requests.get(search_url, headers=headers, params=params)
            if resp.status_code == 200:
                contacts = resp.json().get("_embedded", {}).get("contacts", [])
                if not contacts:
                    return False
                
                contact_id = contacts[0].get("id")
                update_url = f"{self.base_url}/api/v4/contacts/{contact_id}"
                data = {
                    "custom_fields_values": [
                        {
                            "field_code": "PHONE",
                            "values": [
                                {"value": phone, "enum_code": "MOB"}
                            ]
                        }
                    ]
                }
                upd_resp = requests.patch(update_url, headers=headers, json=data)
                return upd_resp.status_code == 200
            return False
        except Exception as e:
            logger.error(f"[AMOCRM UPDATE PHONE ERROR] {e}")
            return False
    def _dummy_placeholder(self):
        # Removing old redundant implementation of get_contact_by_phone as it's now enhanced above
        pass

    def add_contact_note(self, contact_id: int, text: str):
        """Kontaktga izoh (primicheniya) qo'shish."""
        return self._add_note(entity_type="contacts", entity_id=contact_id, text=text)

    def add_lead_note(self, lead_id: int, text: str):
        """Bitimga (Lead) izoh qo'shish."""
        return self._add_note(entity_type="leads", entity_id=lead_id, text=text)

    def _add_note(self, entity_type: str, entity_id: int, text: str):
        """Umumiy izoh qo'shish logikasi (Internal)."""
        self._load_token()
        url = f"{self.base_url}/api/v4/{entity_type}/{entity_id}/notes"
        data = [
            {
                "note_type": "common",
                "params": {
                    "text": text
                }
            }
        ]
        
        try:
            response = requests.post(url, headers=self._get_headers(), json=data)
            if response.status_code == 401 and self.refresh_token():
                response = requests.post(url, headers=self._get_headers(), json=data)
            if response.status_code in [200, 201]:
                self.last_error = None
                logger.info(f"[AMOCRM OK] {entity_type} {entity_id} ga izoh qo'shildi.")
                return response.json()
            else:
                self.last_error = f"add_note_http_{response.status_code}"
                logger.error(f"[AMOCRM NOTE ERROR] {response.status_code}: {response.text}")
                return False
        except Exception as e:
            self.last_error = "add_note_exception"
            logger.error(f"[AMOCRM NOTE EXCEPTION] {e}")
            return False

    async def get_lead_notes(self, lead_id: int) -> List[Dict[str, Any]]:
        """Bitim (Lead) ga tegishli barcha izohlarni (notes) olish."""
        self._load_token()
        url = f"{self.base_url}/api/v4/leads/{lead_id}/notes"
        try:
            response = requests.get(url, headers=self._get_headers())
            if response.status_code == 401:
                if self.refresh_token():
                    response = requests.get(url, headers=self._get_headers())
                else:
                    self.last_error = "amocrm_unauthorized"
                    return []
            if response.status_code == 200:
                self.last_error = None
                return response.json().get("_embedded", {}).get("notes", [])
            if response.status_code == 401:
                self.last_error = "amocrm_unauthorized"
            return []
        except Exception as e:
            self.last_error = "get_notes_exception"
            logger.error(f"[AMOCRM GET NOTES ERROR] {e}")
            return []

    async def delete_note(self, entity_type: str, entity_id: int, note_id: int):
        """Izohni o'chirish."""
        self._load_token()
        url = f"{self.base_url}/api/v4/{entity_type}/{entity_id}/notes/{note_id}"
        try:
            response = requests.delete(url, headers=self._get_headers())
            return response.status_code in [200, 204]
        except Exception as e:
            logger.error(f"[AMOCRM DELETE NOTE ERROR] {e}")
            return False

    def download_file(self, file_uuid: str) -> Optional[bytes]:
        """AmoCRM dan faylni yuklab olish."""
        self._load_token()
        # AmoCRM Files API orqali faylni olish
        url = f"{self.base_url}/api/v4/files/{file_uuid}"
        headers = self._get_headers()
        
        try:
            # 1. Metadatasini olish (download link uchun)
            resp = requests.get(url, headers=headers)
            if resp.status_code == 200:
                file_data = resp.json()
                download_url = file_data.get("download_url")
                
                if download_url:
                    # 2. Haqiqiy faylni yuklab olish
                    file_resp = requests.get(download_url, headers=headers)
                    if file_resp.status_code == 200:
                        return file_resp.content
            
            logger.error(f"[AMOCRM DOWNLOAD ERROR] {resp.status_code}: {resp.text}")
            return None
        except Exception as e:
            logger.error(f"[AMOCRM DOWNLOAD EXCEPTION] {e}")
            return None

    def get_sales_report(self) -> Dict[str, Any]:
        """Oylik sotuv hisobotini (Plan-Fakt) shakllantirish."""
        self._load_token()
        # Won (Muvaffaqiyatli) statusidagi bitimlarni olish
        # Odatda 142 status - bu Success (Won)
        from datetime import datetime, date
        first_day = datetime.combine(date.today().replace(day=1), datetime.min.time())
        timestamp_from = int(first_day.timestamp())
        
        url = f"{self.base_url}/api/v4/leads"
        params = {
            "filter[status][0]": 142, # 142 - muvaffaqiyatli bitim
            "filter[closed_at][from]": timestamp_from
        }
        
        try:
            response = requests.get(url, headers=self._get_headers(), params=params)
            total_sum = 0
            count = 0
            if response.status_code == 200:
                leads = response.json().get("_embedded", {}).get("leads", [])
                for lead in leads:
                    total_sum += lead.get("price", 0)
                    count += 1
            
            target = 80000000 # 80 mln so'm target
            return {
                "fact": total_sum,
                "target": target,
                "count": count,
                "percent": (total_sum / target * 100) if target > 0 else 0
            }
        except Exception as e:
            logger.error(f"[AMOCRM REPORT ERROR] {e}")
            return {"fact": 0, "target": 80000000, "count": 0, "percent": 0}

    def check_stagnated_leads(self, hours=24) -> List[Dict[str, Any]]:
        """Stagnatsiyaga tushgan (o'zgarmagan) bitimlarni aniqlash."""
        self._load_token()
        url = f"{self.base_url}/api/v4/leads"
        # Barcha ochiq (Won yoki Lost bo'lmagan) bitimlarni olamiz
        # Buning uchun barchaOpen status idlarni filtrlash kerak yoki oddiygina barchasini olib tahlil qilamiz
        try:
            response = requests.get(url, headers=self._get_headers())
            if response.status_code == 401:
                if self.refresh_token():
                    response = requests.get(url, headers=self._get_headers())
                else:
                    self.last_error = "amocrm_unauthorized"
                    return []
            stagnated = []
            now = int(time.time())
            limit = hours * 3600
            
            if response.status_code == 200:
                self.last_error = None
                leads = response.json().get("_embedded", {}).get("leads", [])
                for lead in leads:
                    # Agar bitim ochiq bo'lsa (status_id != 142 va != 143)
                    if lead.get("status_id") not in [142, 143]:
                        updated_at = lead.get("updated_at")
                        if (now - updated_at) > limit:
                            stagnated.append(lead)
            elif response.status_code == 401:
                self.last_error = "amocrm_unauthorized"
            else:
                self.last_error = f"check_stagnated_http_{response.status_code}"
            return stagnated
        except Exception as e:
            self.last_error = "check_stagnated_exception"
            logger.error(f"[AMOCRM STAGNATION ERROR] {e}")
            return []

if __name__ == "__main__":
    # Test
    logging.basicConfig(level=logging.INFO)
    # amocrm = AmoCRMSync("sub", "id", "secret", "url")
    # amocrm.create_lead("Test User", "+998901234567", 50000)
