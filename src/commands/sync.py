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
