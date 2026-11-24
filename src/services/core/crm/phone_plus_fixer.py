"""amoCRM kontaktlaridagi "+" siz telefon raqamlarini ommaviy tuzatadi.

Faqat 998 bilan boshlanuvchi 12 xonali (Oʻzbekiston) raqamlar "+998..." ga
oʻgirilib PATCH qilinadi; boshqa formatlarga tegilmaydi.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

_UZ_BARE = re.compile(r"^998\d{9}$")
PAGE_LIMIT = 250
PATCH_BATCH = 50


def fix_phone_value(value: Any) -> Optional[str]:
    """Return "+998..." if value is a bare Uzbek number, else None."""
    raw = str(value or "").strip()
    if raw.startswith("+"):
        return None
    digits = re.sub(r"\D+", "", raw)
    if not _UZ_BARE.match(digits):
        return None
    return f"+{digits}"


def build_contact_patch(contact: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Build PATCH body for one contact, or None if nothing to fix."""
    for field in contact.get("custom_fields_values") or []:
        if str(field.get("field_code") or "").upper() != "PHONE":
            continue
        values = field.get("values") or []
        changed = False
        new_values: List[Dict[str, Any]] = []
        for item in values:
            fixed = fix_phone_value(item.get("value"))
            entry: Dict[str, Any] = {"value": fixed or item.get("value")}
            if item.get("enum_code"):
                entry["enum_code"] = item["enum_code"]
            elif item.get("enum_id"):
                entry["enum_id"] = item["enum_id"]
            new_values.append(entry)
            changed = changed or bool(fixed)
        if not changed:
            return None
        cf: Dict[str, Any] = {"values": new_values}
        if field.get("field_id"):
            cf["field_id"] = field["field_id"]
        else:
            cf["field_code"] = "PHONE"
        return {"id": int(contact["id"]), "custom_fields_values": [cf]}
    return None


async def fix_contact_phones(crm: Any, *, max_pages: int = 400, dry_run: bool = False) -> int:
    """Scan all contacts newest-first and fix bare phones. Returns fixed count."""
    patches: List[Dict[str, Any]] = []
    for page in range(1, max_pages + 1):
        resp = await crm._request_with_auth(
            requests.get,
            f"{crm.base_url}/api/v4/contacts",
            params={"limit": PAGE_LIMIT, "page": page, "order[updated_at]": "desc"},
            timeout=30,
        )
        if resp.status_code != 200:
            break
        contacts = ((resp.json() or {}).get("_embedded") or {}).get("contacts") or []
        for contact in contacts:
            patch = build_contact_patch(contact)
            if patch:
                patches.append(patch)
        if len(contacts) < PAGE_LIMIT:
            break

    if dry_run or not patches:
        logger.info("[PHONE-PLUS] %s kontakt tuzatishga loyiq (dry_run=%s)", len(patches), dry_run)
        return len(patches)

    fixed = 0
    for i in range(0, len(patches), PATCH_BATCH):
        batch = patches[i:i + PATCH_BATCH]
        resp = await crm._request_with_auth(
            requests.patch, f"{crm.base_url}/api/v4/contacts", json=batch, timeout=30
        )
        if resp.status_code in (200, 202):
            fixed += len(batch)
        else:
            logger.error("[PHONE-PLUS] PATCH %s: %s", resp.status_code, resp.text[:200])
    logger.info("[PHONE-PLUS] %s kontakt raqami tuzatildi", fixed)
    return fixed
