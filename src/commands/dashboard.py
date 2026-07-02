"""Dashboard and stats commands."""
from __future__ import annotations

import logging
from datetime import datetime

from src.commands import register_command

logger = logging.getLogger(__name__)


@register_command("/dashboard")
async def cmd_dashboard(event, **ctx):
    msg_controller = ctx["msg_controller"]
    stats = await msg_controller.db.get_today_stats()
    msg = (
        "📊 **OISHA ROI DASHBOARD**\n"
        f"📅 Bugun: {datetime.now().strftime('%d-%m-%Y')}\n\n"
        f"👤 **Yangi lidlar:** {stats['leads_found']} ta\n"
        f"💬 **Sinxron chatlar:** {stats['messages_synced']} ta\n"
        f"👥 **Kontaktlar (Mass):** {stats['contacts_added']} ta\n"
        f"🤝 **DM Lidar:** {stats['private_chats']} ta\n\n"
        "✅ *Oisha hozirda fonda muvaffaqiyatli ishlamoqda.*"
    )
    await event.respond(msg)


@register_command("/lead_cockpit", "/pipeline")
async def cmd_lead_cockpit(event, **ctx):
    msg_controller = ctx["msg_controller"]
    from src.services.core.leads.lead_operating_system import LeadOperatingSystem
    lead_os = LeadOperatingSystem(msg_controller, msg_controller.db)
    report = await lead_os.render_cockpit_report(limit=12, lookback_hours=72)
    await event.respond(report, parse_mode="HTML")


@register_command("/status")
async def cmd_status(event, **ctx):
    await event.respond("🟢 **Oisha Engine:** Active\n🛰 **Server:** GCP Cloud Run")


@register_command("/report")
async def cmd_report(event, **ctx):
    msg_controller = ctx["msg_controller"]
    get_surgical_integration = ctx["get_surgical_integration"]
    await event.respond("⏳ Oisha-OS: Kunlik hisobot (Reportagram) tayyorlanmoqda...")
    try:
        from src.services.core.crm.crm_daily_report import CRMDailyReporter
        amocrm_client = None
        if msg_controller and getattr(msg_controller, "crm", None):
            amocrm_client = getattr(msg_controller.crm, "amocrm", None)
        if not amocrm_client:
            amocrm_client = get_surgical_integration().amocrm
        
        reporter = CRMDailyReporter(amocrm=amocrm_client)
        stats = await reporter.fetch_stats()
        prev = reporter._load_prev_stats()
        report_text = reporter.format_report(stats, prev)
        await event.respond(report_text)
    except Exception as e:
        await event.respond(f"❌ Xatolik yuz berdi: {e}")


@register_command("/stats")
async def cmd_stats(event, **ctx):
    msg_controller = ctx["msg_controller"]
    get_surgical_integration = ctx["get_surgical_integration"]
    await event.respond("⏳ Joriy statistika olinmoqda...")
    try:
        from src.services.core.crm.crm_daily_report import CRMDailyReporter
        amocrm_client = None
        if msg_controller and getattr(msg_controller, "crm", None):
            amocrm_client = getattr(msg_controller.crm, "amocrm", None)
        if not amocrm_client:
            amocrm_client = get_surgical_integration().amocrm
        
        reporter = CRMDailyReporter(amocrm=amocrm_client)
        stats = await reporter.fetch_stats()
        text = (
            f"📊 **Bugungi holat ({stats.date_label})**\n"
            f"Tushgan: {stats.total_leads} lead\n"
            f"Gaplashilgan: {stats.contacted} lead\n"
            f"Sifatli: {stats.qualified} lead\n"
            f"Muvaffaqiyatli (Won): {stats.won}\n"
            f"Daromad: ${stats.revenue:,.0f}\n"
            f"Pipeline qiymati: ${stats.pipeline_value:,.0f}"
        )
        await event.respond(text)
    except Exception as e:
        await event.respond(f"❌ Xatolik: {e}")


@register_command("/history")
async def cmd_history(event, **ctx):
    try:
        from src.services.core.crm.crm_daily_report import CRMDailyReporter
        reporter = CRMDailyReporter(amocrm=None)
        history = reporter.get_history(7)
        if not history:
            await event.respond("📅 Tarix topilmadi. Hisobotlar hali keshga yozilmagan.")
            return
        lines = ["📅 **So'nggi 7 kunlik hisobotlar tarixi:**"]
        for s in history:
            lines.append(
                f"• {s.date_label}: {s.total_leads} lead | {s.won} won | ${s.revenue:,.0f}"
            )
        await event.respond("\n".join(lines))
    except Exception as e:
        await event.respond(f"❌ Xatolik: {e}")
