"""CRM adapters (amoCRM + Airtable) for unified 5-system client sync."""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from src.services.core.crm.amocrm.phone_format import normalize_amocrm_phone

from .models import UnifiedClientProfile, split_full_name

logger = logging.getLogger(__name__)


def _extract_amocrm_field(contact: Dict[str, Any], code: str) -> str:
    for cf in contact.get("custom_fields_values") or []:
        if str(cf.get("field_code") or "").upper() == code.upper():
            vals = cf.get("values") or []
            if vals and vals[0].get("value"):
                return str(vals[0]["value"]).strip()
    return ""


def profile_from_amocrm_contact(
    contact: Dict[str, Any],
    *,
    lead_id: Optional[int] = None,
    stage: str = "",
    company: str = "",
) -> Optional[UnifiedClientProfile]:
    """Convert an amoCRM contact payload into a canonical UnifiedClientProfile."""
    raw_phone = _extract_amocrm_field(contact, "PHONE")
    phone = normalize_amocrm_phone(raw_phone)
    if not phone:
        return None
    first, last = split_full_name(str(contact.get("name") or ""))
    tags = [
        str(t.get("name") or "").strip()
        for t in (contact.get("_embedded") or {}).get("tags") or []
        if isinstance(t, dict) and t.get("name")
    ]
    return UnifiedClientProfile(
        phone=phone,
        first_name=first,
        last_name=last,
        telegram_username=_extract_amocrm_field(contact, "TELEGRAM_LOGIN"),
        company=company or _extract_amocrm_field(contact, "COMPANY"),
        activity=_extract_amocrm_field(contact, "POSITION"),
        stage=stage,
        source="amoCRM",
        tags=tags,
        amocrm_contact_id=int(contact["id"]) if contact.get("id") else None,
        amocrm_lead_id=lead_id,
    )


def profile_from_airtable_record(record: Dict[str, Any]) -> Optional[UnifiedClientProfile]:
    """Convert an Airtable client/project record into a UnifiedClientProfile."""
    fields = record.get("fields") or {}
    raw_phone = (
        fields.get("Telefon")
        or fields.get("Phone")
        or fields.get("Mijoz telefoni")
        or ""
    )
    phone = normalize_amocrm_phone(raw_phone)
    if not phone:
        return None
    raw_name = (
        fields.get("Mijoz")
        or fields.get("Mijoz ismi")
        or fields.get("Ism")
        or fields.get("Client")
        or ""
    )
    first, last = split_full_name(str(raw_name))
    raw_tags = fields.get("Teglar") or fields.get("Tags") or []
    tags = [str(t) for t in raw_tags] if isinstance(raw_tags, list) else [str(raw_tags)]
    return UnifiedClientProfile(
        phone=phone,
        first_name=first,
        last_name=last,
        telegram_username=str(fields.get("Telegram") or fields.get("Telegram @username") or ""),
        company=str(fields.get("Brend") or fields.get("Kompaniya") or fields.get("Loyiha") or ""),
        activity=str(fields.get("Soha") or fields.get("Faoliyat sohasi") or ""),
        region=str(fields.get("Hudud") or fields.get("Shahar") or ""),
        stage=str(fields.get("Bosqich") or fields.get("Status") or ""),
        source="Airtable",
        tags=tags,
        airtable_record_id=str(record.get("id") or ""),
        notes=str(fields.get("Izoh") or ""),
    )


class AmoCRMUnifiedAdapter:
    """Non-destructive amoCRM contact updater (always writes +998XXXXXXXXX)."""

    name = "amocrm"

    def __init__(self, amo_client: Any) -> None:
        self.amo = amo_client

    def sync_profile(self, profile: UnifiedClientProfile, *, dry_run: bool = True) -> str:
        if not profile.phone:
            return "skipped"
        if dry_run:
            return "would_update" if profile.amocrm_contact_id else "would_create"
        if profile.amocrm_contact_id:
            ok = bool(self.amo.update_contact_phone(profile.full_name, profile.phone))
            return "updated" if ok else "failed"
        cid = self.amo.create_contact(profile.full_name, profile.phone)
        if cid:
            profile.amocrm_contact_id = int(cid)
            return "created"
        return "failed"


class AirtableUnifiedAdapter:
    """Non-destructive Airtable client record syncer."""

    name = "airtable"

    def __init__(self, airtable_client: Any, *, table_name: str = "Mijozlar") -> None:
        self.client = airtable_client
        self.table_name = table_name

    def build_fields(self, profile: UnifiedClientProfile) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "Ism": profile.full_name,
            "Telefon": profile.phone,
        }
        if profile.telegram_username:
            payload["Telegram"] = f"@{profile.telegram_username}"
        if profile.company:
            payload["Kompaniya"] = profile.company
        if profile.activity:
            payload["Soha"] = profile.activity
        if profile.region:
            payload["Hudud"] = profile.region
        if profile.stage:
            payload["Bosqich"] = profile.stage
        return payload

    def sync_profile(self, profile: UnifiedClientProfile, *, dry_run: bool = True) -> str:
        if not profile.phone:
            return "skipped"
        if dry_run:
            return "would_update" if profile.airtable_record_id else "would_create"
        fields = self.build_fields(profile)
        if profile.airtable_record_id and hasattr(self.client, "update_record"):
            ok = bool(self.client.update_record(self.table_name, profile.airtable_record_id, fields))
            return "updated" if ok else "failed"
        if hasattr(self.client, "create_record"):
            rec = self.client.create_record(self.table_name, fields)
            if isinstance(rec, dict) and rec.get("id"):
                profile.airtable_record_id = str(rec["id"])
                return "created"
            return "created" if rec else "failed"
        return "skipped"
