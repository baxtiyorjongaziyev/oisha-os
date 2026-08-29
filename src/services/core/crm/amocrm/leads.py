import asyncio
import os
import time
import json
import logging
import requests  # type: ignore
from typing import Optional, Dict, Any, List
from functools import wraps

import structlog

logger = structlog.get_logger()


def retry_with_backoff(
    max_retries=3,
    initial_delay=1,
    backoff_factor=2,
    exceptions=(requests.RequestException,),
):
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
                    logger.warning(
                        f"[AMOCRM RETRY] {func.__name__} attempt {attempt + 1}/{max_retries} failed: {e}"
                    )
                    if attempt < max_retries - 1:
                        time.sleep(delay)
                        delay *= backoff_factor

            logger.error(
                f"[AMOCRM RETRY] {func.__name__} failed after {max_retries} attempts: {last_exception}"
            )
            raise last_exception

        return wrapper

    return decorator


def _plain_secret(value: Any) -> Any:
    """Pydantic SecretStr'ni oddiy matnga aylantiradi.

    OAuth so'rovlari client_secret'ni JSON yoki form body'da yuboradi.
    SecretStr obyekti JSON-serializable emas, form-encoding'da esa
    '**********' ko'rinishida maskalanadi — ikkala holatda ham auth jim
    yiqiladi. Chaqiruvchilarning bir qismi settings'dan xom SecretStr uzatadi,
    shuning uchun normallashtirishni shu yerda, bitta joyda qilamiz.
    """
    getter = getattr(value, "get_secret_value", None)
    return getter() if callable(getter) else value



class AmoCRMLeadsMixin:
    @retry_with_backoff(max_retries=3, initial_delay=1)
    def create_lead_for_contact(
        self, contact_id: int, name: str, price: int = 0, extra_fields: dict = None
    ):
        """Mavjud kontakt uchun yangi bitim (Lead) yarating."""
        if not self.access_token:
            self._load_token()

        url = f"{self.base_url}/api/v4/leads"

        lead_entry = {
            "name": f"Loyiha: {name}",
            "price": price,
            "_embedded": {"contacts": [{"id": int(contact_id)}]},
        }

        if extra_fields:
            cf_values = []
            for f_id, f_val in extra_fields.items():
                if f_id and f_val:
                    cf_values.append(
                        {"field_id": int(f_id), "values": [{"value": str(f_val)}]}
                    )
            if cf_values:
                lead_entry["custom_fields_values"] = cf_values

        data = [lead_entry]

        try:
            response = requests.post(url, headers=self._get_headers(), json=data, timeout=30)
            if response.status_code == 200:
                result = response.json()
                return result.get("_embedded", {}).get("leads", [{}])[0].get("id")
            elif response.status_code == 403:
                err_msg = "[AMOCRM 403] Permission denied. Check if the widget is installed or token has data.records:read scope."
                logger.error(err_msg)
                # Auto-Alert for Owner
                try:
                    from src.context import app_ctx

                    if app_ctx.client:
                        import asyncio

                        asyncio.create_task(
                            app_ctx.client.send_message(
                                "me",
                                f"🆘 **AMOCRM CRITICAL: 403 Forbidden**\n\n{err_msg}",
                            )
                        )
                except Exception:
                    logger.warning("[AMOCRM] Failed to send 403 critical alert via Telegram", exc_info=True)
            elif response.status_code == 401:
                logger.warning("[AMOCRM 401] Token expired. Attempting refresh...")
                if self.refresh_token():
                    return self.create_lead_for_contact(
                        contact_id, name, price, extra_fields
                    )
            return False
        except Exception as e:
            logger.error(f"[AMOCRM ERROR] create_lead_for_contact error: {e}")
            return False

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
            contact = (
                self.get_contact_by_phone(phone)
                if phone and phone != "Raqam yo'q"
                else None
            )
            contact_id = contact.get("id") if contact else None

            if not contact_id and phone and phone != "Raqam yo'q":
                contact_id = self.create_contact(name, phone)

            if not contact_id:
                logger.error(f"[AMOCRM CREATE LEAD] Contact yaratilmadi: {name}")
                return None

            lead_id = self.create_lead_for_contact(
                contact_id, name, price=price, extra_fields=extra_fields
            )
            if lead_id and note:
                self.add_lead_note(lead_id, note)
            return lead_id
        except Exception as e:
            logger.error(f"[AMOCRM CREATE LEAD ERROR] {e}")
            return None

    async def create_standalone_lead(
        self,
        name: str,
        note: str = None,
        price: int = 0,
        pipeline_id: int = 11162698,
        status_id: int = 87609514,
        tags: Optional[List[str]] = None,
        responsible_user_id: Optional[int] = None,
    ) -> Optional[int]:
        """Create an AmoCRM lead even when Telegram phone is unavailable."""
        if not self.access_token:
            self._load_token()

        url = f"{self.base_url}/api/v4/leads"
        payload: Dict[str, Any] = {
            "name": name,
            "price": int(price or 0),
            "pipeline_id": int(pipeline_id),
            "status_id": int(status_id),
        }
        if responsible_user_id:
            payload["responsible_user_id"] = int(responsible_user_id)
        if tags:
            payload["_embedded"] = {"tags": [{"name": str(tag)} for tag in tags if tag]}

        try:
            response = requests.post(url, headers=self._get_headers(), json=[payload], timeout=30)
            if response.status_code == 401 and self.refresh_token():
                response = requests.post(url, headers=self._get_headers(), json=[payload], timeout=30)

            if response.status_code in [200, 201]:
                lead_id = (
                    response.json().get("_embedded", {}).get("leads", [{}])[0].get("id")
                )
                if lead_id and note:
                    self.add_lead_note(int(lead_id), note)
                logger.info(f"[AMOCRM OK] Standalone lead yaratildi: {lead_id}")
                return int(lead_id) if lead_id else None

            self.last_error = f"create_standalone_lead_http_{response.status_code}"
            logger.error(
                f"[AMOCRM STANDALONE LEAD ERROR] {response.status_code}: {response.text}"
            )
            return None
        except Exception as e:
            self.last_error = "create_standalone_lead_exception"
            logger.error(f"[AMOCRM STANDALONE LEAD EXCEPTION] {e}")
            return None

    async def ensure_lead(
        self, name: str, phone: str, note: str = None
    ) -> Optional[int]:
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
                    "status_id": 87609514,
                    "pipeline_id": 11162698,
                    "_embedded": {"contacts": [{"id": int(contact_id)}]},
                }
            ]

            response = requests.post(url, headers=self._get_headers(), json=lead_data, timeout=30)
            if response.status_code in [200, 201]:
                lead_id = (
                    response.json().get("_embedded", {}).get("leads", [{}])[0].get("id")
                )

                # 4. Izoh qo'shish (agar bo'lsa)
                if lead_id and note:
                    self.add_lead_note(lead_id, note)

                return lead_id

            return None
        except Exception as e:
            logger.error(f"[AMOCRM ENSURE LEAD ERROR] {e}")
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
            response = requests.get(url, headers=self._get_headers(), params=params, timeout=30)
            if response.status_code == 401:
                if self.refresh_token():
                    response = requests.get(
                        url, headers=self._get_headers(), params=params,
                        timeout=30)

            if response.status_code == 200:
                data = response.json()
                return data.get("_embedded", {}).get("leads", [])
            return []
        except Exception as e:
            logger.error(f"[AMOCRM GET LEADS ERROR] {e}")
            return []

    async def get_lead(self, lead_id: int) -> Optional[Dict[str, Any]]:
        """Bitta lid (status_id, pipeline_id va hokazo)."""
        if not self.access_token:
            self._load_token()
        url = f"{self.base_url}/api/v4/leads/{lead_id}"
        try:
            response = await self._request_with_auth(requests.get, url, timeout=30)
            if response.status_code == 401 and await asyncio.to_thread(self.refresh_token):
                response = await self._request_with_auth(requests.get, url, timeout=30)
            if response.status_code == 200:
                return response.json()
            logger.warning(
                f"[AMOCRM GET LEAD] {lead_id} -> HTTP {response.status_code}"
            )
            return None
        except Exception as e:
            logger.error(f"[AMOCRM GET LEAD ERROR] {e}")
            return None

    def get_all_leads(self, limit: int = 250) -> List[Dict[str, Any]]:
        """Barcha lidlarni olish (re-engagement uchun)."""
        url = f"{self.base_url}/api/v4/leads"
        params = {"limit": limit, "order[updated_at]": "desc"}

        try:
            response = requests.get(url, headers=self._get_headers(), params=params, timeout=30)
            if response.status_code == 200:
                return response.json().get("_embedded", {}).get("leads", [])
            return []
        except Exception as e:
            logger.error(f"[AMOCRM GET ALL LEADS ERROR] {e}")
            return []

    async def get_leads_detailed(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Bitimlarni batafsil ma'lumotlari bilan olish. Basic plan uchun order olib tashlandi."""
        if not self.access_token:
            self._load_token()

        url = f"{self.base_url}/api/v4/leads"
        # 'order' parametri Basic planda 402/501 berishi mumkin
        params = {"limit": min(limit, 50), "with": "contacts"}

        try:
            response = await self._request_with_auth(requests.get, url, params=params, timeout=30)
            if response.status_code == 401:
                if await asyncio.to_thread(self.refresh_token):
                    response = await self._request_with_auth(
                        requests.get, url, params=params, timeout=30
                    )
                else:
                    self.last_error = "amocrm_unauthorized"
                    return []

            if response.status_code == 200:
                self.last_error = None
                data = response.json()
                return data.get("_embedded", {}).get("leads", [])
            elif response.status_code == 402:
                self.last_error = "amocrm_payment_required"
                logger.error(
                    "[AMOCRM 402] Payment Required. Basic tarifda limitlar bor."
                )
            elif response.status_code == 401:
                self.last_error = "amocrm_unauthorized"
            else:
                self.last_error = f"get_leads_http_{response.status_code}"
            return []
        except Exception as e:
            self.last_error = "get_leads_exception"
            logger.error(f"[AMOCRM DETAILED LEADS ERROR] {e}")
            return []

    async def update_lead_status(
        self, lead_id: int, status_id: int, pipeline_id: int = None
    ):
        """Bitim statusini (va ixtiyoriy ravishda pipelineni) yangilash."""
        url = f"{self.base_url}/api/v4/leads/{lead_id}"
        data = {"status_id": status_id}
        if pipeline_id:
            data["pipeline_id"] = pipeline_id

        try:
            response = await self._request_with_auth(requests.patch, url, json=data, timeout=30)
            if response.status_code == 401 and await asyncio.to_thread(self.refresh_token):
                response = await self._request_with_auth(requests.patch, url, json=data, timeout=30)
            if response.status_code == 200:
                self.last_error = None
                logger.info(
                    f"[AMOCRM OK] Status yangilandi: {lead_id} -> {status_id} (P:{pipeline_id})"
                )
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
                custom_fields.append(
                    {"field_id": int(f_id), "values": [{"enum_id": f_val}]}
                )
            else:
                custom_fields.append(
                    {"field_id": int(f_id), "values": [{"value": str(f_val)}]}
                )

        data = {"custom_fields_values": custom_fields}
        try:
            response = await self._request_with_auth(requests.patch, url, json=data, timeout=30)
            if response.status_code == 200:
                logger.info(f"[AMOCRM OK] Custom fields yangilandi: {lead_id}")
                return True
            return False
        except Exception as e:
            logger.error(f"[AMOCRM FIELDS ERROR] {e}")
            return False

    def update_lead_responsible(self, lead_id: int, responsible_user_id: int):
        """
        Lidning mas'ul shaxsini yangilash.
        """
        self._load_token()
        url = f"{self.base_url}/api/v4/leads/{lead_id}"
        headers = self._get_headers()
        data = {"responsible_user_id": int(responsible_user_id)}

        try:
            response = requests.patch(url, headers=headers, json=data, timeout=30)
            if response.status_code == 200:
                logger.info(
                    f"[AMOCRM UPDATE] Lead {lead_id} assigned to user {responsible_user_id}"
                )
                return True
            else:
                logger.error(
                    f"[AMOCRM UPDATE ERROR] {response.status_code}: {response.text}"
                )
                return False
        except Exception as e:
            logger.error(f"[AMOCRM UPDATE EXCEPTION] {e}")
            return False

    async def add_lead_tag(self, lead_id: int, tag_name: str):
        """Lidga teg qo'shish."""
        url = f"{self.base_url}/api/v4/leads/{lead_id}"
        data = {"_embedded": {"tags": [{"name": tag_name}]}}

        try:
            response = await self._request_with_auth(requests.patch, url, json=data, timeout=30)
            if response.status_code == 200:
                logger.info(f"[AMOCRM OK] Teg qo'shildi: {lead_id} -> {tag_name}")
                return True
            return False
        except Exception as e:
            logger.error(f"[AMOCRM TAG ERROR] {e}")
            return False

    async def delete_leads(self, lead_ids: list):
        """Lidlarni o'chirish (agar integratsiya ruxsat bersa)."""
        if not lead_ids:
            return False
        url = f"{self.base_url}/api/v4/leads"
        # AmoCRM API specifically doesn't allow bulk DELETE via standard DELETE verb in some versions.
        # But we can try the PATCH to 'is_deleted: true' if available, or individual DELETE calls.
        # However, standard practice is DELETE /api/v4/leads/{id}
        headers = self._get_headers()
        success_count = 0
        for lid in lead_ids:
            try:
                resp = requests.delete(f"{url}/{lid}", headers=headers, timeout=30)
                if resp.status_code in [200, 204]:
                    success_count += 1
            except Exception as e:
                logger.error(f"Error deleting lead {lid}: {e}")
        return success_count

    def check_stagnated_leads(self, hours=24) -> List[Dict[str, Any]]:
        """Stagnatsiyaga tushgan (o'zgarmagan) bitimlarni aniqlash."""
        self._load_token()
        url = f"{self.base_url}/api/v4/leads"
        # Barcha ochiq (Won yoki Lost bo'lmagan) bitimlarni olamiz
        # Buning uchun barchaOpen status idlarni filtrlash kerak yoki oddiygina barchasini olib tahlil qilamiz
        try:
            response = requests.get(url, headers=self._get_headers(), timeout=30)
            if response.status_code == 401:
                if self.refresh_token():
                    response = requests.get(url, headers=self._get_headers(), timeout=30)
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
