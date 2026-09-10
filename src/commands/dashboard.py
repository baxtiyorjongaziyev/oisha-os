"""Dashboard and stats commands."""
from __future__ import annotations

import logging
from datetime import datetime

from src.commands import register_command
from src.services.core.crm.daily_report import CRMPeriodReporter
from src.services.core.crm.daily_report.models import PeriodType

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


def _amocrm_from_ctx(msg_controller, get_surgical_integration):
    amocrm = None
    if msg_controller and getattr(msg_controller, "crm", None):
        amocrm = getattr(msg_controller.crm, "amocrm", None)
    if not amocrm:
        amocrm = get_surgical_integration().amocrm
    return amocrm


async def _run_period(event, ptype, msg_controller, get_surgical_integration):
    try:
        amocrm = _amocrm_from_ctx(msg_controller, get_surgical_integration)
        res = await CRMPeriodReporter(amocrm=amocrm).build(ptype)
        await event.respond(res.telegram_text)
    except Exception as e:
        logger.error("Exception handled in %s", __name__, exc_info=True)
        await event.respond(f"❌ Xatolik yuz berdi: {e}")


@register_command("/report")
async def cmd_report(event, **ctx):
    await event.respond("⏳ Oisha-OS: Kunlik CRM hisobot tayyorlanmoqda...")
    await _run_period(event, PeriodType.DAILY, ctx["msg_controller"], ctx["get_surgical_integration"])


@register_command("/report_week")
async def cmd_report_week(event, **ctx):
    await event.respond("⏳ Haftalik CRM hisobot tayyorlanmoqda...")
    await _run_period(event, PeriodType.WEEKLY, ctx["msg_controller"], ctx["get_surgical_integration"])


@register_command("/report_month")
async def cmd_report_month(event, **ctx):
    await event.respond("⏳ Oylik CRM hisobot tayyorlanmoqda...")
    await _run_period(event, PeriodType.MONTHLY, ctx["msg_controller"], ctx["get_surgical_integration"])


@register_command("/stats")
async def cmd_stats(event, **ctx):
    msg_controller = ctx["msg_controller"]
    get_surgical_integration = ctx["get_surgical_integration"]
    await event.respond("⏳ Joriy statistika olinmoqda...")
    try:
        amocrm_client = _amocrm_from_ctx(msg_controller, get_surgical_integration)
        reporter = CRMPeriodReporter(amocrm=amocrm_client)
        res = await reporter.build(PeriodType.DAILY)
        m = res.metrics
        text = (
            f"📊 **Bugungi holat ({m.date_label})**\n"
            f"Yangi bitimlar: {m.new_leads}\n"
            f"Faol: {m.active_count} ({m.active_amount:,.0f} so'm)\n".replace(",", " ")
            + f"Yutilgan: {m.won_count} | Daromad: {m.won_amount:,.0f} so'm\n".replace(",", " ")
            + f"Pipeline: {m.pipeline_value:,.0f} so'm".replace(",", " ")
        )
        await event.respond(text)
    except Exception as e:
        logger.error("Exception handled in %s", __name__, exc_info=True)
        await event.respond(f"❌ Xatolik: {e}")


@register_command("/history")
async def cmd_history(event, **ctx):
    try:
        reporter = CRMPeriodReporter(amocrm=None)
        history = reporter.list_snapshots(PeriodType.DAILY, 7)
        if not history:
            await event.respond("📅 Tarix topilmadi. Hisobotlar hali keshga yozilmagan.")
            return
        lines = ["📅 **So'nggi 7 kunlik CRM hisobotlar:**"]
        for s in history:
            lines.append(
                f"• {s.date_label}: {s.new_leads} lead | {s.won_count} won | {s.won_amount:,.0f} so'm".replace(",", " ")
            )
        await event.respond("\n".join(lines))
    except Exception as e:
        logger.error("Exception handled in %s", __name__, exc_info=True)
        await event.respond(f"❌ Xatolik: {e}")
