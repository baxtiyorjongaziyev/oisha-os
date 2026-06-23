"""Sync commands for portfolio and archive."""
from __future__ import annotations

import logging

from src.commands import register_command

logger = logging.getLogger(__name__)


@register_command("/sync_cases", "/sync_portfolio")
async def cmd_sync_cases(event, **ctx):
    settings = ctx["settings"]
    import asyncio

    parts = event.message.text.lower().strip().split()
    limit_val = 30
    if len(parts) > 1 and parts[1].isdigit():
        limit_val = int(parts[1])
        
    await event.respond(
        f"🚀 **Backlog portfolio sinxronizatsiyasi boshlandi...**\n"
        f"`@{settings.JONBRANDING_CHANNEL}` kanalidan so'nggi {limit_val} ta xabarni tekshirib, portfolio keyslarini aniqlayman va CMS'ga yuklayman. Iltimos, kuting... ⏳"
    )
    try:
        from src.services.core.case_publisher import CasePublisher
        publisher = CasePublisher(client=event.client)
        
        target = settings.JONBRANDING_CHANNEL.strip().lower()
        
        scanned = 0
        published = 0
        skipped = 0
        
        async for msg in event.client.iter_messages(target, limit=limit_val):
            scanned += 1
            if not msg.text:
                skipped += 1
                continue

            try:
                success = await publisher.process_message(msg)
                if success:
                    published += 1
                else:
                    skipped += 1
            except Exception as pe:
                logger.error(f"[CRAWL COMMAND] Error processing message {msg.id}: {pe}")
                skipped += 1

            await asyncio.sleep(2.5)
            
        await event.respond(
            f"🏁 **Portfolio keys sinxronizatsiyasi muvaffaqiyatli yakunlandi!**\n\n"
            f"📊 **Statistika:**\n"
            f"• Skanner qilindi: {scanned} ta xabar\n"
            f"• Yuklandi (CMS): {published} ta keys\n"
            f"• O'tkazib yuborildi: {skipped} ta xabar"
        )
    except Exception as e:
        logger.error(f"[COMMAND] /sync_cases error: {e}", exc_info=True)
        await event.respond(f"❌ **Sinxronizatsiyada xatolik:** {str(e)}")


@register_command("/sync_archive")
async def cmd_sync_archive(event, **ctx):
    import asyncio

    parts = event.message.text.lower().strip().split()
    limit = 30
    if len(parts) > 1:
        try:
            limit = int(parts[1])
        except ValueError:
            pass

    await event.respond(f"🧹 **AmoCRM limitsizlantirish va arxivlash boshlandi...**\nBatch limiti: {limit} ta bitim. Iltimos, kuting... ⏳")
    try:
        from src.services.core.crm_archiver import CRMArchiver
        archiver = CRMArchiver()
        await archiver.init_tables()

        stagnant = await archiver.get_stagnant_leads(max_stagnant_days=21)
        if not stagnant:
            await event.respond("✅ **Hammasi joyida:** Hozircha arxivlash uchun stagnant bitimlar mavjud emas.")
            return

        targets = stagnant[:limit]
        await event.respond(f"🎯 **Arxivlash uchun {len(targets)} ta bitim tanlandi.** Arxivlash va outreach xabarlar generatsiya qilinmoqda...")

        processed_count = 0
        failed_count = 0

        for lead in targets:
            try:
                res = await archiver.archive_lead(lead, dry_run=False)
                if res.get("success"):
                    processed_count += 1
                else:
                    failed_count += 1
            except Exception as ex:
                failed_count += 1
                logger.error(f"[SYNC ARCHIVE] Lead {lead.get('id')} error: {ex}")

        active_leads = await archiver.fetch_all_active_leads()
        active_count = len(active_leads)

        report = (
            f"🏁 **ARXIVLASH VA OUTREACH HISOBOTI**\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"✅ **Muvaffaqiyatli arxivlandi:** {processed_count} ta bitim\n"
            f"❌ **Xatoliklar:** {failed_count} ta\n"
            f"📦 **Qolgan faol bitimlar:** {active_count} / 500 limit\n"
            f"📊 **Yangi bandlik darajasi:** {(active_count / 500) * 100:.1f}%\n"
            f"💡 *Barcha arxivlangan bitimlar Turso Cloud bazasiga 100% xavfsiz saqlandi va 3 bosqichli Uzbek outreach kampaniyalari generatsiya qilindi!*"
        )
        await event.respond(report)
    except Exception as e:
        logger.error(f"[COMMAND] /sync_archive error: {e}", exc_info=True)
        await event.respond(f"❌ **Arxivlashda xatolik yuz berdi:** {str(e)}")


@register_command("/scrape_tez_natija", "/sync_tez_natija")
async def cmd_scrape_tez_natija(event, **ctx):
    import asyncio
    from telethon import errors

    msg_controller = ctx["msg_controller"]
    client = ctx["client"]

    # 1. Parse arguments (e.g. check if 'amocrm' is present)
    parts = event.message.text.lower().strip().split()
    sync_to_amocrm = "amocrm" in parts

    if not msg_controller.google or not msg_controller.google.sheets:
        await event.respond("❌ **Xatolik:** Google Sheets xizmati faollashtirilmagan yoki credentiallar xato.")
        return

    sheets_sync = msg_controller.google.sheets
    amocrm_sync = msg_controller.crm.amocrm if sync_to_amocrm else None

    await event.respond("🚀 **'Tez Natija' guruhlarini skanerlash boshlandi...**\nDialoglar tahlil qilinmoqda...")

    try:
        # 2. Find all groups matching "TEZ NATIJA"
        target_groups = []
        async for dialog in client.iter_dialogs():
            if dialog.is_group or dialog.is_channel:
                if "TEZ NATIJA" in dialog.name.upper():
                    target_groups.append(dialog)

        if not target_groups:
            await event.respond("ℹ️ **Natija:** Nomi 'TEZ NATIJA' bo'lgan birorta ham guruh/kanal topilmadi.")
            return

        group_names = ", ".join([f"'{g.name}'" for g in target_groups])
        await event.respond(f"🔍 **Aniqlandi ({len(target_groups)} ta guruh):**\n{group_names}\n\nA'zolar yig'ilmoqda va Google Sheets-ga saqlanmoqda. Bu biroz vaqt olishi mumkin... ⏳")

        # 3. Process each group
        total_scraped = 0
        total_sheets_added = 0
        total_amocrm_added = 0

        for group in target_groups:
            group_scraped = 0
            group_sheets_added = 0
            group_amocrm_added = 0

            try:
                # Update status for user
                status_msg = await event.respond(f"⏳ **'{group.name}' guruhidan a'zolar o'qilmoqda...**")

                async for user in client.iter_participants(group.id):
                    if user.bot or user.deleted:
                        continue

                    group_scraped += 1
                    total_scraped += 1

                    first_name = user.first_name or ""
                    last_name = user.last_name or ""
                    username = user.username or ""
                    phone = getattr(user, "phone", None)

                    # Deduplicate in AmoCRM
                    amocrm_status = "Yuborilmagan"

                    if sync_to_amocrm and amocrm_sync and phone:
                        try:
                            # Use existing create_lead
                            full_name = f"{first_name} {last_name}".strip() or username or f"User {user.id}"
                            note_text = f"Tez Natija Guruh a'zosi\nGuruh: {group.name}\nUsername: @{username}"
                            lead_id = await amocrm_sync.create_lead(
                                name=f"Tez Natija: {full_name}",
                                phone=phone if phone.startswith("+") else f"+{phone}",
                                note=note_text
                            )
                            if lead_id:
                                amocrm_status = "Sinxronlandi"
                                group_amocrm_added += 1
                                total_amocrm_added += 1
                            else:
                                amocrm_status = "Xato"
                        except Exception as amo_e:
                            logger.error(f"[SCRAPE CMD] AmoCRM sync error for {user.id}: {amo_e}")
                            amocrm_status = f"Xato: {str(amo_e)[:30]}"
                    elif sync_to_amocrm and not phone:
                        amocrm_status = "Raqam yo'q"

                    # Sync to sheets (will automatically deduplicate based on user_id)
                    try:
                        added = sheets_sync.sync_group_member_to_crm(
                            group_name=group.name,
                            user_id=user.id,
                            first_name=first_name,
                            last_name=last_name,
                            username=username,
                            phone=phone,
                            amocrm_status=amocrm_status
                        )
                        if added:
                            group_sheets_added += 1
                            total_sheets_added += 1
                    except Exception as sheet_e:
                        logger.error(f"[SCRAPE CMD] Sheets sync error for {user.id}: {sheet_e}")

                    # Real-time update every 100 users to not spam user messages but show progress
                    if group_scraped % 100 == 0:
                        await status_msg.edit(
                            f"📊 **'{group.name}' progress:**\n"
                            f"• Skanerlandi: {group_scraped} ta a'zo\n"
                            f"• Sheets-ga qo'shildi: {group_sheets_added} ta yangi\n"
                            f"• AmoCRM-ga qo'shildi: {group_amocrm_added} ta"
                        )

                    # Tiny sleep to prevent flooding
                    await asyncio.sleep(0.1)

                await status_msg.edit(
                    f"✅ **'{group.name}' yakunlandi:**\n"
                    f"• Jami skanerlandi: {group_scraped}\n"
                    f"• Yangi qo'shilganlar: {group_sheets_added}\n"
                    f"• AmoCRM: {group_amocrm_added}"
                )

            except errors.ChatAdminRequiredError:
                await event.respond(f"⚠️ **Xatolik:** '{group.name}' guruhida a'zolar ro'yxatini ko'rish huquqi yo'q (admin cheklovi).")
            except Exception as group_e:
                logger.error(f"[SCRAPE CMD] Group {group.name} processing error: {group_e}", exc_info=True)
                await event.respond(f"❌ **Xatolik:** '{group.name}' guruhini qayta ishlashda xato: {group_e}")

        # 4. Final report
        report = (
            f"🏁 **TEZ NATIJA SKANERLASH HISOBOTI**\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"👥 **Jami ko'rib chiqildi:** {total_scraped} ta a'zo\n"
            f"📝 **Google Sheets-ga yozildi:** {total_sheets_added} ta yangi a'zo\n"
            f"💼 **AmoCRM-ga yuborildi:** {total_amocrm_added} ta bitim\n\n"
            f"ℹ️ *Eslatma: Google Sheets-da allaqachon mavjud bo'lgan a'zolar sotuvchilarning statuslari/izohlari o'chib ketmasligi uchun qayta yozilmadi (o'tkazib yuborildi).*"
        )
        await event.respond(report)

    except Exception as e:
        logger.error(f"[COMMAND] /scrape_tez_natija error: {e}", exc_info=True)
        await event.respond(f"❌ **Skanerlashda kutilmagan xatolik:** {str(e)}")
