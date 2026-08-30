"""
CRMArchiver implementation.
"""
from __future__ import annotations

import asyncio
import datetime
import json
import logging
from typing import Any, Dict, List, Optional, Set

import requests
import src.config as config
from src.database import Database
from src.services.core.crm.amocrm_sync import AmoCRMSync
from src.services.core.crm.archiver.campaign import generate_outreach_campaign
from src.services.core.crm.archiver.schema import (
    init_archiver_tables,
    save_archived_lead_and_campaign,
)

logger = logging.getLogger("crm_archiver")


class CRMArchiver:
    def __init__(self, amocrm: Optional[AmoCRMSync] = None, db: Optional[Database] = None):
        self.amocrm = amocrm or AmoCRMSync(
            config.AMOCRM_SUBDOMAIN,
            config.AMOCRM_CLIENT_ID,
            config.AMOCRM_CLIENT_SECRET,
            config.AMOCRM_REDIRECT_URL,
        )
        self.db = db or Database()

    async def init_tables(self):
        await init_archiver_tables(self.db)

    async def fetch_all_active_leads(self) -> List[Dict[str, Any]]:
        logger.info("[ARCHIVER] AmoCRM dan barcha aktiv bitimlarni yuklash boshlandi...")
        active_leads = []
        limit = 250
        page = 1

        if not self.amocrm.access_token:
            self.amocrm._load_token()

        loop = asyncio.get_event_loop()

        while True:
            url = f"{self.amocrm.base_url}/api/v4/leads"
            params = {
                "limit": limit,
                "page": page,
                "with": "contacts",
            }
            try:
                response = await loop.run_in_executor(
                    None,
                    lambda: requests.get(
                        url,
                        headers=self.amocrm._get_headers(),
                        params=params,
                        timeout=30,
                    ),
                )

                if response.status_code == 401:
                    logger.info("[ARCHIVER] Token eskirgan. Yangilanmoqda...")
                    refreshed = await loop.run_in_executor(None, self.amocrm.refresh_token)
                    if refreshed:
                        response = await loop.run_in_executor(
                            None,
                            lambda: requests.get(
                                url,
                                headers=self.amocrm._get_headers(),
                                params=params,
                                timeout=30,
                            ),
                        )
                    else:
                        logger.error("[ARCHIVER] Tokenni yangilash muvaffaqiyatsiz bo'ldi.")
                        break

                if response.status_code != 200:
                    logger.warning(f"[ARCHIVER] Leads HTTP xato: {response.status_code}")
                    break

                data = response.json()
                leads = data.get("_embedded", {}).get("leads", [])
                if not leads:
                    break

                for lead in leads:
                    status_id = lead.get("status_id")
                    if status_id not in (142, 143):
                        active_leads.append(lead)

                if len(leads) < limit:
                    break

                page += 1
            except Exception as e:
                logger.error(f"[ARCHIVER ERROR] Leads yuklashda xato (sahifa {page}): {e}")
                break

        logger.info(f"[ARCHIVER] Jami active bitimlar soni: {len(active_leads)}")
        return active_leads

    async def fetch_open_task_lead_ids(self) -> Set[int]:
        logger.info("[ARCHIVER] Vazifalarni tekshirish boshlandi...")
        open_lead_ids = set()
        limit = 250
        page = 1
        loop = asyncio.get_event_loop()

        while True:
            url = f"{self.amocrm.base_url}/api/v4/tasks"
            params = {
                "limit": limit,
                "page": page,
                "filter[is_completed]": 0,
            }
            try:
                response = await loop.run_in_executor(
                    None,
                    lambda: requests.get(
                        url,
                        headers=self.amocrm._get_headers(),
                        params=params,
                        timeout=30,
                    ),
                )

                if response.status_code == 401:
                    refreshed = await loop.run_in_executor(None, self.amocrm.refresh_token)
                    if refreshed:
                        response = await loop.run_in_executor(
                            None,
                            lambda: requests.get(
                                url,
                                headers=self.amocrm._get_headers(),
                                params=params,
                                timeout=30,
                            ),
                        )
                    else:
                        break

                if response.status_code != 200:
                    break

                data = response.json()
                tasks = data.get("_embedded", {}).get("tasks", [])
                if not tasks:
                    break

                for task in tasks:
                    entity_type = task.get("entity_type")
                    entity_id = task.get("entity_id")
                    if entity_type == "leads" and entity_id:
                        open_lead_ids.add(int(entity_id))

                if len(tasks) < limit:
                    break

                page += 1
            except Exception as e:
                logger.error(f"[ARCHIVER ERROR] Vazifalarni yuklashda xato (sahifa {page}): {e}")
                break

        logger.info(f"[ARCHIVER] Yopilmagan vazifaga ega bitimlar soni: {len(open_lead_ids)}")
        return open_lead_ids

    async def get_stagnant_leads(self, max_stagnant_days: int = 21) -> List[Dict[str, Any]]:
        active_leads = await self.fetch_all_active_leads()
        open_task_lead_ids = await self.fetch_open_task_lead_ids()

        stagnant_threshold = int(datetime.datetime.now().timestamp()) - (max_stagnant_days * 24 * 3600)
        stagnant_leads = []

        for lead in active_leads:
            lead_id = int(lead.get("id"))
            updated_at = int(lead.get("updated_at") or 0)
            if lead_id not in open_task_lead_ids and updated_at < stagnant_threshold:
                stagnant_leads.append(lead)

        stagnant_leads.sort(key=lambda x: x.get("updated_at", 0))
        logger.info(f"[ARCHIVER] Stagnatsiyadagi bitimlar aniqlandi: {len(stagnant_leads)}")
        return stagnant_leads

    async def fetch_contact_details(self, contact_id: int) -> Dict[str, Any]:
        url = f"{self.amocrm.base_url}/api/v4/contacts/{contact_id}"
        loop = asyncio.get_event_loop()
        try:
            response = await loop.run_in_executor(
                None,
                lambda: requests.get(
                    url,
                    headers=self.amocrm._get_headers(),
                    timeout=30,
                ),
            )
            if response.status_code == 200:
                data = response.json()
                name = data.get("name")
                phone = None
                fields = data.get("custom_fields_values", [])
                for field in fields:
                    if field.get("field_code") == "PHONE":
                        phone = field.get("values", [{}])[0].get("value")
                        break
                return {"name": name, "phone": phone, "raw": data}
            return {}
        except Exception as e:
            logger.error(f"[ARCHIVER ERROR] Kontakt yuklashda xato (ID {contact_id}): {e}")
            return {}

    async def generate_outreach_campaign(
        self,
        lead: Dict[str, Any],
        phone: str,
        contact_name: str,
        notes: List[Dict[str, Any]],
    ) -> Dict[str, str]:
        return await generate_outreach_campaign(lead, phone, contact_name, notes)

    async def archive_lead(self, lead: Dict[str, Any], dry_run: bool = True) -> Dict[str, Any]:
        lead_id = int(lead.get("id"))
        logger.info(f"[ARCHIVER] Bitim arxivlanmoqda {lead_id} ({lead.get('name')}) - Dry run: {dry_run}")

        contact_id = None
        contact_name = None
        phone = None
        contacts = lead.get("_embedded", {}).get("contacts", []) or []
        if contacts:
            contact_id = int(contacts[0].get("id"))
            contact_details = await self.fetch_contact_details(contact_id)
            contact_name = contact_details.get("name")
            phone = contact_details.get("phone")

        notes = await self.amocrm.get_lead_notes(lead_id)
        campaign = await self.generate_outreach_campaign(lead, phone, contact_name, notes)

        archive_payload = {
            "lead_id": lead_id,
            "name": lead.get("name"),
            "price": lead.get("price", 0),
            "status_id": lead.get("status_id"),
            "pipeline_id": lead.get("pipeline_id"),
            "responsible_user_id": lead.get("responsible_user_id"),
            "created_at": lead.get("created_at"),
            "updated_at": lead.get("updated_at"),
            "phone": phone,
            "contact_id": contact_id,
            "contact_name": contact_name,
            "notes": json.dumps(notes, ensure_ascii=False),
            "custom_fields": json.dumps(lead.get("custom_fields_values", []), ensure_ascii=False),
            "archived_at": datetime.datetime.now().isoformat(),
        }

        if not dry_run:
            await save_archived_lead_and_campaign(self.db, archive_payload, campaign)
            loop = asyncio.get_event_loop()
            status_updated = await self.amocrm.update_lead_status(lead_id, 143, lead.get("pipeline_id"))
            if not status_updated:
                logger.error(f"[ARCHIVER] {lead_id} bitimni Closed Lost qilishda HTTP xato.")
                return {"success": False, "lead_id": lead_id, "error": "AmoCRM status o'zgartirish xatosi"}

            await loop.run_in_executor(
                None,
                lambda: self.amocrm.add_lead_note(
                    lead_id,
                    "Oisha-OS: Bitim Turso bazasiga xavfsiz arxivlandi va faol limitsiz holatga (Closed Lost) o'tkazildi.",
                ),
            )

        return {
            "success": True,
            "lead_id": lead_id,
            "name": lead.get("name"),
            "phone": phone,
            "contact_name": contact_name,
            "campaign": campaign,
        }
