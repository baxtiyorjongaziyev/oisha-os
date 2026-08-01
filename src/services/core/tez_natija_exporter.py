"""
TezNatijaExporter — Tez Natija guruhlaridan a'zolarni skanlab,
Google Sheets'ga CRM ro'yxat sifatida chiqaradi.

Guruhlar: TEZ NATIJA 2, 3, 4, 5 UMUMIY
Chiqish: Google Sheets "Tez Natija CRM" varog'i

CRM ustunlari:
  A: Telegram ID
  B: Ism
  C: @Username
  D: Telefon
  E: Manba guruh
  F: Qo'shildi
  G: Holat          ← sotuvchi to'ldiradi: Yangi / Bog'lanildi / Qiziq / Rad etdi / Mijoz
  H: Mas'ul         ← sotuvchi ismi
  I: Bog'lanilgan sana
  J: Izoh           ← sotuvchi yozadi
"""

from __future__ import annotations

import asyncio
import logging
import random
from typing import TYPE_CHECKING, Optional

from src.time_utils import get_local_now

if TYPE_CHECKING:
    from telethon import TelegramClient
    from src.services.core.gsheets import GoogleSheetsSync
    from src.services.core.crm.amocrm_sync import AmoCRMSync
    from src.database import Database

logger = logging.getLogger(__name__)

TEZ_NATIJA_GROUPS = [
    '"TEZ NATIJA 2" UMUMIY',
    '"TEZ NATIJA 3" UMUMIY',
    '"TEZ NATIJA 4" UMUMIY',
    '"TEZ NATIJA 5" UMUMIY',
]

SHEET_NAME = "Tez Natija CRM"
SHEET_HEADERS = [
    "Telegram ID", "Ism", "@Username", "Telefon",
    "Manba guruh", "Qo'shildi",
    "Holat", "Mas'ul", "Bog'lanilgan sana", "Izoh",
]

# AmoCRM: Hunter voronkasi — Tez Natija leadlari shu bosqichga tushadi
_AMO_PIPELINE_ID = 10117998
_AMO_STATUS_ID = 80178230
# AmoCRM rate limit ~7 req/sek. Har lead 1-2 request => xavfsiz 0.4s pauza
_AMO_DELAY = 0.4


class TezNatijaExporter:
    """Tez Natija guruhlaridan a'zolarni CRM formatida export qiladi."""

    def __init__(
        self,
        sheets: Optional["GoogleSheetsSync"] = None,
        amocrm: Optional["AmoCRMSync"] = None,
        db: Optional["Database"] = None,
    ):
        self.sheets = sheets
        self.amocrm = amocrm
        self.db = db
        self._worksheet = None

    def _get_or_create_worksheet(self):
        if self._worksheet is not None:
            return self._worksheet
        if self.sheets is None or self.sheets.spreadsheet is None:
            return None
        try:
            self._worksheet = self.sheets.spreadsheet.worksheet(SHEET_NAME)
        except Exception:
            try:
                self._worksheet = self.sheets.spreadsheet.add_worksheet(
                    title=SHEET_NAME, rows="3000", cols=str(len(SHEET_HEADERS))
                )
                self._worksheet.append_row(SHEET_HEADERS)
                self._format_header(self._worksheet)
                logger.info("[EXPORT] '%s' varog'i yaratildi", SHEET_NAME)
            except Exception as exc:
                logger.error("[EXPORT] Worksheet yaratishda xato: %s", exc)
                return None
        return self._worksheet

    def _format_header(self, ws):
        try:
            ws.format("A1:J1", {
                "backgroundColor": {"red": 0.18, "green": 0.37, "blue": 0.73},
                "textFormat": {"bold": True, "foregroundColor": {"red": 1, "green": 1, "blue": 1}},
                "horizontalAlignment": "CENTER",
            })
        except Exception:
            logger.error("Exception handled in %s", __name__, exc_info=True)

    async def export_all_groups(
        self,
        client: "TelegramClient",
        progress_cb=None,
    ) -> dict:
        """Barcha Tez Natija guruhlarini skanlab CRM sheets'ga yozadi."""
        total_new = 0
        total_skip = 0
        errors = []

        for group_name in TEZ_NATIJA_GROUPS:
            try:
                result = await self._export_group(client, group_name, progress_cb)
                total_new += result["new"]
                total_skip += result["skip"]
                logger.info("[EXPORT] %s: %d yangi, %d skip", group_name, result["new"], result["skip"])
            except Exception as exc:
                logger.error("[EXPORT] %s xato: %s", group_name, exc)
                errors.append(f"{group_name}: {exc}")
            await asyncio.sleep(5)

        return {"new": total_new, "skip": total_skip, "errors": errors}

    async def _export_group(
        self,
        client: "TelegramClient",
        group_name: str,
        progress_cb,
    ) -> dict:
        ws = self._get_or_create_worksheet()
        if ws is None:
            # Sheets ulanmagan — guruhni skan qilib Telegram so'rovlarini
            # behuda sarflamaymiz
            logger.error("[EXPORT] Worksheet yo'q (Sheets ulanmagan) — %s o'tkazib yuborildi", group_name)
            return {"new": 0, "skip": 0}

        target = None
        async for dialog in client.iter_dialogs():
            if group_name.upper() in (dialog.name or "").upper():
                target = dialog
                break

        if target is None:
            logger.warning("[EXPORT] Guruh topilmadi: %s", group_name)
            return {"new": 0, "skip": 0}

        existing_ids: set = set()
        if ws is not None:
            try:
                col_a = ws.col_values(1)
                existing_ids = {str(v) for v in col_a[1:] if v}
            except Exception:
                logger.error("Exception handled in %s", __name__, exc_info=True)

        new_count = 0
        skip_count = 0
        batch: list = []

        try:
            async for user in client.iter_participants(target.id):
                if user.bot or user.deleted:
                    skip_count += 1
                    continue

                uid = str(user.id)
                if uid in existing_ids:
                    skip_count += 1
                    continue

                first = user.first_name or ""
                last = user.last_name or ""
                full_name = f"{first} {last}".strip() or "Noma'lum"
                username = f"@{user.username}" if user.username else ""
                phone = user.phone or ""
                now = get_local_now().strftime("%Y-%m-%d")

                row = [
                    uid,
                    full_name,
                    username,
                    phone,
                    group_name,
                    now,
                    "Yangi",   # Holat
                    "",        # Mas'ul
                    "",        # Bog'lanilgan sana
                    "",        # Izoh
                ]
                batch.append(row)
                existing_ids.add(uid)
                new_count += 1

                if len(batch) >= 50:
                    await self._flush_batch(ws, batch)
                    batch = []
                    if progress_cb:
                        await progress_cb(group_name, new_count)
                    await asyncio.sleep(random.uniform(1, 2))

        except Exception as exc:
            try:
                from telethon import errors as tg_errors
                if isinstance(exc, tg_errors.FloodWaitError):
                    logger.warning("[EXPORT] FloodWait %ss", exc.seconds)
                    await asyncio.sleep(exc.seconds + 5)
                    return {"new": new_count, "skip": skip_count}
            except Exception:
                logger.error("Exception handled in %s", __name__, exc_info=True)
            raise

        if batch:
            await self._flush_batch(ws, batch)

        return {"new": new_count, "skip": skip_count}

    async def _flush_batch(self, ws, rows: list):
        if ws is None or not rows:
            return
        try:
            ws.append_rows(rows, value_input_option="USER_ENTERED")
        except Exception as exc:
            logger.error("[EXPORT] Batch yozishda xato: %s", exc)

    # ---------------------------------------------------------------
    #  AmoCRM export
    # ---------------------------------------------------------------

    async def _ensure_amo_state_table(self):
        """AmoCRM'ga eksport qilingan a'zolarni kuzatuvchi jadval (dedup uchun)."""
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
        """Barcha Tez Natija guruhlari a'zolarini AmoCRM'ga lead sifatida yozadi."""
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
        """Bitta a'zo uchun AmoCRM lead yaratadi. Raqam bo'lsa kontakt bog'laydi."""
        first = user.first_name or ""
        last = user.last_name or ""
        full_name = f"{first} {last}".strip() or "Noma'lum"
        username = f"@{user.username}" if user.username else ""
        phone = user.phone or ""

        lead_name = f"Tez Natija: {full_name}"
        if username:
            lead_name += f" ({username})"

        # Manba guruhini toza tag sifatida: "TEZ NATIJA 5"
        tag = group_name.replace('"', "").replace(" UMUMIY", "").strip()

        note_parts = [f"Manba: {group_name}", f"Telegram ID: {user.id}"]
        if username:
            note_parts.append(f"Username: {username}")
        note = "\n".join(note_parts)

        try:
            if phone:
                # Raqam bor: kontakt qidiradi/yaratadi + bitim bog'laydi
                lead_id = await self.amocrm.ensure_lead(full_name, phone, note=note)
                if lead_id:
                    try:
                        await self.amocrm.add_lead_tag(lead_id, tag)
                    except Exception:
                        logger.error("Exception handled in %s", __name__, exc_info=True)
                    return lead_id
                # Fallback: raqamli lead yaratib bo'lmasa standalone
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
