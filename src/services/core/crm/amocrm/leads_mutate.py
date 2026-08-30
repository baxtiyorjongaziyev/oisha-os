"""
Lead update and mutation operations for AmoCRM.
"""
from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

import requests
import structlog

logger = structlog.get_logger()


class AmoCRMLeadsMutateMixin:
    """Methods for updating and deleting leads in AmoCRM."""

    async def update_lead_status(
        self,
        lead_id: int,
        status_id: int,
        pipeline_id: Optional[int] = None,
    ) -> bool:
        self._load_token()
        url = f"{self.base_url}/api/v4/leads/{lead_id}"
        payload: Dict[str, Any] = {"status_id": status_id}
        if pipeline_id:
            payload["pipeline_id"] = pipeline_id

        try:
            response = await asyncio.to_thread(
                requests.patch,
                url,
                headers=self._get_headers(),
                json=payload,
                timeout=30,
            )
            return response.status_code in [200, 204]
        except Exception as e:
            logger.error(f"[AMOCRM UPDATE LEAD STATUS ERROR] ID {lead_id}: {e}")
            return False

    async def update_lead_custom_fields(self, lead_id: int, fields_dict: dict):
        self._load_token()
        url = f"{self.base_url}/api/v4/leads/{lead_id}"
        cf_values = []
        for field_id, value in fields_dict.items():
            cf_values.append(
                {"field_id": int(field_id), "values": [{"value": value}]}
            )

        payload = {"custom_fields_values": cf_values}
        try:
            response = await asyncio.to_thread(
                requests.patch,
                url,
                headers=self._get_headers(),
                json=payload,
                timeout=30,
            )
            return response.status_code in [200, 204]
        except Exception as e:
            logger.error(
                f"[AMOCRM UPDATE LEAD CUSTOM FIELDS ERROR] ID {lead_id}: {e}"
            )
            return False

    def update_lead_responsible(self, lead_id: int, responsible_user_id: int):
        self._load_token()
        url = f"{self.base_url}/api/v4/leads/{lead_id}"
        payload = {"responsible_user_id": responsible_user_id}

        try:
            response = requests.patch(
                url, headers=self._get_headers(), json=payload, timeout=30
            )
            if response.status_code in [200, 204]:
                logger.info(
                    f"[AMOCRM UPDATE RESPONSIBLE SUCCESS] Lead {lead_id} -> User {responsible_user_id}"
                )
                return True
            logger.error(
                f"[AMOCRM UPDATE RESPONSIBLE FAILED] Status {response.status_code}: {response.text}"
            )
            return False
        except Exception as e:
            logger.error(f"[AMOCRM UPDATE RESPONSIBLE ERROR] {e}")
            return False

    async def add_lead_tag(self, lead_id: int, tag_name: str):
        self._load_token()
        url = f"{self.base_url}/api/v4/leads/{lead_id}"
        payload = {"_embedded": {"tags": [{"name": tag_name}]}}

        try:
            response = await asyncio.to_thread(
                requests.patch,
                url,
                headers=self._get_headers(),
                json=payload,
                timeout=30,
            )
            return response.status_code in [200, 204]
        except Exception as e:
            logger.error(f"[AMOCRM ADD LEAD TAG ERROR] ID {lead_id}: {e}")
            return False

    async def delete_leads(self, lead_ids: list):
        """Lidlarni o'chirish."""
        if not lead_ids:
            return False
        url = f"{self.base_url}/api/v4/leads"
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
