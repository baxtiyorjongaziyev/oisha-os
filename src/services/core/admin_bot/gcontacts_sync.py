"""
Google Contacts & Telegram synchronization mixin for AdminBot.
"""
from __future__ import annotations

import asyncio
from datetime import datetime
import structlog
from telethon import functions, types

logger = structlog.get_logger()


class AdminGContactsSyncMixin:
    """Mixin providing Google Contacts to Telegram user synchronization."""

    async def _run_gcontacts_telegram_sync(self, event, wait_msg):
        """Fon rejimida Google Kontaktlarni Telegram bilan sinxronizatsiya qiladi."""
        try:
            from src.services.core.google_contacts_service import GoogleContactsService
            gcontacts = GoogleContactsService()

            # 1. Fetch all Google Contacts
            contacts = gcontacts.get_all_contacts(max_results=5000)
            total_contacts = len(contacts)

            if not contacts:
                await wait_msg.edit("❌ Google Contacts bo'sh yoki ulanishda xatolik yuz berdi.")
                return

            await wait_msg.edit(f"⏳ `{total_contacts}` ta kontakt o'qildi. Telegram profillar qidirilmoqda...")

            # 2. Extract phone numbers
            phone_to_contact = {}
            for c in contacts:
                for p in c["phones"]:
                    clean_p = p.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
                    if clean_p.startswith("+"):
                        clean_p = clean_p[1:]
                    if clean_p:
                        phone_to_contact[clean_p] = c

            total_phones = len(phone_to_contact)
            matched_via_phone = {}

            # 3. Match via Telegram contacts import API
            batch_size = 100
            phones_list = list(phone_to_contact.keys())

            for i in range(0, len(phones_list), batch_size):
                batch = phones_list[i:i + batch_size]
                input_contacts = []
                for p in batch:
                    c = phone_to_contact[p]
                    input_contacts.append(
                        types.InputPhoneContact(
                            client_id=int(p[-9:]) if len(p) >= 9 else 0,
                            phone="+" + p,
                            first_name=c["given_name"] or c["display_name"] or "Mijoz",
                            last_name=c["family_name"] or "",
                        )
                    )

                try:
                    res = await self.bot_client(functions.contacts.ImportContactsRequest(contacts=input_contacts))
                    for user in res.users:
                        phone = user.phone or ""
                        matched_c = phone_to_contact.get(phone) or phone_to_contact.get("+" + phone)
                        if matched_c:
                            matched_via_phone[phone] = {
                                "user_id": user.id,
                                "username": user.username,
                                "first_name": user.first_name,
                                "last_name": user.last_name,
                                "contact": matched_c,
                                "method": "Telefon raqami",
                            }
                    await self.bot_client(functions.contacts.DeleteContactsRequest(id=[u.id for u in res.users]))
                except Exception as imp_err:
                    logger.warning(f"[GCONTACTS SYNC] Phone batch import error: {imp_err}")

                await asyncio.sleep(1)

            # 4. Search Tez Natija groups
            target_groups = ["TEZ NATIJA 2", "TEZ NATIJA 3", "TEZ NATIJA 4", "TEZ NATIJA 5"]
            all_group_members = []

            async for dialog in self.bot_client.iter_dialogs():
                if dialog.is_group or dialog.is_channel:
                    if any(tg in dialog.name.upper() for tg in target_groups):
                        try:
                            async for member in self.bot_client.iter_participants(dialog):
                                if not member.bot and not member.deleted:
                                    all_group_members.append(member)
                        except Exception as grp_err:
                            logger.warning(f"[GCONTACTS SYNC] Group fetch error for {dialog.name}: {grp_err}")

            # 5. Name matching against group members
            matched_via_groups = {}
            for member in all_group_members:
                m_first = (member.first_name or "").strip().lower()
                m_last = (member.last_name or "").strip().lower()
                m_username = (member.username or "").strip().lower()

                for c in contacts:
                    c_given = (c["given_name"] or "").strip().lower()
                    c_fam = (c["family_name"] or "").strip().lower()
                    c_disp = (c["display_name"] or "").strip().lower()
                    uid = c["resource_name"]

                    if uid not in matched_via_groups and not any(p in matched_via_phone for p in c["phones"]):
                        is_match = False
                        if c_given and c_fam and m_first and m_last:
                            if c_given == m_first and c_fam == m_last:
                                is_match = True
                        elif c_disp:
                            m_disp = f"{m_first} {m_last}".strip()
                            if c_disp == m_disp or c_disp == m_first or (m_username and c_disp == m_username):
                                is_match = True

                        if is_match:
                            matched_via_groups[uid] = {
                                "user_id": member.id,
                                "username": member.username,
                                "first_name": member.first_name,
                                "last_name": member.last_name,
                                "contact": c,
                                "method": "TN Guruhi a'zosi",
                            }
                            break

            # 6. Combine all matches
            all_matches = []
            for p, data in matched_via_phone.items():
                all_matches.append(data)
            for uid, data in matched_via_groups.items():
                if not any(m["user_id"] == data["user_id"] for m in all_matches):
                    data["method"] = "TN guruhi a'zosi (Ism mosligi)"
                    all_matches.append(data)

            # 7. Save to DB & update Google Contacts note
            updated_gcontacts_count = 0
            for match in all_matches:
                c = match["contact"]
                tg_link = f"https://t.me/{match['username']}" if match["username"] else f"tg://user?id={match['user_id']}"
                
                current_note = c["note"] or ""
                if "Telegram:" not in current_note and "tg://user" not in current_note:
                    tg_info = f"\n[Telegram: @{match['username'] or 'yoq'} | ID: {match['user_id']} | Link: {tg_link}]"
                    new_note = (current_note + tg_info).strip()
                    success = gcontacts.update_contact_note(c["resource_name"], new_note)
                    if success:
                        updated_gcontacts_count += 1

                try:
                    async with await self.db.get_connection() as conn:
                        await conn.execute(
                            """
                            INSERT INTO users (user_id, username, first_name, last_name, phone, role, created_at)
                            VALUES (?, ?, ?, ?, ?, 'Mijoz', ?)
                            ON CONFLICT(user_id) DO UPDATE SET
                                username=excluded.username,
                                first_name=excluded.first_name,
                                last_name=excluded.last_name,
                                phone=coalesce(users.phone, excluded.phone)
                            """,
                            (
                                match["user_id"],
                                match["username"],
                                match["first_name"],
                                match["last_name"],
                                c["phones"][0] if c["phones"] else "",
                                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            )
                        )
                        await conn.commit()
                except Exception as db_err:
                    logger.error(f"[GCONTACTS SYNC] Failed to save to DB for {match['user_id']}: {db_err}")

            # 8. Report results
            report_msg = (
                f"📊 **GOOGLE CONTACTS VA TELEGRAM SINXRONIZATSIYASI YAKUNLANDI!**\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"👤 **Jami Google kontaktlar:** `{total_contacts}` ta\n"
                f"📞 **Telefon raqamli kontaktlar:** `{total_phones}` ta\n"
                f"✅ **Telegram topilgan jami profil:** `{len(all_matches)}` ta\n"
                f"   └ 📱 *Telefon raqam orqali:* `{len(matched_via_phone)}` ta\n"
                f"   └ 👥 *TN guruh a'zolari orqali:* `{len(matched_via_groups)}` ta\n"
                f"📝 **Google Contacts'da yangilanganlar:** `{updated_gcontacts_count}` ta\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"💡 *Oisha topilgan profillarni Google Contacts eslatmalariga (note) muvaffaqiyatli saqladi va Oisha-OS bazasiga kiritdi.*"
            )

            if all_matches:
                details = "\n\n**Yangi mos kelgan kontaktlar:**\n"
                for m in all_matches[:30]:
                    tg_user = f"@{m['username']}" if m["username"] else f"ID: {m['user_id']}"
                    details += f"• {m['contact']['display_name']} -> {tg_user} ({m.get('method', 'Telefon')})\n"
                if len(all_matches) > 30:
                    details += f"*(va yana {len(all_matches) - 30} ta kontakt)*"
                report_msg += details

            await wait_msg.edit(report_msg, link_preview=False)

        except Exception as e:
            logger.error(f"❌ [GCONTACTS SYNC ERROR] {e}")
            await wait_msg.edit(f"❌ **Sinxronizatsiya davomida xatolik yuz berdi:** `{str(e)}`")
