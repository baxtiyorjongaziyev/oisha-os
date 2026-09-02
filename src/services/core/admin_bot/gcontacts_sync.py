"""
Google Contacts & Telegram synchronization mixin for AdminBot.
"""
from __future__ import annotations

import asyncio
from typing import Any, Dict, List
import structlog
from telethon import functions, types

logger = structlog.get_logger()


def _extract_phone_map(contacts: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    phone_to_contact = {}
    for c in contacts:
        for p in c.get("phones", []):
            clean_p = p.replace(" ", "").replace("-", "").replace("(", "").replace(")", "").lstrip("+")
            if clean_p:
                phone_to_contact[clean_p] = c
    return phone_to_contact


async def _import_and_match_tg_contacts(user_client: Any, phone_to_contact: Dict[str, Any]) -> Dict[str, Any]:
    matched_via_phone = {}
    phones_list = list(phone_to_contact.keys())
    batch_size = 100
    for i in range(0, len(phones_list), batch_size):
        batch = phones_list[i:i + batch_size]
        input_contacts = [
            types.InputPhoneContact(
                client_id=int(p[-9:]) if len(p) >= 9 else 0, phone="+" + p,
                first_name=phone_to_contact[p].get("given_name") or phone_to_contact[p].get("display_name") or "Mijoz",
                last_name=phone_to_contact[p].get("family_name") or "",
            )
            for p in batch
        ]
        try:
            res = await user_client(functions.contacts.ImportContactsRequest(contacts=input_contacts))
            for u in res.users:
                if u.phone and u.phone in phone_to_contact:
                    matched_via_phone[u.phone] = (u, phone_to_contact[u.phone])
        except Exception as exc:
            logger.error("[GCONTACTS_SYNC] Batch import error: %s", exc)
        await asyncio.sleep(1)
    return matched_via_phone


class AdminGContactsSyncMixin:
    """Mixin providing Google Contacts to Telegram user synchronization."""

    async def _run_gcontacts_telegram_sync(self, event: Any, wait_msg: Any) -> None:
        """Fon rejimida Google Kontaktlarni Telegram bilan sinxronizatsiya qiladi."""
        try:
            from src.services.core.google_contacts_service import GoogleContactsService
            contacts = GoogleContactsService().get_all_contacts(max_results=5000)
            if not contacts:
                await wait_msg.edit("❌ Google Contacts bo'sh yoki ulanishda xatolik yuz berdi.")
                return

            await wait_msg.edit(f"⏳ `{len(contacts)}` ta kontakt o'qildi. Telegram profillar qidirilmoqda...")
            phone_to_contact = _extract_phone_map(contacts)
            matched = await _import_and_match_tg_contacts(self.user_client, phone_to_contact)

            new_synced = 0
            for phone, (tg_user, g_contact) in matched.items():
                try:
                    await self.db.save_user(
                        user_id=tg_user.id, first_name=tg_user.first_name or "",
                        last_name=tg_user.last_name or "", username=tg_user.username or "",
                        phone="+" + phone,
                    )
                    new_synced += 1
                except Exception:
                    pass

            report = (
                f"✅ **Google Contacts Sinxronizatsiyasi Yakunlandi!**\n\n"
                f"🔹 **Jami Google Kontaktlar:** `{len(contacts)}` ta\n"
                f"🔸 **Telefon raqami borlar:** `{len(phone_to_contact)}` ta\n"
                f"🎯 **Telegramda topilganlar:** `{len(matched)}` ta\n"
                f"💾 **Bazaga yangi saqlanganlar:** `{new_synced}` ta"
            )
            await wait_msg.edit(report)
        except Exception as exc:
            logger.error("[GCONTACTS_SYNC] General error: %s", exc)
            await wait_msg.edit(f"⚠️ Xatolik yuz berdi: `{exc}`")
