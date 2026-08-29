import os
import io
import time
import json
import logging
import structlog
import asyncio
import psutil
import platform
from datetime import datetime
from telethon import events, Button, functions, types
from src.database import Database
from src.controllers.message_controller import MessageController
from src.time_utils import get_local_now, is_quiet_hours
from src.services.core.mission_control import MissionControl, MissionControlFetchError
from src.services.core.crm.crm_night_shift import CRMNightShift
from src.services.core.admin_command_router import (
    build_chatid_response,
    build_command_center_response,
    build_finance_risks_response,
    build_oisha_stats_response,
    build_project_risks_response,
    build_sales_priorities_response,
    build_start_response,
    build_team_capacity_response,
    resolve_start_role,
)
from src.services.core.business_command_center import (
    collect_business_command_snapshot,
    collect_finance_project_risks,
    collect_project_delivery_risks,
    collect_sales_today_priorities,
    collect_team_capacity_snapshot,
)
from src.services.core.telegram.bot_runtime import BotRuntimePort, TelethonBotRuntime
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

if TYPE_CHECKING:
    from src.services.utils.access_manager import AccessManager

logger = structlog.get_logger()

class AdminMissionSchedulerMixin:
    async def trigger_daily_missions(self):
        """Asosiy missiya taqsimlash logikasi."""
        try:
            from src.settings import settings

            if not settings.SALES_MANAGER_IDS:
                logger.warning("[ADMIN_BOT] trigger_daily_missions: No managers found.")
                return False

            mc = MissionControl(db=self.db)

            # Menejerlarni tayyorlaymiz
            managers = []
            for mid in settings.SALES_MANAGER_IDS:
                try:
                    entity = await self.bot_client.get_entity(mid)
                    name = entity.first_name or "Menejer"
                    username = f"@{entity.username}" if entity.username else name
                    managers.append({"id": mid, "name": name, "username": username})
                except Exception as e:
                    logger.error(f"Error getting entity for {mid}: {e}")
                    managers.append({"id": mid, "name": str(mid), "username": str(mid)})

            # Vazifalarni taqsimlaymiz
            try:
                distribution = await mc.distribute_missions(managers)
            except MissionControlFetchError as exc:
                logger.error(
                    f"[ADMIN_BOT] Mission fetch skipped because AmoCRM state is unknown: {exc}"
                )
                owner_id = getattr(self.access_manager, "owner_id", None)
                if owner_id:
                    try:
                        await self.bot_client.send_message(
                            owner_id,
                            "⚠️ AmoCRM pipeline holatini olib bo'lmadi.\n"
                            "Shu sabab jamoaga 'pipeline bo'sh' degan noto'g'ri signal yuborilmadi.\n\n"
                            f"Tafsilot: {exc}",
                        )
                    except Exception as owner_error:
                        logger.error(
                            f"[ADMIN_BOT] Failed to notify owner about AmoCRM issue: {owner_error}"
                        )
                return False

            if not distribution:
                await self.notify_team(
                    "📋 **Bugungi vazifalar:**\n\n"
                    "1️⃣ CLOSER'dagi mijozlardan boshlang'ich to'lovni oling\n"
                    "2️⃣ Mavjud lidlar bilan ishlang (follow-up, takliflar)\n"
                    "3️⃣ Eski mijozlarga qayta sotuv (upsell)\n\n"
                    "💡 <i>Yangi lid izlash — faqat yuqoridagilar tugagandan keyin!</i>",
                    topic_id=settings.CRM_TOPIC_ID,
                )
                return True

            # Hisobot
            full_report = f"👸 **AVTOMATIK KUNLIK MISSYALAR** ({datetime.now().strftime('%H:%M')}) 🚀\n\n"

            for manager in managers:
                mid = manager["id"]
                missions = distribution.get(mid, [])
                if not missions:
                    continue

                report = f"👤 {manager['username']} **uchun vazifalar:**\n"
                for i, m in enumerate(missions, 1):
                    report += (
                        f"{i}. [{m['lead_name']}]({m['link']})\n   ┗ {m['mission']}\n"
                    )
                full_report += report + "\n"

            await self.notify_team(
                full_report, topic_id=settings.CRM_TOPIC_ID, parse_mode="markdown"
            )
            return True

        except Exception as e:
            logger.error(f"[ADMIN_BOT] trigger_daily_missions error: {e}")
            return False

    async def _show_settings_menu(self, event, edit=False):
        """Tizim sozlamalarini ko'rsatish."""
        from src.settings import settings

        mode = settings.LEAD_DISTRIBUTION_MODE
        msg = f"⚙️ **TIZIM SOZLAMALARI**\n\n🎯 Taqsimot: `{mode}`"
        btns = [
            [
                Button.inline("CLAIM", b"set_dist_mode:CLAIM"),
                Button.inline("ROUND_ROBIN", b"set_dist_mode:ROUND_ROBIN"),
            ],
            [Button.inline("⬅️ Orqaga", b"dashboard")],
        ]
        if edit:
            await event.edit(msg, buttons=btns)
        else:
            await event.respond(msg, buttons=btns)

    async def _run_gcontacts_telegram_sync(self, event, wait_msg):
        from src.services.core.gcontacts import GoogleContactsSync
        from telethon import functions, types
        import random
        import re

        try:
            # 1. Initialize GoogleContactsSync
            gcontacts = GoogleContactsSync()
            if not gcontacts.service:
                await wait_msg.edit("❌ **Xatolik:** Google Contacts xizmatiga ulanib bo'lmadi. Sozlamalarni tekshiring.")
                return

            # 2. Fetch all Google Contacts
            contacts = gcontacts.list_all_contacts()
            if not contacts:
                await wait_msg.edit("ℹ️ **Google Contacts bo'sh yoki yuklab bo'lmadi.**")
                return

            total_contacts = len(contacts)
            await wait_msg.edit(f"📥 **{total_contacts} ta kontakt yuklandi.**\nTelefon raqamlari orqali Telegram akkauntlarini qidirish boshlandi... 👸🛡️")

            # 3. Filter contacts with phone numbers and normalize them
            phone_to_contact = {}
            for c in contacts:
                for phone in c["phones"]:
                    # Normalize
                    clean_phone = phone.replace(" ", "").replace("-", "").replace("(", "").replace(")", "").strip()
                    if clean_phone.startswith("8") and len(clean_phone) == 11 and clean_phone[1] == '9':
                        clean_phone = "998" + clean_phone[2:]
                    elif len(clean_phone) == 9:
                        clean_phone = "998" + clean_phone
                    
                    if not clean_phone.startswith("+"):
                        clean_phone = "+" + clean_phone
                    
                    phone_to_contact[clean_phone] = c

            total_phones = len(phone_to_contact)
            if total_phones == 0:
                await wait_msg.edit("ℹ️ **Telefon raqamiga ega birorta ham kontakt topilmadi.**")
                return

            await wait_msg.edit(
                f"📥 **{total_contacts} ta kontaktdan {total_phones} ta noyob telefon raqami topildi.**\n"
                f"Telegram userbot orqali qidirilmoqda (bu bir oz vaqt olishi mumkin)... ⏳"
            )

            # 4. Batch import phones via Userbot to lookup Telegram accounts
            matched_via_phone = {}
            phones_list = list(phone_to_contact.keys())
            batch_size = 50
            
            for i in range(0, len(phones_list), batch_size):
                batch = phones_list[i : i + batch_size]
                import_contacts = []
                for p in batch:
                    # Normalize clean phone for Telegram import
                    clean_p = p.replace("+", "").strip()
                    import_contacts.append(
                        types.InputPhoneContact(
                            client_id=random.randrange(-(2**63), 2**63),
                            phone=clean_p,
                            first_name="Oisha Sync",
                            last_name="",
                        )
                    )
                
                try:
                    # Import batch
                    result = await self.user_client(
                        functions.contacts.ImportContactsRequest(contacts=import_contacts)
                    )
                    
                    # Process matched users
                    if result.users:
                        user_ids = []
                        for user in result.users:
                            user_ids.append(user.id)
                            u_phone = getattr(user, "phone", "")
                            if u_phone:
                                norm_u_phone = "+" + u_phone.lstrip("+")
                                # Match with or without "+"
                                contact = phone_to_contact.get(norm_u_phone) or phone_to_contact.get(norm_u_phone.replace("+", ""))
                                if contact:
                                    matched_via_phone[norm_u_phone] = {
                                        "user_id": user.id,
                                        "username": user.username,
                                        "first_name": user.first_name,
                                        "last_name": user.last_name,
                                        "contact": contact,
                                    }
                        
                        # Clean up: delete imported contacts from userbot
                        if user_ids:
                            await self.user_client(
                                functions.contacts.DeleteContactsRequest(id=user_ids)
                            )
                except Exception as batch_err:
                    logger.error(f"[GCONTACTS SYNC] Batch import error: {batch_err}")

                # Send progress update
                progress = min(100, int((i + len(batch)) / total_phones * 100))
                await wait_msg.edit(
                    f"📥 **Telefon qidiruvi: {progress}% bajarildi...**\n"
                    f"Hozirgacha telefon orqali topilganlar: `{len(matched_via_phone)}` ta.\n"
                    f"Keyingi bosqich: TN guruhlarini tahlil qilish. 👸🛡️"
                )
                await asyncio.sleep(random.uniform(1.0, 2.5))

            # 5. Search inside "TN" groups for unmatched contacts
            await wait_msg.edit(
                f"📥 **Telefon qidiruvi tugadi.** Topilganlar: `{len(matched_via_phone)}` ta.\n"
                f"Endi TN guruhlaridan qolgan kontaktlarni qidirish boshlandi... 🔍"
            )

            # Find TN groups
            tn_groups = []
            dialogs = await self.user_client.get_dialogs(limit=300)
            for d in dialogs:
                if d.is_group or d.is_channel:
                    title = getattr(d, "name", "") or ""
                    title_upper = title.upper()
                    if "TN " in title_upper or " TN" in title_upper or "TEZ NATIJA" in title_upper or title_upper == "TN":
                        tn_groups.append(d)

            matched_via_groups = {}
            unmatched_contacts = [c for c in contacts if not any(p in matched_via_phone for p in c["phones"])]

            if tn_groups and unmatched_contacts:
                await wait_msg.edit(
                    f"👥 **{len(tn_groups)} ta TN guruhi topildi.**\n"
                    f"Guruh a'zolarini va oxirgi xabarlarni tahlil qilyapman... 🕵️‍♀️"
                )

                # Collect all unique members of TN groups
                group_members = {}  # user_id -> User
                for group in tn_groups:
                    try:
                        async for member in self.user_client.iter_participants(group.entity):
                            group_members[member.id] = member
                    except Exception as member_err:
                        logger.warning(f"Could not get members for group {group.name}: {member_err}")

                # Match unmatched contacts against group members by name
                for contact in unmatched_contacts:
                    c_disp = (contact["display_name"] or "").strip().lower()
                    c_given = (contact["given_name"] or "").strip().lower()
                    c_fam = (contact["family_name"] or "").strip().lower()

                    if not c_disp and not c_given:
                        continue

                    # Search in group members
                    for uid, member in group_members.items():
                        m_first = (member.first_name or "").strip().lower()
                        m_last = (member.last_name or "").strip().lower()
                        m_username = (member.username or "").strip().lower()

                        is_match = False
                        # High confidence name matching
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
                                "contact": contact,
                                "method": "TN Guruhi a'zosi",
                            }
                            break

            # 6. Save matches database and update Google Contacts notes
            all_matches = []
            for p, data in matched_via_phone.items():
                all_matches.append(data)
            for uid, data in matched_via_groups.items():
                # Avoid duplicates
                if not any(m["user_id"] == data["user_id"] for m in all_matches):
                    data["method"] = "TN guruhi a'zosi (Ism mosligi)"
                    all_matches.append(data)

            # Save to database and update Google Contacts note
            updated_gcontacts_count = 0
            for match in all_matches:
                c = match["contact"]
                tg_link = f"https://t.me/{match['username']}" if match["username"] else f"tg://user?id={match['user_id']}"
                
                # Check if note already has Telegram info
                current_note = c["note"] or ""
                if "Telegram:" not in current_note and "tg://user" not in current_note:
                    tg_info = f"\n[Telegram: @{match['username'] or 'yoq'} | ID: {match['user_id']} | Link: {tg_link}]"
                    new_note = (current_note + tg_info).strip()
                    success = gcontacts.update_contact_note(c["resource_name"], new_note)
                    if success:
                        updated_gcontacts_count += 1

                # Save to database `users` table
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

            # 7. Send final report
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

            # Show details of matches if any
            if all_matches:
                details = "\n\n**Yangi mos kelgan kontaktlar:**\n"
                for m in all_matches[:30]:  # Limit list to top 30 to prevent Telegram message length limit
                    tg_user = f"@{m['username']}" if m["username"] else f"ID: {m['user_id']}"
                    details += f"• {m['contact']['display_name']} -> {tg_user} ({m.get('method', 'Telefon')})\n"
                if len(all_matches) > 30:
                    details += f"*(va yana {len(all_matches) - 30} ta kontakt)*"
                report_msg += details

            await wait_msg.edit(report_msg, link_preview=False)

        except Exception as e:
            logger.error(f"❌ [GCONTACTS SYNC ERROR] {e}")
            await wait_msg.edit(f"❌ **Sinxronizatsiya davomida xatolik yuz berdi:** `{str(e)}`")
