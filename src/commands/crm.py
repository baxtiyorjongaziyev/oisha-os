"""CRM audit and report commands."""
from __future__ import annotations

import structlog

from src.commands import register_command

logger = structlog.get_logger()


@register_command("/junk_audit")
async def cmd_junk_audit(event, **ctx):
    msg_controller = ctx["msg_controller"]
    if msg_controller and msg_controller.enterprise_reporter:
        await event.respond(
            "🧹 **CRM Audit boshlandi...**\nOisha 'bekorchi' sdelkalarni qidirmoqda. Iltimos, kuting... ⏳"
        )
        try:
            report = await msg_controller.enterprise_reporter.get_junk_leads_report(
                limit=250
            )
            if len(report) > 4000:
                for chunk in [
                    report[i : i + 4000] for i in range(0, len(report), 4000)
                ]:
                    await event.respond(chunk)
            else:
                await event.respond(report)
        except Exception as e:
            logger.error(f"[COMMAND] /junk_audit error: {e}", exc_info=True)
            await event.respond(f"❌ **Auditda xato:** {str(e)}")
    else:
        await event.respond("❌ **Xato:** EnterpriseReporter topilmadi.")


@register_command("/stagnant")
async def cmd_stagnant(event, **ctx):
    msg_controller = ctx["msg_controller"]
    if msg_controller and msg_controller.enterprise_reporter:
        await event.respond("🔍 **Stagnatsiya tahlili boshlandi...**")
        try:
            alert = (
                await msg_controller.enterprise_reporter.get_stagnant_leads_alert()
            )
            if alert:
                await event.respond(alert)
            else:
                await event.respond(
                    "✅ **Hammasi joyida:** Hozircha 24 soatdan oshgan stagnant lidlar yo'q."
                )
        except Exception as e:
            logger.error(f"[COMMAND] /stagnant error: {e}", exc_info=True)
            await event.respond(f"❌ **Xato:** {str(e)}")
    else:
        await event.respond("❌ **Xato:** EnterpriseReporter topilmadi.")


@register_command("/contacts_audit")
async def cmd_contacts_audit(event, **ctx):
    msg_controller = ctx["msg_controller"]
    client = ctx["client"]
    get_surgical_integration = ctx["get_surgical_integration"]
    import asyncio
    global _crm_audit_running
    if _crm_audit_running:
        await event.respond("⚠️ **Audit allaqachon fonda ishlamoqda!**\nHisobot olish uchun `/contacts_report` yozing.")
        return

    parts = event.message.text.lower().strip().split()
    limit_val = 500
    force_val = False
    if len(parts) > 1:
        for part in parts[1:]:
            if part.isdigit():
                limit_val = int(part)
            elif part.lower() == "force":
                force_val = True

    await event.respond(
        f"🔍 **AmoCRM Kontaktlar Auditi boshlandi...**\n"
        f"🎯 Maqsad: {limit_val} ta bitimni tahlil qilish (force={force_val}).\n"
        f"Fonda ishlamoqda, tugagandan so'ng xabar beraman. Progressni ko'rish: `/contacts_report` ⏳"
    )

    async def run_audit_task():
        global _crm_audit_running
        _crm_audit_running = True
        try:
            amocrm_client = None
            if msg_controller and getattr(msg_controller, "crm", None):
                amocrm_client = getattr(msg_controller.crm, "amocrm", None)
            if not amocrm_client:
                amocrm_client = get_surgical_integration().amocrm

            db_instance = msg_controller.db
            tg_client = client

            from src.services.core.crm_contacts_auditor import CRMContactsAuditor
            auditor = CRMContactsAuditor(
                amocrm=amocrm_client,
                db=db_instance,
                tg_client=tg_client,
            )

            async def progress_cb(current, total, stats):
                cats_str = "\n".join(
                    f"• {k}: {v} ta" for k, v in stats["categories"].items()
                )
                progress_msg = (
                    f"📈 **CRM Audit Progress ({current}/{total})**\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"Tahlil qilindi: {stats['processed']} ta\n"
                    f"O'tkavib yuborildi (avval qilingan): {stats['skipped']} ta\n\n"
                    f"**Toifalar bo'yicha:**\n{cats_str}"
                )
                try:
                    await event.respond(progress_msg)
                except Exception as err:
                    logger.error(f"[AUDITOR CALLBACK] Failed to send progress: {err}")

            stats = await auditor.run_audit(
                limit=limit_val, progress_callback=progress_cb, force=force_val
            )

            cats_str = "\n".join(
                f"• {k}: {v} ta" for k, v in stats["categories"].items()
            )
            final_msg = (
                f"🏁 **CRM AUDIT YAKUNLANDI!**\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"Jami tekshirildi: {stats['total_leads']} ta bitim\n"
                f"Tahlil qilindi: {stats['processed']} ta\n"
                f"O'tkazib yuborildi: {stats['skipped']} ta\n\n"
                f"**Toifalar bo'yicha yakuniy natijalar:**\n{cats_str}\n\n"
                f"💡 *Batafsil hisobot matnini olish uchun `/contacts_report` deb yozing.*"
            )
            await event.respond(final_msg)

        except Exception as e:
            logger.error(f"[AUDITOR TASK] Failed: {e}", exc_info=True)
            try:
                await event.respond(f"❌ **Audit jarayonida xatolik yuz berdi:** {str(e)}")
            except Exception:
                logger.warning(
                    "[CRM] failed to send error message to user after audit task failure",
                    exc_info=True,
                )
        finally:
            _crm_audit_running = False

    asyncio.create_task(run_audit_task())


@register_command("/contacts_report")
async def cmd_contacts_report(event, **ctx):
    msg_controller = ctx["msg_controller"]
    await event.respond("📊 **Audit hisoboti tayyorlanmoqda...**")
    try:
        import inspect
        async def _local_maybe_await(value):
            if inspect.isawaitable(value):
                return await value
            return value

        db_instance = msg_controller.db
        conn = await db_instance.get_connection()
        
        await _local_maybe_await(
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS crm_contacts_audit (
                    lead_id INTEGER PRIMARY KEY,
                    lead_name TEXT,
                    contact_id INTEGER,
                    contact_name TEXT,
                    phone TEXT,
                    username TEXT,
                    telegram_user_id INTEGER,
                    call_summary TEXT,
                    telegram_history TEXT,
                    category TEXT,
                    explanation TEXT,
                    audited_at TEXT
                )
                """
            )
        )
        await _local_maybe_await(conn.commit())
        
        cursor = await _local_maybe_await(conn.execute("SELECT COUNT(*), category FROM crm_contacts_audit GROUP BY category"))
        rows = await _local_maybe_await(cursor.fetchall())
        
        total_audited = 0
        cats = {
            "Mijoz": 0,
            "Shaxsiy": 0,
            "Kandidat": 0,
            "Hamkor/Jamoa": 0,
            "Boshqa": 0
        }
        for count, cat in rows:
            if cat in cats:
                cats[cat] = count
            total_audited += count

        if total_audited == 0:
            await event.respond("📊 **Hozircha audit natijalari mavjud emas.**\nAuditni boshlash uchun `/contacts_audit` yozing.")
            return

        cursor = await _local_maybe_await(conn.execute(
            "SELECT lead_id, contact_name, category, phone, username FROM crm_contacts_audit ORDER BY audited_at DESC LIMIT 5"
        ))
        latest_rows = await _local_maybe_await(cursor.fetchall())
        latest_lines = []
        for lid, name, cat, phone, username in latest_rows:
            tg_info = f" (@{username})" if username else ""
            phone_info = f" ({phone})" if phone else ""
            latest_lines.append(f"• [ID {lid}] {name}{phone_info}{tg_info} ➔ **{cat}**")
        
        latest_str = "\n".join(latest_lines) if latest_lines else "Topilmadi"

        report = (
            f"📊 **CRM KONTAKTLAR AUDITI HISOBOTI**\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"Jami audit qilingan: {total_audited} ta kontakt\n\n"
            f"**Toifalar bo'yicha taqsimot:**\n"
            f"• Mijoz: {cats['Mijoz']} ta ({(cats['Mijoz']/total_audited)*100:.1f}%)\n"
            f"• Shaxsiy: {cats['Shaxsiy']} ta ({(cats['Shaxsiy']/total_audited)*100:.1f}%)\n"
            f"• Kandidat: {cats['Kandidat']} ta ({(cats['Kandidat']/total_audited)*100:.1f}%)\n"
            f"• Hamkor/Jamoa: {cats['Hamkor/Jamoa']} ta ({(cats['Hamkor/Jamoa']/total_audited)*100:.1f}%)\n"
            f"• Boshqa: {cats['Boshqa']} ta ({(cats['Boshqa']/total_audited)*100:.1f}%)\n\n"
            f"**So'nggi tahlil qilingan 5 ta kontakt:**\n{latest_str}\n\n"
            f"💡 *Jarayonni qaytadan boshlash uchun `/contacts_reset` yozishingiz mumkin.*"
        )
        await event.respond(report)
    except Exception as e:
        logger.error(f"[COMMAND] /contacts_report error: {e}", exc_info=True)
        await event.respond(f"❌ **Hisobot tayyorlashda xato:** {str(e)}")


@register_command("/contacts_reset")
async def cmd_contacts_reset(event, **ctx):
    msg_controller = ctx["msg_controller"]
    await event.respond("⏳ **Audit ma'lumotlari tozalanmoqda...**")
    try:
        import inspect
        async def _local_maybe_await(value):
            if inspect.isawaitable(value):
                return await value
            return value

        db_instance = msg_controller.db
        conn = await db_instance.get_connection()
        
        await _local_maybe_await(
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS crm_contacts_audit (
                    lead_id INTEGER PRIMARY KEY,
                    lead_name TEXT,
                    contact_id INTEGER,
                    contact_name TEXT,
                    phone TEXT,
                    username TEXT,
                    telegram_user_id INTEGER,
                    call_summary TEXT,
                    telegram_history TEXT,
                    category TEXT,
                    explanation TEXT,
                    audited_at TEXT
                )
                """
            )
        )
        await _local_maybe_await(conn.commit())
        
        await _local_maybe_await(conn.execute("DELETE FROM crm_contacts_audit"))
        await _local_maybe_await(conn.commit())
        await event.respond("✅ **Audit ma'lumotlari muvaffaqiyatli tozalandi!**\nEndi `/contacts_audit` orqali yangi audit boshlashingiz mumkin.")
    except Exception as e:
        logger.error(f"[COMMAND] /contacts_reset error: {e}", exc_info=True)
        await event.respond(f"❌ **Tozalashda xatolik yuz berdi:** {str(e)}")
