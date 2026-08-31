"""
AmoCRM export mixin for Tez Natija members.
"""
from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Optional

from src.time_utils import get_local_now
from src.services.core.tez_natija.sheets_exporter import TEZ_NATIJA_GROUPS

if TYPE_CHECKING:
    from telethon import TelegramClient

logger = logging.getLogger(__name__)

_AMO_PIPELINE_ID = 10117998
_AMO_STATUS_ID = 80178230
_AMO_DELAY = 0.4


class TezNatijaAmoCRMMixin:
    """AmoCRM export mixin for Tez Natija leads."""

    async def _ensure_amo_state_table(self):
        if self.db is None:
            return
        async with await self.db.get_connection() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS tez_natija_amocrm_export (
                    telegram_id INTEGER PRIMARY KEY,
                    lead_id INTEGER,
                    group_name TEXT,
                    exported_at TEXT
                )
            """)
            await conn.commit()

    async def _amo_already_exported(self, telegram_id: int) -> bool:
        if self.db is None:
            return False
        async with await self.db.get_connection() as conn:
            row = await (await conn.execute(
                "SELECT 1 FROM tez_natija_amocrm_export WHERE telegram_id = ?",
                (telegram_id,),
            )).fetchone()
            return row is not None

    async def _amo_mark_exported(
        self, telegram_id: int, lead_id: Optional[int], group_name: str
    ):
        if self.db is None:
            return
        now = get_local_now().isoformat()
        async with await self.db.get_connection() as conn:
            await conn.execute(
                """INSERT INTO tez_natija_amocrm_export
                   (telegram_id, lead_id, group_name, exported_at)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(telegram_id) DO UPDATE SET
                     lead_id = excluded.lead_id,
                     group_name = excluded.group_name,
                     exported_at = excluded.exported_at""",
                (telegram_id, lead_id, group_name, now),
            )
            await conn.commit()

    async def export_all_groups_to_amocrm(
        self,
        client: "TelegramClient",
        progress_cb=None,
    ) -> dict:
        if self.amocrm is None:
            return {"new": 0, "skip": 0, "errors": ["AmoCRM ulanmagan"]}

        await self._ensure_amo_state_table()

        total_new = 0
        total_skip = 0
        errors = []

        for group_name in TEZ_NATIJA_GROUPS:
            try:
                result = await self._export_group_to_amocrm(client, group_name, progress_cb)
                total_new += result["new"]
                total_skip += result["skip"]
                logger.info(
                    "[AMO-EXPORT] %s: %d yangi lead, %d skip",
                    group_name, result["new"], result["skip"],
                )
            except Exception as exc:
                logger.error("[AMO-EXPORT] %s xato: %s", group_name, exc)
                errors.append(f"{group_name}: {exc}")
            await asyncio.sleep(2)

        return {"new": total_new, "skip": total_skip, "errors": errors}

    async def _export_group_to_amocrm(
        self,
        client: "TelegramClient",
        group_name: str,
        progress_cb,
    ) -> dict:
        target = None
        async for dialog in client.iter_dialogs():
            if group_name.upper() in (dialog.name or "").upper():
                target = dialog
                break

        if target is None:
            logger.warning("[AMO-EXPORT] Guruh topilmadi: %s", group_name)
            return {"new": 0, "skip": 0}

        new_count = 0
        skip_count = 0

        try:
            async for user in client.iter_participants(target.id):
                if user.bot or user.deleted:
                    skip_count += 1
                    continue

                if await self._amo_already_exported(user.id):
                    skip_count += 1
                    continue

                lead_id = await self._create_amo_lead(user, group_name)
                await self._amo_mark_exported(user.id, lead_id, group_name)

                if lead_id:
                    new_count += 1
                else:
                    skip_count += 1

                if progress_cb and new_count and new_count % 25 == 0:
                    await progress_cb(group_name, new_count)

                await asyncio.sleep(_AMO_DELAY)

        except Exception as exc:
            try:
                from telethon import errors as tg_errors
                if isinstance(exc, tg_errors.FloodWaitError):
                    logger.warning("[AMO-EXPORT] FloodWait %ss", exc.seconds)
                    await asyncio.sleep(exc.seconds + 5)
                    return {"new": new_count, "skip": skip_count}
            except Exception:
                logger.error("Exception handled in %s", __name__, exc_info=True)
            raise

        return {"new": new_count, "skip": skip_count}

    async def _create_amo_lead(self, user, group_name: str) -> Optional[int]:
        first = user.first_name or ""
        last = user.last_name or ""
        full_name = f"{first} {last}".strip() or "Noma'lum"
        username = f"@{user.username}" if user.username else ""
        phone = user.phone or ""

        lead_name = f"Tez Natija: {full_name}"
        if username:
            lead_name += f" ({username})"

        tag = group_name.replace('"', "").replace(" UMUMIY", "").strip()

        note_parts = [f"Manba: {group_name}", f"Telegram ID: {user.id}"]
        if username:
            note_parts.append(f"Username: {username}")
        note = "\n".join(note_parts)

        try:
            if phone:
                lead_id = await self.amocrm.ensure_lead(full_name, phone, note=note)
                if lead_id:
                    try:
                        await self.amocrm.add_lead_tag(lead_id, tag)
                    except Exception:
                        logger.error("Exception handled in %s", __name__, exc_info=True)
                    return lead_id
            lead_id = await self.amocrm.create_standalone_lead(
                name=lead_name,
                note=note,
                pipeline_id=_AMO_PIPELINE_ID,
                status_id=_AMO_STATUS_ID,
                tags=[tag, "Tez Natija"],
            )
            return lead_id
        except Exception as exc:
            logger.error("[AMO-EXPORT] Lead yaratishda xato (%s): %s", full_name, exc)
            return None
