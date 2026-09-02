"""
AmoCRM context fetching, lead notes/tasks collation, and formatting mixin.
"""
from __future__ import annotations

import json
import logging
import os
import time
from typing import Optional
import httpx


STATUS_IDS = {"won": 142, "lost": 143}
logger = logging.getLogger("SmartTaskCreator")


class ContextBuilderMixin:
    """Handles AmoCRM API auth, data extraction, and lead context formatting."""

    def _load_token(self) -> Optional[str]:
        """Token ni fayldan yuklash."""

        if not os.path.exists(self.token_file):
            return None

        try:
            with open(self.token_file, "r", encoding="utf-8-sig") as f:
                data = json.load(f)

            token = data.get("access_token")
            expires = data.get("expires_at", 0)

            if not token or time.time() > expires:
                return None

            self._token = token
            self._token_expires = expires
            return token

        except Exception as e:
            logger.error("[SMART_TASK] Token load error: %s", e)
            return None

    def _get_headers(self) -> dict:
        """API headerlari."""
        if not self._token or time.time() > self._token_expires:
            self._load_token()
        return {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }

    def get_lead_full(self, lead_id: int) -> dict:
        """Lead ning to'liq ma'lumotini olish — contacts, tags, notes."""
        try:
            # Lead + contacts + tags (bitta so'rov)
            resp = httpx.get(
                f"{self.base_url}/api/v4/leads/{lead_id}",
                params={"with": "contacts,tags"},
                headers=self._get_headers(),
                timeout=30,
            )
            if resp.status_code != 200:
                return {}
            lead = resp.json()

            # Notes (bitta so'rov)
            notes = []
            try:
                notes_resp = httpx.get(
                    f"{self.base_url}/api/v4/leads/{lead_id}/notes",
                    headers=self._get_headers(),
                    timeout=30,
                )
                if notes_resp.status_code == 200:
                    notes = notes_resp.json().get("_embedded", {}).get("notes", [])
            except Exception as exc:
                logger.debug("[SMART_TASK] Notes fetch failed for lead %d: %s", lead_id, exc)

            # Tasks (bitta so'rov)
            tasks = []
            try:
                tasks_resp = httpx.get(
                    f"{self.base_url}/api/v4/tasks",
                    params={
                        "filter[entity_id]:eq": lead_id,
                        "filter[entity_type]:eq": "leads",
                        "limit": 10,
                    },
                    headers=self._get_headers(),
                    timeout=30,
                )
                if tasks_resp.status_code == 200:
                    tasks = tasks_resp.json().get("_embedded", {}).get("tasks", [])
            except Exception as exc:
                logger.debug("[SMART_TASK] Tasks fetch failed for lead %d: %s", lead_id, exc)

            # Contact phones — faqat bitta contact uchun
            phones = []
            contacts = lead.get("_embedded", {}).get("contacts", [])
            if contacts:
                try:
                    c_resp = httpx.get(
                        f"{self.base_url}/api/v4/contacts/{contacts[0]['id']}",
                        headers=self._get_headers(),
                        timeout=30,
                    )
                    if c_resp.status_code == 200:
                        for cf in c_resp.json().get("custom_fields_values", []):
                            if cf.get("field_code") == "PHONE":
                                for v in cf.get("values", []):
                                    phones.append(v.get("value", ""))
                except Exception as exc:
                    logger.debug("[SMART_TASK] Contact phones fetch failed for lead %d: %s", lead_id, exc)

            return {
                "lead": lead,
                "notes": notes,
                "tasks": tasks,
                "phones": phones,
            }

        except Exception as e:
            logger.error("[SMART_TASK] Error getting lead %d: %s", lead_id, e)
            return {}

    def format_lead_context(self, data: dict) -> str:
        """Lead ma'lumotlarini AI uchun formatlash."""
        lead = data.get("lead", {})
        notes = data.get("notes", [])
        tasks = data.get("tasks", [])
        phones = data.get("phones", [])

        lines = []
        lines.append(f"LEAD: {lead.get('name', 'Nomalum')}")
        lines.append(f"ID: {lead.get('id')}")
        lines.append(f"Status ID: {lead.get('status_id')}")
        lines.append(f"Narx: {lead.get('price', 0)} so'm")
        lines.append(f"Yaratilgan: {lead.get('created_at')}")
        lines.append(f"Yangilangan: {lead.get('updated_at')}")

        # Tags
        tags = lead.get("_embedded", {}).get("tags", [])
        if tags:
            lines.append(f"Tags: {', '.join(t.get('name', '') for t in tags)}")

        # Phones
        if phones:
            lines.append(f"Telefonlar: {', '.join(phones)}")

        # Notes
        if notes:
            lines.append(f"\nCRM Yozuvlari ({len(notes)}):")
            for n in notes[-5:]:  # oxirgi 5 ta
                ntype = n.get("note_type", "common")
                params = n.get("params", {})
                text = params.get("text", "")
                if text:
                    lines.append(f"  [{ntype}]: {text[:300]}")

        # Tasks
        if tasks:
            lines.append(f"\nTasklar ({len(tasks)}):")
            for t in tasks[-3:]:  # oxirgi 3 ta
                completed = "YAKUNLANGAN" if t.get("is_completed") else "BAJARILMADI"
                lines.append(f"  [{completed}] {t.get('text', '')[:200]}")

        return "\n".join(lines)

    def get_status_name(self, status_id: int) -> str:
        """Status ID dan nom qaytarish."""
        for name, sid in STATUS_IDS.items():
            if sid == status_id:
                return name
        return f"unknown_{status_id}"
