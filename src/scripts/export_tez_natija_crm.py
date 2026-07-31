"""
TEZ NATIJA guruh a'zolarini Google Sheets CRM ga export qilish.

Usage:
    python -m src.scripts.export_tez_natija_crm

Yoki:
    from src.scripts.export_tez_natija_crm import export_all_groups
    asyncio.run(export_all_groups())
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from telethon import TelegramClient, errors
from telethon.tl.types import Channel, Chat, User

logger = logging.getLogger(__name__)

# TEZ NATIJA guruhlari
TEZ_NATIJA_GROUPS = [
    "TEZ NATIJA 2",
    "TEZ NATIJA 3",
    "TEZ NATIJA 4",
    "TEZ NATIJA 5",
]


async def scrape_group_members(
    client: TelegramClient,
    group_name: str,
) -> List[Dict[str, Any]]:
    """Bitta guruh a'zolarini yig'ish."""
    logger.info("🔍 Qidirilmoqda: %s", group_name)
    target_group = None

    async for dialog in client.iter_dialogs():
        if dialog.name and group_name.upper() in dialog.name.upper():
            target_group = dialog
            logger.info("✅ Topildi: %s (ID: %s)", dialog.name, dialog.id)
            break

    if not target_group:
        logger.warning("❌ '%s' guruhi topilmadi.", group_name)
        return []

    members = []
    count = 0

    try:
        async for user in client.iter_participants(target_group.id):
            if user.bot:
                continue

            member = {
                "user_id": user.id,
                "first_name": user.first_name or "",
                "last_name": user.last_name or "",
                "username": user.username or "",
                "phone": user.phone or "",
                "group_name": target_group.name,
                "group_id": target_group.id,
                "scraped_at": datetime.now(timezone.utc).isoformat(),
            }
            members.append(member)
            count += 1

            if count % 100 == 0:
                logger.info("📈 %s dan %d ta a'zo yig'ildi...", target_group.name, count)
                await asyncio.sleep(1)

    except errors.FloodWaitError as exc:
        logger.warning("⏳ FloodWait: %d soniya kutish kerak.", exc.seconds)
        await asyncio.sleep(exc.seconds)
    except Exception as exc:
        logger.error("❌ Xatolik: %s", exc, exc_info=True)

    logger.info("✅ %s dan jami %d ta a'zo yig'ildi.", target_group.name, count)
    return members


async def export_to_google_sheets(
    all_members: List[Dict[str, Any]],
    spreadsheet_id: Optional[str] = None,
    credentials_path: str = "service_account.json",
) -> int:
    """Barcha a'zolarni Google Sheets CRM ga export qilish."""
    try:
        import gspread
        from google.oauth2.service_account import Credentials
    except ImportError:
        logger.error("❌ gspread o'rnatilmagan. 'pip install gspread' ishga tushiring.")
        return 0

    if not spreadsheet_id:
        spreadsheet_id = os.getenv("GSHEET_ID", "")

    if not spreadsheet_id:
        logger.error("❌ GSHEET_ID belgilanmagan.")
        return 0

    if not os.path.exists(credentials_path):
        logger.error("❌ Credentials fayli topilmadi: %s", credentials_path)
        return 0

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_file(credentials_path, scopes=scopes)
    gc = gspread.authorize(creds)

    try:
        ss = gc.open_by_key(spreadsheet_id)
    except Exception as exc:
        logger.error("❌ Spreadsheet ochilmadi: %s", exc)
        return 0

    # "Tez Natija CRM" varog'ini topish yoki yaratish
    try:
        sheet = ss.worksheet("Tez Natija CRM")
        logger.info("📋 Mavjud 'Tez Natija CRM' varogi topildi.")
    except gspread.exceptions.WorksheetNotFound:
        sheet = ss.add_worksheet(title="Tez Natija CRM", rows="5000", cols="12")
        sheet.append_row([
            "Telegram ID", "Guruh", "Ism", "Familiya", "Username", "Telefon",
            "Holati", "Izoh", "Sotuvchi", "Sinxro vaqti", "AmoCRM", "Manba"
        ])
        logger.info("📋 'Tez Natija CRM' varogi yaratildi.")

    # Mavjud ID larni olish (takrorlanishni oldini olish uchun)
    try:
        existing_ids = set(sheet.col_values(1))
    except Exception:
        logger.error("Exception handled in %s", __name__, exc_info=True)
        existing_ids = set()

    # Yangi qatorlarni tayyorlash
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
    new_rows = []
    skipped = 0

    for member in all_members:
        user_id_str = str(member["user_id"])
        if user_id_str in existing_ids:
            skipped += 1
            continue

        username_str = f"@{member['username']}" if member["username"] else ""
        phone_str = str(member["phone"]) if member["phone"] else ""

        new_rows.append([
            user_id_str,
            member["group_name"],
            member["first_name"],
            member["last_name"],
            username_str,
            phone_str,
            "Yangi",           # Holati
            "",                # Izoh
            "",                # Sotuvchi
            now_str,           # Sinxro vaqti
            "Export qilindi",  # AmoCRM
            "TEZ NATIJA",     # Manba
        ])
        existing_ids.add(user_id_str)

    # Batch qo'shish (tezroq)
    if new_rows:
        try:
            sheet.append_rows(new_rows, value_input_option="USER_ENTERED")
            logger.info("✅ %d ta yangi qator qo'shildi.", len(new_rows))
        except Exception as exc:
            logger.error("❌ Qatorlarni qo'shishda xatolik: %s", exc)
            return 0

    logger.info("📊 Jami: %d ta yangi, %d ta takrorlandi, jami %d ta",
                len(new_rows), skipped, len(all_members))
    return len(new_rows)


async def export_to_amocrm(
    all_members: List[Dict[str, Any]],
) -> int:
    """Barcha a'zolarni AmoCRM ga sync qilish."""
    try:
        from src.services.core.crm.amocrm_sync import AmoCRMSync
        amocrm = AmoCRMSync()
    except Exception as exc:
        logger.warning("⚠️ AmoCRM ulanmadi: %s", exc)
        return 0

    count = 0
    for member in all_members:
        try:
            full_name = f"{member['first_name']} {member['last_name']}".strip()
            if not full_name:
                full_name = f"Lead {member['user_id']}"

            phone = member.get("phone") or ""
            username = member.get("username") or ""
            group = member.get("group_name") or ""

            await amocrm.sync_lead(
                user_id=member["user_id"],
                name=full_name,
                phone=phone,
                note=f"TEZ NATIJA guruhidan export. Guruh: {group}. @{username}",
            )
            count += 1

            if count % 50 == 0:
                logger.info("📈 AmoCRM ga %d ta sync qilindi...", count)
                await asyncio.sleep(0.5)

        except Exception as exc:
            logger.debug("AmoCRM sync xatolik: %s", exc)

    logger.info("✅ AmoCRM ga jami %d ta sync qilindi.", count)
    return count


async def export_all_groups(
    spreadsheet_id: Optional[str] = None,
    credentials_path: str = "service_account.json",
    sync_amocrm: bool = True,
) -> Dict[str, Any]:
    """Barcha TEZ NATIJA guruhlarini export qilish."""
    from src.settings import settings

    session_path = os.getenv("USERBOT_SESSION_STRING", "")

    if session_path:
        from telethon.sessions import StringSession
        client = TelegramClient(StringSession(session_path), settings.API_ID, settings.API_HASH)
    else:
        session_file = os.getenv("USERBOT_SESSION_FILE", "userbot_session")
        client = TelegramClient(session_file, settings.API_ID, settings.API_HASH)

    results = {
        "groups": {},
        "total_members": 0,
        "sheets_exported": 0,
        "amocrm_synced": 0,
        "started_at": datetime.now(timezone.utc).isoformat(),
    }

    try:
        await client.connect()
        if not await client.is_user_authorized():
            logger.error("❌ Userbot authorized emas!")
            return results

        logger.info("🚀 TEZ NATIJA guruhlari skanerlashni boshlayapmiz...")

        all_members = []
        for group_name in TEZ_NATIJA_GROUPS:
            members = await scrape_group_members(client, group_name)
            results["groups"][group_name] = len(members)
            all_members.extend(members)
            await asyncio.sleep(2)  # Guruhlar orasida kutish

        results["total_members"] = len(all_members)

        # Google Sheets ga export
        if all_members:
            sheets_count = await export_to_google_sheets(
                all_members, spreadsheet_id, credentials_path
            )
            results["sheets_exported"] = sheets_count

            # AmoCRM ga sync
            if sync_amocrm:
                amocrm_count = await export_to_amocrm(all_members)
                results["amocrm_synced"] = amocrm_count

    except Exception as exc:
        logger.error("❌ Umumiy xatolik: %s", exc, exc_info=True)
    finally:
        await client.disconnect()

    results["finished_at"] = datetime.now(timezone.utc).isoformat()
    return results


def main() -> None:
    """CLI entry point."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    results = asyncio.run(export_all_groups())

    print("\n" + "=" * 50)
    print("📊 TEZ NATIJA CRM EXPORT NATIJASI")
    print("=" * 50)
    for group, count in results.get("groups", {}).items():
        print(f"  {group}: {count} ta a'zo")
    print(f"  Jami a'zolar: {results.get('total_members', 0)}")
    print(f"  Google Sheets: {results.get('sheets_exported', 0)} ta yangi qator")
    print(f"  AmoCRM: {results.get('amocrm_synced', 0)} ta sync")
    print("=" * 50)


if __name__ == "__main__":
    main()
