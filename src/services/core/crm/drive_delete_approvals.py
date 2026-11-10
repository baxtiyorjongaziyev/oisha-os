"""Owner-only Telegram review for verified amoCRM -> Google Drive copies.

No unattended deletion. Request must be created by owner in a private chat,
then claimed once via a Telegram inline-button callback from that same owner.
"""
from __future__ import annotations

import logging
import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from src.database_pool import db_pool
from src.settings import settings
from src.services.core.crm.amocrm_sync import AmoCRMSync
from src.services.core.gdrive import GoogleDriveSync
from src.services.core.crm.safe_drive_automation import (
    COPY_MARKER, CopyRecord, SafeCRMDriveAutomation,
)

LOG = logging.getLogger(__name__)
RECEIPT = re.compile(
    r"\[OISHA_DRIVE_COPY\] lead=(\d+) note=(\d+) "
    r"drive=([A-Za-z0-9_-]+) sha256=([a-f0-9]{64}) size=(\d+)"
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def _schema() -> None:
    await db_pool.execute(
        """CREATE TABLE IF NOT EXISTS crm_drive_delete_approvals (
           id TEXT PRIMARY KEY,
           lead_id INTEGER NOT NULL,
           note_id INTEGER NOT NULL,
           drive_id TEXT NOT NULL,
           size INTEGER NOT NULL,
           sha256 TEXT NOT NULL,
           status TEXT NOT NULL,
           requested_at TEXT NOT NULL,
           expires_at TEXT NOT NULL,
           resolved_at TEXT,
           resolved_by INTEGER
        )"""
    )
    await db_pool.commit()


def parse_verified_receipt(
    lead_id: int, text: str, originals: dict[int, dict[str, Any]]
) -> CopyRecord | None:
    match = RECEIPT.search(text)
    if not match or int(match[1]) != lead_id:
        return None
    note_id, drive_id, sha256, size = (
        int(match[2]), match[3], match[4], int(match[5])
    )
    original = originals.get(note_id)
    if not original or original.get("note_type") != "file":
        return None
    uuid = (original.get("params") or {}).get("file_uuid")
    if not uuid or size <= 0:
        return None
    return CopyRecord(
        lead_id=lead_id, note_id=note_id, file_id=str(uuid),
        drive_id=drive_id,
        drive_url=f"https://drive.google.com/file/d/{drive_id}/view",
        sha256=sha256, size=size,
    )


async def verified_records(amo: AmoCRMSync, lead_id: int) -> list[CopyRecord]:
    notes = await amo.get_lead_notes(lead_id)
    if amo.last_error:
        raise RuntimeError(f"Could not read CRM notes: {amo.last_error}")
    originals = {int(n["id"]): n for n in notes if n.get("note_type") == "file"}
    records: dict[int, CopyRecord] = {}
    for n in notes:
        text = str((n.get("params") or {}).get("text") or "")
        if COPY_MARKER not in text:
            continue
        record = parse_verified_receipt(lead_id, text, originals)
        if record:
            records[record.note_id] = record
    return list(records.values())


async def request_approval(record: CopyRecord) -> str:
    await _schema()
    request_id = secrets.token_urlsafe(12)
    now = _utcnow()
    await db_pool.execute(
        """INSERT INTO crm_drive_delete_approvals
           (id,lead_id,note_id,drive_id,size,sha256,status,requested_at,expires_at)
           VALUES (?,?,?,?,?,?,'pending',?,?)""",
        [request_id, record.lead_id, record.note_id, record.drive_id,
         record.size, record.sha256, now.isoformat(),
         (now + timedelta(hours=12)).isoformat()],
    )
    await db_pool.commit()
    return request_id


async def claim(request_id: str, *, actor: int, approve: bool) -> dict | None:
    """Atomic, one-time transition. Expired/replayed requests never proceed."""
    if not settings.OWNER_ID or actor != int(settings.OWNER_ID):
        raise PermissionError("Not the configured owner")
    now = _utcnow().isoformat()
    await _schema()
    rows = await db_pool.execute(
        """UPDATE crm_drive_delete_approvals
           SET status = ?, resolved_by = ?, resolved_at = ?
           WHERE id = ? AND status = 'pending' AND expires_at > ?
           RETURNING lead_id,note_id,drive_id,size,sha256""",
        ["processing" if approve else "rejected", actor, now, request_id, now],
    )
    await db_pool.commit()
    return dict(rows[0]) if len(rows) == 1 else None


async def finish(request_id: str, *, status: str) -> None:
    if status not in {"deleted", "failed"}:
        raise ValueError("Invalid completion status")
    await db_pool.execute(
        "UPDATE crm_drive_delete_approvals SET status = ?, resolved_at = ? "
        "WHERE id = ? AND status = 'processing'",
        [status, _utcnow().isoformat(), request_id],
    )
    await db_pool.commit()


def register_crm_drive_approval_handlers(dp: Any, *, owner_id: int) -> None:
    from aiogram import F
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

    def is_owner_private_chat(obj: Any) -> bool:
        user = getattr(obj, "from_user", None)
        message = getattr(obj, "message", None) or obj
        chat = getattr(message, "chat", None)
        return bool(
            owner_id and user and int(getattr(user, "id", 0)) == int(owner_id)
            and chat and int(getattr(chat, "id", 0)) == int(owner_id)
            and getattr(chat, "type", "") == "private"
        )

    @dp.message(F.text.regexp(r"(?i)^/crm_drive_review(?:\s+\d+)?$"))
    async def review(message: Any) -> None:
        if not is_owner_private_chat(message):
            await message.answer("Faqat rahbarning shaxsiy chatida ishlaydi.")
            return
        parts = (message.text or "").split()
        if len(parts) != 2:
            await message.answer("Namuna: /crm_drive_review 12345 (amoCRM bitim ID)")
            return
        lead_id = int(parts[1])
        try:
            amo = AmoCRMSync()
            records = await verified_records(amo, lead_id)
            if not records:
                await message.answer("Tasdiqlangan nusxa topilmadi. Avval fayllarni Driveʼga nusxalang.")
                return
            for record in records[:5]:
                rid = await request_approval(record)
                buttons = InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="✅ CRM originalini oʼchirish",
                                         callback_data=f"crmoff:yes:{rid}"),
                    InlineKeyboardButton(text="❌ Saqlab qolish",
                                         callback_data=f"crmoff:no:{rid}"),
                ]])
                await message.answer(
                    f"CRM bitim #{record.lead_id}, fayl note #{record.note_id}\n"
                    f"Drive nusxasi: {record.drive_url}\n"
                    f"Hajm: {record.size} bayt\n"
                    "Tasdiq 12 soatda eskiradi. Original faqat ✅ bosilgandan "
                    "va Drive checksum qayta tekshirilgandan keyin oʼchiriladi.",
                    reply_markup=buttons,
                )
            if len(records) > 5:
                await message.answer(
                    f"Bu safar 5/{len(records)} fayl koʼrsatildi. "
                    "Qolganlarini keyin koʼrib chiqing."
                )
        except Exception:
            LOG.exception("CRM Drive review listing failed")
            await message.answer("Tekshiruv xatosi. Fayllar oʼchirilmadi.")

    @dp.callback_query(F.data.startswith("crmoff:"))
    async def decide(callback: Any) -> None:
        if not is_owner_private_chat(callback):
            await callback.answer("Faqat rahbar tasdiqlaydi.", show_alert=True)
            return
        pieces = str(callback.data or "").split(":")
        if len(pieces) != 3 or pieces[1] not in {"yes", "no"}:
            await callback.answer("Notoʼg'ri soʼrov", show_alert=True)
            return
        action, request_id = pieces[1], pieces[2]
        try:
            row = await claim(request_id, actor=int(owner_id), approve=(action == "yes"))
            if not row:
                await callback.answer("Soʼrov muddati oʼtgan yoki qayta ishlangan.", show_alert=True)
                return
            if action == "no":
                await callback.message.edit_text("❌ Rad etildi. CRM fayli saqlanib qoldi.")
                await callback.answer()
                return
            record = CopyRecord(
                lead_id=int(row["lead_id"]), note_id=int(row["note_id"]),
                file_id="", drive_id=str(row["drive_id"]),
                drive_url=f"https://drive.google.com/file/d/{row['drive_id']}/view",
                sha256=str(row["sha256"]), size=int(row["size"]),
            )
            try:
                service = SafeCRMDriveAutomation(
                    AmoCRMSync(), GoogleDriveSync(settings.GSHEET_CREDS_FILE),
                    settings.GDRIVE_OFFLOAD_FOLDER_ID or "",
                )
                success = await service.delete_approved_original(
                    record, approval_id=request_id, acting_owner_id=int(owner_id),
                )
                await finish(request_id, status="deleted" if success else "failed")
            except Exception:
                LOG.exception("Approved CRM note deletion failed")
                await finish(request_id, status="failed")
                success = False
            await callback.message.edit_text(
                ("✅ Owner tasdigʼi bilan CRM original note oʼchirildi. "
                 "Drive nusxasi saqlandi.") if success else
                "⚠️ Oʼchirish tugamadi. Fayl holatini CRMʼda tekshiring."
            )
            await callback.answer()
        except Exception:
            LOG.exception("CRM Drive approval callback failed")
            await callback.answer("Xatolik. CRM va Drive holatini tekshiring.", show_alert=True)
