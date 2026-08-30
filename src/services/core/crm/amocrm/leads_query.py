"""
Lead querying operations for AmoCRM.
"""
from __future__ import annotations

import asyncio
import time
from typing import Any, Dict, List, Optional

import requests
import structlog

logger = structlog.get_logger()


class AmoCRMLeadsQueryMixin:
    """Methods for querying leads from AmoCRM."""

    async def get_leads(self, status_id: Optional[int] = None) -> List[Dict[str, Any]]:
        self._load_token()
        url = f"{self.base_url}/api/v4/leads"
        params = {}
        if status_id:
            params["filter[statuses][0][status_id]"] = status_id

        try:
            response = await asyncio.to_thread(
                requests.get,
                url,
                headers=self._get_headers(),
                params=params,
                timeout=30,
            )
            if response.status_code == 200:
                return (
                    response.json().get("_embedded", {}).get("leads", [])
                )
            return []
        except Exception as e:
            logger.error(f"[AMOCRM GET LEADS ERROR] {e}")
            return []

    async def get_lead(self, lead_id: int) -> Optional[Dict[str, Any]]:
        self._load_token()
        url = f"{self.base_url}/api/v4/leads/{lead_id}"
        params = {"with": "contacts,loss_reason"}

        try:
            response = await asyncio.to_thread(
                requests.get,
                url,
                headers=self._get_headers(),
                params=params,
                timeout=30,
            )
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            logger.error(f"[AMOCRM GET LEAD ERROR] ID {lead_id}: {e}")
            return None

    def get_all_leads(self, limit: int = 250) -> List[Dict[str, Any]]:
        self._load_token()
        url = f"{self.base_url}/api/v4/leads"
        params = {"limit": limit, "with": "contacts"}

        try:
            response = requests.get(
                url, headers=self._get_headers(), params=params, timeout=30
            )
            if response.status_code == 200:
                return (
                    response.json().get("_embedded", {}).get("leads", [])
                )
            return []
        except Exception as e:
            logger.error(f"[AMOCRM GET ALL LEADS ERROR] {e}")
            return []

    async def get_leads_detailed(self, limit: int = 50) -> List[Dict[str, Any]]:
        self._load_token()
        url = f"{self.base_url}/api/v4/leads"
        params = {"limit": limit, "with": "contacts,loss_reason"}

        try:
            response = await asyncio.to_thread(
                requests.get,
                url,
                headers=self._get_headers(),
                params=params,
                timeout=30,
            )
            if response.status_code == 200:
                leads = response.json().get("_embedded", {}).get("leads", [])
                for lead in leads:
                    contacts = (
                        lead.get("_embedded", {}).get("contacts", [])
                    )
                    if contacts:
                        contact_id = contacts[0].get("id")
                        if contact_id:
                            contact_details = await asyncio.to_thread(
                                self.get_contact_details, contact_id
                            )
                            if contact_details:
                                lead["contact_phone"] = (
                                    contact_details.get("phone")
                                )
                                lead["contact_name"] = (
                                    contact_details.get("name")
                                )
                return leads
            return []
        except Exception as e:
            logger.error(f"[AMOCRM GET DETAILED LEADS ERROR] {e}")
            return []

    def check_stagnated_leads(self, hours=24) -> List[Dict[str, Any]]:
        """Stagnatsiyaga tushgan (o'zgarmagan) bitimlarni aniqlash."""
        self._load_token()
        url = f"{self.base_url}/api/v4/leads"
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
