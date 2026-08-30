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


from src.services.core.crm.amocrm.auth import (
    _plain_secret,
    retry_with_backoff,
)



class AmoCRMContactsMixin:
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
                        "values": [{"value": phone, "enum_code": "MOB"}],
                    }
                ],
            }
        ]
        try:
            response = requests.post(url, headers=self._get_headers(), json=data, timeout=30)
            if response.status_code in [200, 201]:
                return (
                    response.json()
                    .get("_embedded", {})
                    .get("contacts", [{}])[0]
                    .get("id")
                )
            return None
        except Exception as e:
            logger.error(f"[AMOCRM CONTACT CREATE ERROR] {e}")
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
            response = requests.get(url, headers=self._get_headers(), params=params, timeout=30)
            if response.status_code == 200:
                contacts = response.json().get("_embedded", {}).get("contacts", [])
                if contacts:
                    return contacts[0]

            # Ikkinchi marta qisqa raqam bilan qidirish (agar birinchi marta topilmasa)
            params = {"query": short_phone}
            response = requests.get(url, headers=self._get_headers(), params=params, timeout=30)
            if response.status_code == 200:
                contacts = response.json().get("_embedded", {}).get("contacts", [])
                if contacts:
                    return contacts[0]

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
            response = requests.get(url, headers=self._get_headers(), params=params, timeout=30)
            if response.status_code == 200:
                leads_refs = response.json().get("_embedded", {}).get("leads", [])
                if not leads_refs:
                    return []

                active_leads = []
                for ref in leads_refs:
                    l_id = ref.get("id")
                    # Bitim statusini tekshirish
                    l_url = f"{self.base_url}/api/v4/leads/{l_id}"
                    l_resp = requests.get(l_url, headers=self._get_headers(), timeout=30)
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

    def find_active_lead_by_phone(self, phone: str) -> Optional[Dict[str, Any]]:
        """Telefon orqali mavjud ochiq sdelkani topish.

        Uchrashuv kabi aniq actionlar yangi lead yaratmasligi kerak: avval
        shu telefon bog'langan ochiq sdelkani topamiz va ishni o'sha ichiga
        qo'yamiz. Won/Lost yopiq sdelkalar hisobga olinmaydi.
        """
        contact = self.get_contact_by_phone(phone)
        contact_id = contact.get("id") if contact else None
        if not contact_id:
            return None

        active_leads = self.get_active_leads_for_contact(int(contact_id))
        if not active_leads:
            return None

        return sorted(
            active_leads,
            key=lambda lead: int(
                lead.get("updated_at") or lead.get("created_at") or 0
            ),
            reverse=True,
        )[0]

    def get_lead_by_phone(self, phone: str) -> Optional[Dict[str, Any]]:
        """Telefon raqami orqali bitimni qidirish."""
        if not self.access_token:
            self._load_token()

        url = f"{self.base_url}/api/v4/contacts"
        params = {"query": phone}
        try:
            response = requests.get(url, headers=self._get_headers(), params=params, timeout=30)
            if response.status_code == 200:
                data = response.json()
                if not data:
                    return None
                contacts = data.get("_embedded", {}).get("contacts", [])
                if contacts:
                    contact = contacts[0]
                    leads = contact.get("_embedded", {}).get("leads", [])
                    if leads:
                        lead_id = leads[0].get("id")
                        lead_url = f"{self.base_url}/api/v4/leads/{lead_id}"
                        lead_resp = requests.get(lead_url, headers=self._get_headers(), timeout=30)
                        if lead_resp.status_code == 200:
                            return lead_resp.json()
            return None
        except Exception as e:
            logger.error(f"[AMOCRM FIND ERROR] {e}")
            return None

    def get_lead_status_text(self, lead: Dict[str, Any]) -> str:
        """Bitim holatini matn ko'rinishida qaytarish."""
        if not lead:
            return "Yangi mijoz"
        price = lead.get("price", 0)
        status_id = lead.get("status_id")
        return f"Mavjud mijoz. Bitim narxi: {price}. Status ID: {status_id}"

    async def get_user_context(self, phone: str) -> str:
        """User uchun kontekstni (lead statusini) olish."""
        lead = self.get_lead_by_phone(phone)
        return self.get_lead_status_text(lead) if lead else "Yangi mijoz"

    def merge_contacts(self, target_id: int, source_ids: List[int]) -> bool:
        """Kontaktlarni birlashtrish: source kontaktlarni target ga merge qilish."""
        self._load_token()
        url = f"{self.base_url}/api/v4/contacts/{target_id}/merge"
        data = [{"id": sid} for sid in source_ids]

        try:
            response = requests.post(url, headers=self._get_headers(), json=data, timeout=30)
            if response.status_code == 401 and self.refresh_token():
                response = requests.post(url, headers=self._get_headers(), json=data, timeout=30)
            if response.status_code in [200, 204]:
                logger.info(f"[AMOCRM MERGE] Kontaktlar birlashtirildi: {source_ids} -> {target_id}")
                return True
            logger.error(f"[AMOCRM MERGE ERROR] {response.status_code}: {response.text}")
            return False
        except Exception as e:
            logger.error(f"[AMOCRM MERGE EXCEPTION] {e}")
            return False

    def move_lead_to_contact(self, lead_id: int, contact_id: int) -> bool:
        """Leadni boshqa kontaktga ko'chirish (link qilish)."""
        self._load_token()
        url = f"{self.base_url}/api/v4/leads/{lead_id}/link"
        data = [{"to_entity_id": contact_id, "to_entity_type": "contacts"}]

        try:
            response = requests.post(url, headers=self._get_headers(), json=data, timeout=30)
            if response.status_code == 401 and self.refresh_token():
                response = requests.post(url, headers=self._get_headers(), json=data, timeout=30)
            if response.status_code in [200, 204]:
                logger.info(f"[AMOCRM LINK] Lead {lead_id} -> Contact {contact_id}")
                return True
            logger.error(f"[AMOCRM LINK ERROR] {response.status_code}: {response.text}")
            return False
        except Exception as e:
            logger.error(f"[AMOCRM LINK EXCEPTION] {e}")
            return False

    def unlink_lead_from_contact(self, lead_id: int, contact_id: int) -> bool:
        """Leadni kontaktdan ajratish (unlink)."""
        self._load_token()
        url = f"{self.base_url}/api/v4/leads/{lead_id}/unlink"
        data = [{"to_entity_id": contact_id, "to_entity_type": "contacts"}]

        try:
            response = requests.post(url, headers=self._get_headers(), json=data, timeout=30)
            if response.status_code == 401 and self.refresh_token():
                response = requests.post(url, headers=self._get_headers(), json=data, timeout=30)
            if response.status_code in [200, 204]:
                return True
            return False
        except Exception as e:
            logger.error(f"[AMOCRM UNLINK EXCEPTION] {e}")
            return False

    def get_contact_details(self, contact_id: int) -> Optional[Dict[str, Any]]:
        """Kontakt tafsilotlarini olish."""
        self._load_token()
        url = f"{self.base_url}/api/v4/contacts/{contact_id}"
        params = {"with": "leads"}
        try:
            response = requests.get(url, headers=self._get_headers(), params=params, timeout=30)
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            logger.error(f"[AMOCRM CONTACT DETAILS ERROR] {e}")
            return None

    def get_lead_phone(self, lead_id: int) -> Optional[str]:
        """Lidga biriktirilgan birinchi telefon raqamini olish."""
        url = f"{self.base_url}/api/v4/leads/{lead_id}"
        params = {"with": "contacts"}

        try:
            response = requests.get(url, headers=self._get_headers(), params=params, timeout=30)
            if response.status_code == 200:
                contacts = response.json().get("_embedded", {}).get("contacts", [])
                if not contacts:
                    return None

                # Kontakt ID orqali telefonni olish
                contact_id = contacts[0].get("id")
                c_url = f"{self.base_url}/api/v4/contacts/{contact_id}"
                c_resp = requests.get(c_url, headers=self._get_headers(), timeout=30)
                if c_resp.status_code == 200:
                    fields = c_resp.json().get("custom_fields_values", [])
                    for field in fields:
                        if field.get("field_code") == "PHONE":
                            return field.get("values", [{}])[0].get("value")
            return None
        except Exception as e:
            logger.error(f"[AMOCRM GET PHONE ERROR] {e}")
            return None

    def get_user_name(self, user_id: int) -> str:
        """User ID orqali xodimning ismini olish."""
        if not user_id:
            return "Sotuv menejeri"

        url = f"{self.base_url}/api/v4/users/{user_id}"
        try:
            response = requests.get(url, headers=self._get_headers(), timeout=30)
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
            resp = requests.get(search_url, headers=headers, params=params, timeout=30)
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
                            "values": [{"value": phone, "enum_code": "MOB"}],
                        }
                    ]
                }
                upd_resp = requests.patch(update_url, headers=headers, json=data, timeout=30)
                return upd_resp.status_code == 200
            return False
        except Exception as e:
            logger.error(f"[AMOCRM UPDATE PHONE ERROR] {e}")
            return False

    async def get_contact_details_async(
        self, contact_id: int, *, cache_ttl_seconds: int = 300
    ) -> Optional[Dict[str, Any]]:
        """Fetch contact details with linked leads and a short-lived per-process cache."""
        contact_id = int(contact_id)
        cached = self._contact_details_cache.get(contact_id)
        if cached and time.time() - cached[0] < cache_ttl_seconds:
            return cached[1]
        response = await self._request_with_auth(
            requests.get,
            f"{self.base_url}/api/v4/contacts/{contact_id}",
            params={"with": "leads"},
            timeout=30,
        )
        if response.status_code != 200:
            return None
        details = response.json()
        self._contact_details_cache[contact_id] = (time.time(), details)
        return details

    @staticmethod
    def _phone_from_contact(contact: Dict[str, Any]) -> str:
        for field in contact.get("custom_fields_values") or []:
            if str(field.get("field_code") or "").upper() != "PHONE":
                continue
            values = field.get("values") or []
            if values and values[0].get("value"):
                return str(values[0]["value"])
        return ""

    async def get_primary_contact_phone(self, lead: Dict[str, Any]) -> str:
        """Resolve a lead phone even when `with=contacts` embeds only contact IDs."""
        contacts = (
            lead.get("_embedded", {}).get("contacts", [])
            or lead.get("contacts", [])
        )
        for contact in contacts:
            phone = self._phone_from_contact(contact)
            if phone:
                return phone
            contact_id = contact.get("id")
            if not contact_id:
                continue
            details = await self.get_contact_details_async(int(contact_id))
            if details:
                phone = self._phone_from_contact(details)
                if phone:
                    return phone
        return ""

    async def get_contact_linked_leads(self, contact_id: int) -> List[Dict[str, Any]]:
        """Return leads linked to a contact for safe single-lead call routing."""
        details = await self.get_contact_details_async(contact_id)
        if not details:
            return []
        return details.get("_embedded", {}).get("leads", []) or []
