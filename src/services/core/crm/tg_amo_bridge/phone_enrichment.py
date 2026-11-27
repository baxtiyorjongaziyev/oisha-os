"""Enrich an existing amoCRM contact card with a phone number shared in chat context."""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from .analyzer import contact_phones, is_internal_team_phone, normalize_uz_phone

logger = logging.getLogger("TgAmoBridge.phone_enrichment")


def _matches_username(contact: Dict[str, Any], username: str) -> bool:
    needle = username.lstrip("@").strip().lower()
    if len(needle) < 4:
        return False
    if needle in str(contact.get("name") or "").lower():
        return True
    for fld in contact.get("custom_fields_values") or []:
        for val in fld.get("values") or []:
            text = str(val.get("value") or "").lower()
            if f"@{needle}" in text or f"t.me/{needle}" in text or text.strip("@ ") == needle:
                return True
    return False


async def _find_existing_contact_id(
    crm: Any,
    *,
    cached: Optional[dict],
    amo_chat_id: Optional[str],
    username: Optional[str],
) -> tuple[Optional[int], Optional[int]]:
    """Locate the amoCRM contact already bound to this Telegram chat (even without a phone)."""
    cached_cid = int((cached or {}).get("linked_contact_id") or 0)
    cached_lid = int((cached or {}).get("linked_lead_id") or 0) or None
    if cached_cid > 0:
        return cached_cid, cached_lid

    if amo_chat_id and hasattr(crm, "get_contact_chats"):
        links = await crm.get_contact_chats(chat_id=amo_chat_id)
        for item in links or []:
            cid = int(item.get("contact_id") or 0)
            if cid > 0:
                lid = (
                    int(item.get("entity_id") or 0)
                    if str(item.get("entity_type") or "").lower() == "lead"
                    else cached_lid
                )
                return cid, (lid or cached_lid)

    if username and hasattr(crm, "find_contacts_by_query_async"):
        contacts = await crm.find_contacts_by_query_async(username.lstrip("@"))
        for contact in contacts or []:
            if _matches_username(contact, username) and contact.get("id"):
                leads = (contact.get("_embedded") or {}).get("leads") or []
                lid = int(leads[0]["id"]) if leads and leads[0].get("id") else cached_lid
                return int(contact["id"]), lid

    return None, cached_lid


async def enrich_contact_phone_from_context(
    crm: Any,
    store: Any,
    *,
    peer_id: int,
    phone: str,
    phone_source: str,
    cached: Optional[dict],
    amo_chat_id: Optional[str],
    username: Optional[str],
    client_name: str,
    dry_run: bool = False,
) -> tuple[bool, Optional[int], Optional[int]]:
    """Write a chat-shared phone number into the existing amoCRM contact card.

    Returns (updated, contact_id, lead_id).
    """
    norm = normalize_uz_phone(phone)
    if not norm or is_internal_team_phone(norm):
        return False, None, None
    if not hasattr(crm, "add_phone_to_contact_async"):
        return False, None, None

    contact_id, lead_id = await _find_existing_contact_id(
        crm, cached=cached, amo_chat_id=amo_chat_id, username=username
    )
    if not contact_id:
        return False, None, None

    if hasattr(crm, "get_contact_details_async"):
        details = await crm.get_contact_details_async(contact_id)
        if details and norm in contact_phones(details):
            await store.upsert_chat_link(
                peer_id,
                amo_chat_id=amo_chat_id,
                phone=norm,
                username=username,
                linked_contact_id=contact_id,
                linked_lead_id=lead_id,
            )
            return True, contact_id, lead_id

    if dry_run:
        return True, contact_id, lead_id

    formatted = f"+{norm}"
    updated = await crm.add_phone_to_contact_async(contact_id, formatted)
    if not updated:
        return False, contact_id, lead_id

    await store.upsert_chat_link(
        peer_id,
        amo_chat_id=amo_chat_id,
        phone=norm,
        username=username,
        linked_contact_id=contact_id,
        linked_lead_id=lead_id,
    )
    if lead_id and hasattr(crm, "add_lead_note_async"):
        note = (
            "Suhbat kontekstidan telefon raqami avtomatik aniqlandi va "
            f"kontakt kartochkasiga qoʻshildi: {formatted} "
            f"(manba: {phone_source}, mijoz: {client_name}, tg_id: {peer_id})."
        )
        await crm.add_lead_note_async(lead_id, note)

    logger.info(
        "[TG-AMO] Enriched contact %s with chat phone (source=%s, peer_id=%s)",
        contact_id,
        phone_source,
        peer_id,
    )
    return True, contact_id, lead_id
