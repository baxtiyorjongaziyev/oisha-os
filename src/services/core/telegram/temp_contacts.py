"""Temporary Telegram contacts used to resolve a phone number to a user.

Telegram only lets a userbot reach a phone number after importing it as a
contact. Every import must be undone, otherwise the owner's address book fills
up with "Oisha Lookup" entries.
"""

from __future__ import annotations

import asyncio
import logging
import random
from typing import Any, Optional

logger = logging.getLogger(__name__)

TEMP_CONTACT_NAME = "Oisha Lookup"


async def import_temp_contact(client: Any, phone: str) -> tuple[Any, bool]:
    """Import ``phone`` as a temporary contact.

    Returns ``(user, newly_imported)``. ``newly_imported`` is False when the
    number was already in the address book, so the caller must not delete it.
    """
    from telethon.tl import functions, types

    contact = types.InputPhoneContact(
        client_id=random.randrange(-(2**63), 2**63),
        phone=phone.replace("+", ""),
        first_name=TEMP_CONTACT_NAME,
        last_name="",
    )
    result = await client(functions.contacts.ImportContactsRequest(contacts=[contact]))
    users = list(getattr(result, "users", None) or [])
    if not users:
        return None, False
    imported = getattr(result, "imported", None)
    # Older mocks/clients may not expose ``imported``; treat that as new.
    newly_imported = True if imported is None else bool(imported)
    return users[0], newly_imported


async def delete_temp_contact(
    client: Any, user_id: Optional[int], *, attempts: int = 3, delay: float = 1.0
) -> bool:
    """Delete a temporary contact, retrying transient failures."""
    if not user_id:
        return True
    from telethon.tl import functions

    for attempt in range(1, attempts + 1):
        try:
            await client(functions.contacts.DeleteContactsRequest(id=[int(user_id)]))
            return True
        except Exception as exc:
            if attempt == attempts:
                logger.warning(
                    "[TEMP_CONTACT] Could not delete temporary contact %s: %s",
                    user_id,
                    exc,
                )
                return False
            await asyncio.sleep(delay * attempt)
    return False
