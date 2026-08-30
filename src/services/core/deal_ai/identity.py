"""
Identity extraction and Telegram message sampling.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any, Dict, List, Optional

from src.services.core.deal_ai.models import PHONE_RE, USERNAME_RE

logger = logging.getLogger(__name__)


async def gather_identity(amocrm: Any, tg_client: Any, lead: Dict[str, Any]) -> Dict[str, Any]:
    text = lead.get("name") or ""
    phone: Optional[str] = None
    username: Optional[str] = None
    contact_id: Optional[int] = None

    try:
        notes = await amocrm.get_lead_notes(int(lead["id"]))
    except Exception:
        logger.error("Exception handled in %s", __name__, exc_info=True)
        notes = []
    notes_text = " ".join(
        str((n.get("params") or {}).get("text") or "") for n in (notes or [])
    )

    contacts_ref = (lead.get("_embedded", {}).get("contacts") or [])
    if contacts_ref:
        contact_id = int(contacts_ref[0].get("id") or 0) or None

    contact_text = ""
    if contact_id:
        contact = await asyncio.to_thread(
            amocrm.get_contact_details, contact_id
        ) or {}
        contact_text = json.dumps(contact, ensure_ascii=False)[:5000]
        for field in contact.get("custom_fields_values") or []:
            if field.get("field_code") == "PHONE":
                for value in field.get("values") or []:
                    digits = re.sub(r"\D+", "", str(value.get("value") or ""))
                    if len(digits) >= 9:
                        phone = digits
                        break

    corpus = "\n".join([text, notes_text, contact_text])
    for match in USERNAME_RE.finditer(corpus):
        candidate = match.group(1).lower()
        if 5 <= len(candidate) <= 32 and candidate not in ("gmail", "outlook"):
            username = candidate
            break
    if not phone:
        for match in PHONE_RE.finditer(corpus):
            digits = re.sub(r"\D+", "", match.group(0))
            if len(digits) >= 9:
                phone = digits
                break

    user_id: Optional[int] = None
    if (username or phone) and tg_client:
        try:
            from telethon.tl import types
            target = username or ("+" + phone if phone else None)
            if target:
                entity = await tg_client.get_entity(target)
                if isinstance(entity, types.User):
                    user_id = int(entity.id)
                    if not username and getattr(entity, "username", None):
                        username = entity.username.lower()
                    if not phone and getattr(entity, "phone", None):
                        phone = re.sub(r"\D+", "", entity.phone)
        except Exception as exc:
            logger.debug(f"[DEAL AI] get_entity skip: {exc}")

    return {
        "phone": phone,
        "username": username,
        "user_id": user_id,
        "contact_id": contact_id,
        "corpus_snippet": corpus[:1200],
    }


async def fetch_telegram_messages(
    tg_client: Any, identity: Dict[str, Any], message_window: int = 30
) -> List[Dict[str, Any]]:
    if not tg_client:
        return []
    target = identity.get("user_id") or identity.get("username")
    if not target and identity.get("phone"):
        target = "+" + identity["phone"]
    if not target:
        return []
    try:
        messages: List[Dict[str, Any]] = []
        async for msg in tg_client.iter_messages(target, limit=message_window):
            if not msg or not getattr(msg, "text", None):
                continue
            messages.append(
                {
                    "date": msg.date.isoformat() if msg.date else None,
                    "out": bool(msg.out),
                    "text": str(msg.text)[:600],
                }
            )
        messages.reverse()
        return messages
    except Exception as exc:
        logger.debug(f"[DEAL AI] iter_messages skip ({target}): {exc}")
        return []
