"""
Identity extraction, telegram profile cross-referencing, and note text parsing mixin.
"""
from __future__ import annotations

from collections import defaultdict
import logging
from typing import Any, Dict, Iterable, List, Optional, Set

from src.services.core.hygiene.models import (
    LeadIdentity,
    _safe_ts,
    extract_phones,
    extract_usernames,
    normalize_phone,
)

logger = logging.getLogger("AmoCRMDealHygiene")


class IdentityMixin:
    """Extracts lead identity markers and correlates with Telegram history."""

    async def _build_identity(
        self,
        lead: Dict[str, Any],
        telegram_profiles: Dict[str, List[Dict[str, Any]]],
    ) -> LeadIdentity:
        lead_id = int(lead["id"])
        notes = await self.amocrm.get_lead_notes(lead_id)
        note_text = self._notes_to_text(notes)
        identity = LeadIdentity(
            lead_id=lead_id,
            lead_name=lead.get("name") or f"Lead #{lead_id}",
            status_id=lead.get("status_id"),
            pipeline_id=lead.get("pipeline_id"),
            responsible_user_id=lead.get("responsible_user_id"),
            updated_at=_safe_ts(lead.get("updated_at")),
            note_text=note_text,
        )

        identity.phones.update(extract_phones(identity.lead_name))
        identity.phones.update(extract_phones(note_text))
        identity.telegram_usernames.update(extract_usernames(identity.lead_name))
        identity.telegram_usernames.update(extract_usernames(note_text))

        for contact_ref in lead.get("_embedded", {}).get("contacts", []) or []:
            contact_id = contact_ref.get("id")
            if not contact_id:
                continue
            identity.contact_ids.add(int(contact_id))
            contact = self.amocrm.get_contact_details(int(contact_id)) or {}
            contact_text = self._contact_to_text(contact)
            identity.phones.update(extract_phones(contact_text))
            identity.telegram_usernames.update(extract_usernames(contact_text))
            for phone in self._extract_contact_phones(contact):
                identity.phones.add(phone)

        for phone in list(identity.phones):
            for profile in telegram_profiles.get(f"phone:{phone}", []):
                self._merge_profile(identity, profile)

        for username in list(identity.telegram_usernames):
            for profile in telegram_profiles.get(f"username:{username}", []):
                self._merge_profile(identity, profile)

        return identity

    async def _load_telegram_profiles(self) -> Dict[str, List[Dict[str, Any]]]:
        profiles: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        if not self.db:
            return profiles

        try:
            conn = await self.db.get_connection()
            async with conn.execute(
                """
                SELECT user_id, first_name, last_name, username, phone, intent, role, detailed_role
                FROM users
                WHERE (phone IS NOT NULL AND phone != '')
                   OR (username IS NOT NULL AND username != '')
                """
            ) as cursor:
                rows = await cursor.fetchall()
                columns = [desc[0] for desc in cursor.description]
        except Exception as exc:
            logger.warning(f"[DEAL HYGIENE] Telegram profile load failed: {exc}")
            return profiles

        for row in rows:
            profile = dict(row) if isinstance(row, dict) else dict(zip(columns, row))
            phone = normalize_phone(profile.get("phone"))
            username = str(profile.get("username") or "").lstrip("@").lower()
            if phone:
                profiles[f"phone:{phone}"].append(profile)
            if username:
                profiles[f"username:{username}"].append(profile)
        return profiles

    async def _get_metasell_analysis(self, lead_id: int) -> Optional[Dict[str, Any]]:
        if not self.db or not hasattr(self.db, "get_latest_call_analysis"):
            return None
        try:
            return await self.db.get_latest_call_analysis(lead_id)
        except Exception as exc:
            logger.warning(f"[DEAL HYGIENE] MetaSell analysis fetch failed for {lead_id}: {exc}")
            return None

    def _notes_to_text(self, notes: Iterable[Dict[str, Any]]) -> str:
        parts: List[str] = []
        for note in notes or []:
            params = note.get("params") or {}
            text = params.get("text") or params.get("message") or ""
            if not text and params:
                text = " ".join(str(v) for v in params.values() if isinstance(v, (str, int, float)))
            if text:
                parts.append(str(text)[:1000])
        return "\n".join(parts[-30:])

    def _contact_to_text(self, contact: Dict[str, Any]) -> str:
        parts = [str(contact.get("name") or "")]
        for field in contact.get("custom_fields_values") or []:
            parts.append(str(field.get("field_name") or field.get("field_code") or ""))
            for value in field.get("values") or []:
                parts.append(str(value.get("value") or ""))
        return "\n".join(parts)

    def _extract_contact_phones(self, contact: Dict[str, Any]) -> Set[str]:
        phones: Set[str] = set()
        for field in contact.get("custom_fields_values") or []:
            if field.get("field_code") != "PHONE":
                continue
            for value in field.get("values") or []:
                normalized = normalize_phone(value.get("value"))
                if normalized:
                    phones.add(normalized)
        return phones

    def _merge_profile(self, identity: LeadIdentity, profile: Dict[str, Any]) -> None:
        try:
            identity.telegram_user_ids.add(int(profile["user_id"]))
        except (KeyError, TypeError, ValueError):
            pass
        username = str(profile.get("username") or "").lstrip("@").lower()
        if username:
            identity.telegram_usernames.add(username)
        phone = normalize_phone(profile.get("phone"))
        if phone:
            identity.phones.add(phone)

