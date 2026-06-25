"""Avtomatik task yaratish — 'Birinchi kontakt' statusidagi leadlarga follow-up task.

24/7 ishlaydi, BackgroundMonitor dan chaqiriladi.
"""

from __future__ import annotations

import time
import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

# Pipeline va status ID lari
PIPELINE_ID = 10117998
FIRST_CONTACT_STATUS = 86076798  # "Birinchi kontakt qilindi"
OWNER_ID = 13021974  # Baxtiyorjon

# Follow-up task text patterns
TASK_TEXT_CALL = "Qayta qo'ng'iroq qilish - {name} ({phone})"
TASK_TEXT_SMS = "SMS yuborish - {name} ({phone})"


class AutoTaskCreator:
    """Birinchi kontakt statusidagi leadlarga avtomatik task yaratadi."""

    def __init__(self, token_file: str = "data/amocrm_token.json"):
        self.token_file = token_file
        self.base_url = "https://jonbrandingagency.amocrm.ru"
        self._token: Optional[str] = None
        self._token_expires: float = 0

    def _load_token(self) -> Optional[str]:
        """Token ni fayldan yuklash."""
        import json
        import os

        if not os.path.exists(self.token_file):
            logger.error("[AUTO_TASK] Token file not found: %s", self.token_file)
            return None

        try:
            with open(self.token_file, "r", encoding="utf-8-sig") as f:
                data = json.load(f)

            token = data.get("access_token")
            expires = data.get("expires_at", 0)

            if not token:
                return None

            if time.time() > expires:
                logger.warning("[AUTO_TASK] Token expired at %s", expires)
                return None

            self._token = token
            self._token_expires = expires
            return token

        except Exception as e:
            logger.error("[AUTO_TASK] Token load error: %s", e)
            return None

    def _get_headers(self) -> dict:
        """API headerlari."""
        if not self._token or time.time() > self._token_expires:
            self._load_token()
        return {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }

    def get_first_contact_leads(self) -> list[dict]:
        """'Birinchi kontakt' statusidagi barcha leadlarni olish."""
        try:
            resp = httpx.get(
                f"{self.base_url}/api/v4/leads",
                params={
                    "filter[statuses][0][pipeline_id]:eq": PIPELINE_ID,
                    "filter[statuses][0][status_id]:eq": FIRST_CONTACT_STATUS,
                    "limit": 250,
                },
                headers=self._get_headers(),
                timeout=15,
            )

            if resp.status_code == 200:
                leads = resp.json().get("_embedded", {}).get("leads", [])
                logger.info("[AUTO_TASK] Found %d leads in first contact status", len(leads))
                return leads
            else:
                logger.error("[AUTO_TASK] Failed to get leads: %s", resp.status_code)
                return []

        except Exception as e:
            logger.error("[AUTO_TASK] Error getting leads: %s", e)
            return []

    def get_lead_tasks(self, lead_id: int) -> list[dict]:
        """Lead uchun barcha tasklarni olish."""
        try:
            resp = httpx.get(
                f"{self.base_url}/api/v4/tasks",
                params={
                    "filter[entity_id]:eq": lead_id,
                    "filter[entity_type]:eq": "leads",
                    "limit": 50,
                },
                headers=self._get_headers(),
                timeout=15,
            )

            if resp.status_code == 200:
                return resp.json().get("_embedded", {}).get("tasks", [])
            return []

        except Exception as e:
            logger.error("[AUTO_TASK] Error getting tasks for lead %d: %s", lead_id, e)
            return []

    def get_lead_contacts(self, lead_id: int) -> list[dict]:
        """Lead uchun kontaktlarni olish."""
        try:
            resp = httpx.get(
                f"{self.base_url}/api/v4/leads/{lead_id}",
                params={"with": "contacts"},
                headers=self._get_headers(),
                timeout=15,
            )

            if resp.status_code == 200:
                return resp.json().get("_embedded", {}).get("contacts", [])
            return []

        except Exception as e:
            logger.error("[AUTO_TASK] Error getting contacts for lead %d: %s", lead_id, e)
            return []

    def get_contact_phone(self, contact_id: int) -> str:
        """Kontakt telefon raqamini olish."""
        try:
            resp = httpx.get(
                f"{self.base_url}/api/v4/contacts/{contact_id}",
                headers=self._get_headers(),
                timeout=15,
            )

            if resp.status_code == 200:
                for cf in resp.json().get("custom_fields_values", []):
                    if cf.get("field_code") == "PHONE":
                        values = cf.get("values", [])
                        if values:
                            return values[0].get("value", "")
            return ""

        except Exception as e:
            logger.error("[AUTO_TASK] Error getting phone for contact %d: %s", contact_id, e)
            return ""

    def create_task(
        self,
        lead_id: int,
        text: str,
        task_type: str = "call",
        complete_till: Optional[int] = None,
    ) -> Optional[int]:
        """AmoCRM ga task yaratish."""
        if complete_till is None:
            # Default: 24 soat ichida
            complete_till = int(time.time()) + 86400

        task_data = {
            "text": text,
            "entity_id": lead_id,
            "entity_type": "leads",
            "complete_till": complete_till,
            "responsible_user_id": OWNER_ID,
            "params": {"type": task_type},
        }

        try:
            resp = httpx.post(
                f"{self.base_url}/api/v4/tasks",
                headers=self._get_headers(),
                json=[task_data],
                timeout=15,
            )

            if resp.status_code in (200, 201):
                tasks = resp.json().get("_embedded", {}).get("tasks", [])
                if tasks:
                    task_id = tasks[0].get("id")
                    logger.info("[AUTO_TASK] Created task %d for lead %d", task_id, lead_id)
                    return task_id
            else:
                logger.error(
                    "[AUTO_TASK] Failed to create task: %s %s",
                    resp.status_code,
                    resp.text[:200],
                )
            return None

        except Exception as e:
            logger.error("[AUTO_TASK] Error creating task: %s", e)
            return None

    def needs_followup(self, lead: dict, existing_tasks: list[dict]) -> bool:
        """Lead ga follow-up task kerakmi?"""
        now = int(time.time())

        # Agar allaqachon yakunlanmagan task bo'lsa — kerak emas
        for t in existing_tasks:
            if not t.get("is_completed", False):
                return False

        # Agar oxirgi task 48 soatdan oldin tugagan bo'lsa — kerak
        for t in existing_tasks:
            if t.get("is_completed", False):
                completed_at = t.get("completed_at", 0)
                if completed_at and (now - completed_at) < 172800:  # 48 hours
                    return False

        return True

    def process_leads(self, dry_run: bool = False) -> dict:
        """Barcha birinchi kontakt leadlarni qayta ishlash."""
        stats = {
            "total_leads": 0,
            "needs_followup": 0,
            "tasks_created": 0,
            "errors": 0,
        }

        leads = self.get_first_contact_leads()
        stats["total_leads"] = len(leads)

        for lead in leads:
            lead_id = lead["id"]
            lead_name = lead.get("name", "Unknown")

            try:
                # Tasklarni tekshirish
                existing_tasks = self.get_lead_tasks(lead_id)

                if not self.needs_followup(lead, existing_tasks):
                    continue

                stats["needs_followup"] += 1

                # Kontaktni olish
                contacts = self.get_lead_contacts(lead_id)
                phone = ""
                for c in contacts:
                    phone = self.get_contact_phone(c["id"])
                    if phone:
                        break

                # Task matnini shakllantirish
                task_text = TASK_TEXT_CALL.format(name=lead_name, phone=phone or "raqam yo'q")

                if dry_run:
                    logger.info("[AUTO_TASK][DRY] Would create: %s", task_text)
                    stats["tasks_created"] += 1
                    continue

                # Task yaratish
                task_id = self.create_task(lead_id, task_text, task_type="call")
                if task_id:
                    stats["tasks_created"] += 1
                else:
                    stats["errors"] += 1

            except Exception as e:
                logger.error("[AUTO_TASK] Error processing lead %d: %s", lead_id, e)
                stats["errors"] += 1

        logger.info(
            "[AUTO_TASK] Done: %d leads, %d need followup, %d tasks created, %d errors",
            stats["total_leads"],
            stats["needs_followup"],
            stats["tasks_created"],
            stats["errors"],
        )

        return stats


# Singleton
_creator: Optional[AutoTaskCreator] = None


def get_auto_task_creator() -> AutoTaskCreator:
    """AutoTaskCreator singleton."""
    global _creator
    if _creator is None:
        _creator = AutoTaskCreator()
    return _creator


async def run_auto_task_creation(dry_run: bool = False) -> dict:
    """BackgroundMonitor dan chaqiriladi."""
    creator = get_auto_task_creator()
    return creator.process_leads(dry_run=dry_run)


if __name__ == "__main__":
    import sys
    import asyncio
    sys.stdout.reconfigure(encoding="utf-8")
    dry = "--dry-run" in sys.argv
    stats = asyncio.run(run_auto_task_creation(dry_run=dry))
    print(f"Stats: {stats}")
