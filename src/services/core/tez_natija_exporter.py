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


class TezNatijaExporter:
    """Tez Natija guruhlaridan a'zolarni CRM formatida export qiladi."""

    def __init__(self, sheets: Optional["GoogleSheetsSync"] = None):
        self.sheets = sheets
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
            pass

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
                pass

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
                pass
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
