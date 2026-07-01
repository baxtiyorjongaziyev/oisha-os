"""
sync_single_lead — TN5 Topic 7 dan yangi lead larni avtomatik sinxronizatsiya qilish.

Usage:
    from src.handlers.lead_sync import sync_single_lead
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from telethon import TelegramClient
    from telethon.events import NewMessage

logger = logging.getLogger(__name__)


async def sync_single_lead(
    event: "NewMessage.Event",
    *,
    client: "TelegramClient",
    lead_scraper: object,
    msg_controller: object,
    TN5_GROUP_ID: int,
) -> None:
    """Single leadni avtomatik tahlil qilish va qo'shish."""
    if not event.message.text:
        return

    try:
        data = await lead_scraper.parse_intro_with_ai(event.message.text)

        if not data or not data.get("is_relevant"):
            reason = data.get("relevance_reason") if data else "AI Xatosi"
            logger.info("🚫 [SKIP] Relevant emas: %s", reason)
            lead_scraper._mark_processed(
                event.id, TN5_GROUP_ID, status="irrelevant", reason=reason
            )
            return

        if data and data.get("phone"):
            phones = data.get("phone")
            if isinstance(phones, str):
                phones = [
                    p.strip()
                    for p in phones.replace(",", " ").replace("/", " ").split()
                    if p.strip()
                ]

            primary_phone = phones[0] if phones else None
            if not primary_phone:
                lead_scraper._mark_processed(
                    event.id, TN5_GROUP_ID, status="skipped", reason="No phone"
                )
                return

            sender = await event.get_sender()
            first_name = data.get("first_name")
            if not first_name or first_name.lower() == "unknown":
                first_name = getattr(sender, "first_name", None) or getattr(
                    sender, "username", "Unknown"
                )

            last_name = data.get("last_name") or getattr(sender, "last_name", "")

            full_name = lead_scraper.format_contact_name(
                first_name, last_name, is_tn5=True
            )
            bio = f"Biznes: {data.get('business', 'Noʻmalum')}\nEhtiyoj: {data.get('needs', 'Noʻmalum')}\n\n[AUTO-SYNCED]"

            await msg_controller.google.save_contact(full_name, phones, notes=bio)

            try:
                crm_sync = await msg_controller.crm.sync_lead(
                    user_id=event.sender_id,
                    name=full_name,
                    phone=primary_phone,
                    note=bio,
                )
                if crm_sync.get("success"):
                    logger.info("[ENTERPRISE] AmoCRM Lead created: %s", full_name)
                else:
                    logger.warning(
                        "[ENTERPRISE] AmoCRM Sync Error: %s", crm_sync.get("error")
                    )
            except Exception as amo_ex:
                logger.warning("[ENTERPRISE] AmoCRM Sync Error: %s", amo_ex)

            try:
                from telethon import functions

                await client(
                    functions.contacts.AddContactRequest(
                        id=event.sender_id,
                        first_name=full_name,
                        last_name="",
                        phone=primary_phone,
                        add_phone_privacy_exception=True,
                    )
                )
            except Exception as exc:
                logger.warning("TG Add Error: %s", exc)

            lead_scraper._mark_processed(event.id, TN5_GROUP_ID, status="synced")
            logger.info("✅ [ENTERPRISE SYNC OK] %s avtomatik qo'shildi!", full_name)
    except Exception as exc:
        logger.error("❌ [ENTERPRISE SYNC ERROR] %s", exc)
