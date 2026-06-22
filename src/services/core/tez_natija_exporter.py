"""
TezNatijaExporter — Tez Natija guruhlaridan a'zolarni skanlab,
Google Sheets'ga sotuvchilar uchun taklif ma'lumotlari bilan chiqaradi.

Guruhlar: TEZ NATIJA 2, 3, 4, 5
Chiqish: Google Sheets "Tez Natija Leads" varog'i

Ustunlar:
  A: Telegram ID
  B: Ism Familiya
  C: Username (@)
  D: Telefon
  E: Manba guruh
  F: Skanlangan vaqt
  G: Taklif xabari (Gemini tomonidan)
  H: Holat (Yangi / Yuborildi / Rad etdi)
"""

from __future__ import annotations

import asyncio
import logging
import random
from datetime import datetime
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

SHEET_NAME = "Tez Natija Leads"
SHEET_HEADERS = [
    "Telegram ID", "Ism", "Username", "Telefon",
    "Manba guruh", "Skanlangan", "Taklif xabari", "Holat",
]

_INVITE_PROMPT = """Siz Jon Branding agentligining savdo mutaxassisi siz.
Quyidagi Telegram foydalanuvchisi "{name}" uchun shaxsiy taklif xabari yozing.
U "{group}" guruhida — demak kichik biznes yoki o'z brendini rivojlantirmoqchi.

Talab:
- O'zbek tilida, samimiy va qisqa (3-4 jumla)
- Ism bilan murojaat
- Jon Branding'ning qiymatini ko'rsat (brend identifikatsiya, logo, SMM, packaging)
- CTA: "suhbatlashaylikmi?" yoki shunga o'xshash
- Reklama emas, do'stona muloqot

Faqat xabarni yoz, boshqa narsa yo'q."""


class TezNatijaExporter:
    """Tez Natija guruhlaridan a'zolarni export qiladi."""

    def __init__(self, gemini_api_key: str, sheets: Optional["GoogleSheetsSync"] = None):
        self._api_key = gemini_api_key
        self.sheets = sheets
        self._gemini = None
        self._worksheet = None

    @property
    def gemini(self):
        if self._gemini is None:
            from google import genai
            self._gemini = genai.Client(api_key=self._api_key)
        return self._gemini

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
                    title=SHEET_NAME, rows="2000", cols=str(len(SHEET_HEADERS))
                )
                self._worksheet.append_row(SHEET_HEADERS)
                logger.info("[EXPORT] '%s' varog'i yaratildi", SHEET_NAME)
            except Exception as exc:
                logger.error("[EXPORT] Worksheet yaratishda xato: %s", exc)
                return None
        return self._worksheet

    async def export_all_groups(
        self,
        client: "TelegramClient",
        generate_invites: bool = True,
        progress_cb=None,
    ) -> dict:
        """Barcha Tez Natija guruhlarini skanlab sheets'ga yozadi."""
        total_new = 0
        total_skip = 0
        errors = []

        for group_name in TEZ_NATIJA_GROUPS:
            try:
                result = await self._export_group(
                    client, group_name, generate_invites, progress_cb
                )
                total_new += result["new"]
                total_skip += result["skip"]
                logger.info(
                    "[EXPORT] %s: %d yangi, %d skip",
                    group_name, result["new"], result["skip"],
                )
            except Exception as exc:
                logger.error("[EXPORT] %s xato: %s", group_name, exc)
                errors.append(f"{group_name}: {exc}")
            await asyncio.sleep(5)

        return {"new": total_new, "skip": total_skip, "errors": errors}

    async def _export_group(
        self,
        client: "TelegramClient",
        group_name: str,
        generate_invites: bool,
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

        existing_ids = set()
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
                now = get_local_now().strftime("%Y-%m-%d %H:%M")

                invite_msg = ""
                if generate_invites:
                    invite_msg = await self._generate_invite(full_name, group_name)
                    await asyncio.sleep(random.uniform(0.8, 1.5))

                row = [uid, full_name, username, phone,
                       group_name, now, invite_msg, "Yangi"]
                batch.append(row)
                existing_ids.add(uid)
                new_count += 1

                if len(batch) >= 20:
                    await self._flush_batch(ws, batch)
                    batch = []
                    if progress_cb:
                        await progress_cb(group_name, new_count)
                    await asyncio.sleep(random.uniform(1, 2))

        except Exception as exc:
            from telethon import errors as tg_errors
            if hasattr(tg_errors, "FloodWaitError") and isinstance(exc, tg_errors.FloodWaitError):
                logger.warning("[EXPORT] FloodWait %ss, kutilmoqda...", exc.seconds)
                await asyncio.sleep(exc.seconds + 5)
            else:
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

    async def _generate_invite(self, name: str, group: str) -> str:
        try:
            from src.utils.ai_utils import safe_ai_call
            import os
            from src.settings import settings

            prompt = _INVITE_PROMPT.format(name=name, group=group)
            response = await safe_ai_call(
                client=self.gemini,
                prompt=[prompt],
                system_instruction="Faqat xabar matni. Qo'shtirnoqsiz.",
                model=os.getenv("GEMINI_SELF_LEARNING_MODEL", settings.GEMINI_CALL_MODEL),
            )
            return response.text.strip()
        except Exception as exc:
            logger.debug("[EXPORT] Invite generatsiyada xato: %s", exc)
            return (
                f"Salom {name}! Jon Branding agentligimiz kichik bizneslar uchun "
                f"professional brend yaratishda yordam beradi. Qiziqasizmi?"
            )
