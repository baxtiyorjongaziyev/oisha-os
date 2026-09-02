"""
Telegram group topic and member scraping into AmoCRM contacts mixin.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any



logger = logging.getLogger("LeadScraper")

CYRILLIC_TO_LATIN = {
    "А": "A", "Б": "B", "В": "V", "Г": "G", "Д": "D", "Е": "E", "Ё": "Yo", "Ж": "J", "З": "Z", "И": "I",
    "Й": "Y", "К": "K", "Л": "L", "М": "M", "Н": "N", "О": "O", "П": "P", "Р": "R", "С": "S", "Т": "T",
    "У": "U", "Ф": "F", "Х": "X", "Ц": "Ts", "Ч": "Ch", "Ш": "Sh", "Щ": "Sh", "Ъ": "", "Ы": "I", "Ь": "",
    "Э": "E", "Ю": "Yu", "Я": "Ya", "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "yo",
    "ж": "j", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m", "n": "n", "о": "o", "п": "p",
    "р": "r", "с": "s", "т": "t", "у": "u", "ф": "f", "х": "x", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sh",
    "ъ": "", "ы": "i", "ь": "", "э": "e", "ю": "yu", "я": "ya", "ў": "o'", "қ": "q", "ғ": "g'", "ҳ": "h",
    "Ў": "O'", "Қ": "Q", "Ғ": "G'", "Ҳ": "H",
}


def _to_latin(text: str) -> str:
    for cyr, lat in CYRILLIC_TO_LATIN.items():
        text = text.replace(cyr, lat)
    return text


class GroupSyncMixin:
    """Handles Telegram group/topic scraping and AmoCRM syncing."""

    async def sync_topic_to_contacts(
        self, client: Any, group_id: int, topic_id: int, limit: int = 50
    ):
        """Muayyan topickdagi barcha xabarlardan lidlarni qidirib topish va saqlash."""
        logger.info(f"[SCRAPER] {group_id}:{topic_id} topigini tahlili boshlandi... 👸🛡️")
        async for message in client.iter_messages(group_id, reply_to=topic_id, limit=limit):
            if not message.text or await self._is_processed(message.id):
                continue
            lead_data = await self.parse_intro_with_ai(message.text)
            if lead_data and lead_data.get("phone"):
                full_name = f"{lead_data.get('name', 'Client')} TN5"
                phones = [lead_data.get("phone")]
                try:
                    await self.google.save_contact(
                        name=full_name, phones=phones,
                        notes=f"Lid from TG Topic: {topic_id}\nOriginal: {message.text[:100]}",
                        group_name="TEZ NATIJA 5",
                    )
                    self._mark_processed(message.id, group_id, status="saved")
                except Exception as exc:
                    logger.error("[SCRAPER] Topic save failed: %s", exc)

    async def _sync_single_member(self, user: Any, prefix: str, group_label: str, client: Any) -> bool:
        phone = getattr(user, "phone", None)
        name = getattr(user, "first_name", "") or ""
        surname = getattr(user, "last_name", "") or ""
        username = getattr(user, "username", "") or ""
        full_name = _to_latin(f"{name} {surname}".strip() or username or f"User {user.id}")

        name_parts = full_name.split(maxsplit=1)
        first_name = name_parts[0] if name_parts else "Unknown"
        display_last_name = f"{name_parts[1] if len(name_parts) > 1 else ''} {prefix}".strip()
        phones = [phone if phone.startswith("+") else f"+{phone}"] if phone else []

        try:
            if await self.db.get_user_info(user.id):
                return False
            await self.db.save_user(
                user_id=user.id, first_name=first_name, last_name=display_last_name,
                username=username, phone=phones[0] if phones else "",
            )
            if phones:
                await self.google.save_contact(
                    name=f"{first_name} {display_last_name}", phones=phones,
                    notes=f"Telegram ID: {user.id}\nUsername: @{username}", group_name=group_label,
                )
            return True
        except Exception as exc:
            logger.error("[MASS SYNC] User save error: %s", exc)
            return False

    async def sync_all_group_members(
        self,
        client: Any,
        group_id: int,
        limit: int = 50,
        no_phone_only: bool = False,
        group_label: str = "TEZ NATIJA 5",
        prefix: str = "TN5",
    ):
        """Ommaiy tarzda guruhdagi barcha a'zolarni to'g'ridan-to'g'ri saqlash."""
        logger.info(f"[MASS SYNC] {group_label} ({group_id}) skanerlash boshlandi...")
        saved_count = 0
        try:
            async for user in client.iter_participants(group_id):
                if user.bot or user.deleted:
                    continue
                if saved_count >= limit:
                    break
                if await self._is_processed(user.id * -1):
                    continue
                if no_phone_only and getattr(user, "phone", None):
                    continue

                if await self._sync_single_member(user, prefix, group_label, client):
                    saved_count += 1
                self._mark_processed(user.id * -1, group_id, status="saved")
                await asyncio.sleep(0.5)
        except Exception as exc:
            logger.error("[MASS SYNC] Iteration failed: %s", exc)
