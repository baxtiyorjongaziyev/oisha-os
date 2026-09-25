"""
Lead creation operations for AmoCRM.
"""
from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

import requests
import structlog
from src.services.core.crm.amocrm.auth import retry_with_backoff
from src.services.core.crm.amocrm_pipeline_config import SALES_NEW_STATUS_ID, SALES_PIPELINE_ID

logger = structlog.get_logger()


class AmoCRMLeadsCreateMixin:
    """Methods for creating and ensuring leads in AmoCRM."""

    @retry_with_backoff(max_retries=3, initial_delay=1)
    def create_lead_for_contact(
        self,
        contact_id: int,
        lead_name: str,
        price: int = 0,
        pipeline_id: Optional[int] = None,
        status_id: Optional[int] = None,
        custom_fields: Optional[List[Dict[str, Any]]] = None,
    ) -> Optional[int]:
        """Kontaktga biriktirilgan yangi bitim yaratish."""
        self._load_token()
        url = f"{self.base_url}/api/v4/leads"

        lead_data: Dict[str, Any] = {
            "name": lead_name,
            "price": price,
            "_embedded": {"contacts": [{"id": contact_id}]},
        }

        if pipeline_id:
            lead_data["pipeline_id"] = pipeline_id
        if status_id:
            lead_data["status_id"] = status_id
        if custom_fields:
            lead_data["custom_fields_values"] = custom_fields

        try:
            response = requests.post(
                url, headers=self._get_headers(), json=[lead_data], timeout=30
            )
            if response.status_code == 401 and self.refresh_token():
                response = requests.post(
                    url, headers=self._get_headers(), json=[lead_data], timeout=30
                )
            if response.status_code in [200, 201]:
                lead_id = (
                    response.json()
                    .get("_embedded", {})
                    .get("leads", [{}])[0]
                    .get("id")
                )
                logger.info(
                    f"[AMOCRM LEAD CREATED] ID: {lead_id} for contact {contact_id}"
                )
                return lead_id
            if response.status_code == 400 and "custom_fields_values" in lead_data:
                logger.warning(
                    f"[AMOCRM LEAD RETRY] Status 400 with custom fields, retrying without: {response.text}"
                )
                fallback_data = dict(lead_data)
                fallback_data.pop("custom_fields_values", None)
                retry_resp = requests.post(
                    url, headers=self._get_headers(), json=[fallback_data], timeout=30
                )
                if retry_resp.status_code in [200, 201]:
                    lead_id = (
                        retry_resp.json()
                        .get("_embedded", {})
                        .get("leads", [{}])[0]
                        .get("id")
                    )
                    logger.info(
                        f"[AMOCRM LEAD CREATED FALLBACK] ID: {lead_id} without custom fields for contact {contact_id}"
                    )
                    return lead_id
            logger.error(
                f"[AMOCRM LEAD CREATE FAILED] Status: {response.status_code}, Body: {response.text}"
            )
            return None
        except Exception as e:
            logger.error(f"[AMOCRM LEAD CREATE ERROR] {e}")
            return None

    async def create_lead(
        self,
        name: str,
        phone: str,
        price: int = 0,
        pipeline_id: Optional[int] = None,
        status_id: Optional[int] = None,
        custom_fields: Optional[List[Dict[str, Any]]] = None,
    ) -> Optional[int]:
        """Telefon raqam orqali kontaktni qidiradi (yoki yaratadi) va unga bitim ochadi."""
        contact = await asyncio.to_thread(self.get_contact_by_phone, phone)

        if not contact:
            contact_id = await asyncio.to_thread(
                self.create_contact, name, phone
            )
            if not contact_id:
                logger.error(f"[AMOCRM] Kontakt yaratib bo'lmadi: {phone}")
                return None
        else:
            contact_id = contact.get("id")

        return await asyncio.to_thread(
            self.create_lead_for_contact,
            contact_id=contact_id,
            lead_name=f"{name} ({phone})",
            price=price,
            pipeline_id=pipeline_id,
            status_id=status_id,
            custom_fields=custom_fields,
        )

    async def create_standalone_lead(
        self,
        name: str,
        price: int = 0,
        pipeline_id: Optional[int] = None,
        status_id: Optional[int] = None,
        custom_fields: Optional[List[Dict[str, Any]]] = None,
        tags: Optional[List[str]] = None,
        note: Optional[str] = None,
    ) -> Optional[int]:
        """Kontaktsiz to'g'ridan-to'g'ri mustaqil bitim (lead) ochadi."""
        self._load_token()
        url = f"{self.base_url}/api/v4/leads"

        lead_data: Dict[str, Any] = {
            "name": name,
            "price": price,
        }

        if pipeline_id:
            lead_data["pipeline_id"] = pipeline_id
        if status_id:
            lead_data["status_id"] = status_id
        if custom_fields:
            lead_data["custom_fields_values"] = custom_fields
        if tags:
            lead_data["_embedded"] = {"tags": [{"name": t} for t in tags]}

        try:
            response = await asyncio.to_thread(
                requests.post,
                url,
                headers=self._get_headers(),
                json=[lead_data],
                timeout=30,
            )
            if response.status_code in [200, 201]:
                lead_id = (
                    response.json()
                    .get("_embedded", {})
                    .get("leads", [{}])[0]
                    .get("id")
                )
                logger.info(
                    f"[AMOCRM STANDALONE LEAD CREATED] ID: {lead_id} Name: {name}"
                )
                if note and lead_id:
                    await asyncio.to_thread(
                        self.add_lead_note, int(lead_id), str(note)
                    )
                return lead_id
            if response.status_code == 400 and "custom_fields_values" in lead_data:
                logger.warning(
                    f"[AMOCRM STANDALONE RETRY] Status 400 with custom fields, retrying without: {response.text}"
                )
                fallback_data = dict(lead_data)
                fallback_data.pop("custom_fields_values", None)
                retry_resp = await asyncio.to_thread(
                    requests.post,
                    url,
                    headers=self._get_headers(),
                    json=[fallback_data],
                    timeout=30,
                )
                if retry_resp.status_code in [200, 201]:
                    lead_id = (
                        retry_resp.json()
                        .get("_embedded", {})
                        .get("leads", [{}])[0]
                        .get("id")
                    )
                    logger.info(
                        f"[AMOCRM STANDALONE LEAD CREATED FALLBACK] ID: {lead_id} without custom fields"
                    )
                    if note and lead_id:
                        await asyncio.to_thread(
                            self.add_lead_note, int(lead_id), str(note)
                        )
                    return lead_id
            logger.error(
                f"[AMOCRM STANDALONE LEAD FAILED] Status: {response.status_code}, Body: {response.text}"
            )
            return None
        except Exception as e:
            logger.error(f"[AMOCRM STANDALONE LEAD ERROR] {e}")
            return None

    async def ensure_lead(
        self,
        name: str,
        phone: str,
        note: Optional[str] = None,
        pipeline_id: Optional[int] = None,
        status_id: Optional[int] = None,
        custom_fields: Optional[List[Dict[str, Any]]] = None,
    ) -> Optional[int]:
        """Mavjud aktiv bitimni qidiradi, bo'lmasa yangisini ochadi."""
        existing_lead = await asyncio.to_thread(
            self.find_active_lead_by_phone, phone
        )
        if existing_lead:
            lead_id = existing_lead.get("id")
            logger.info(
                f"[AMOCRM ENSURE LEAD] Mavjud aktiv bitim topildi: {lead_id}"
            )
            if note:
                await asyncio.to_thread(self.add_lead_note, lead_id, note)
            return lead_id

        lead_id = await self.create_lead(
            name=name,
            phone=phone,
            pipeline_id=pipeline_id or SALES_PIPELINE_ID,
            status_id=status_id or SALES_NEW_STATUS_ID,
            custom_fields=custom_fields,
        )
        if lead_id and note:
            await asyncio.to_thread(self.add_lead_note, lead_id, note)

        return lead_id
