"""
erp_handlers.py — Telegram command handlers for the Oisha-OS ERP module.

Each handler is a plain async function that accepts a message object
(aiogram Message or Telethon event) and a db connection, then replies
in Uzbek.  No Router / Dispatcher coupling — wire these up wherever
the project registers its command handlers.

Usage example (aiogram):
    from src.services.core.erp_handlers import COMMAND_REGISTRY, cmd_erp_holat
    # register manually or call directly:
    await cmd_erp_holat(message, db)

Usage example (Telethon):
    await cmd_erp_holat(event, db)
"""
from __future__ import annotations

import logging
from datetime import date
from typing import Optional

from src.services.core.erp_dashboard import ERPDashboard

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

async def _reply(message, text: str) -> None:
    """Send *text* back to the user regardless of framework in use.

    Tries in order:
      1. message.answer(text)  — aiogram Message
      2. message.reply(text)   — Telethon / generic
      3. message.respond(text) — Telethon ConversationMessage
    """
    fn = (
        getattr(message, "answer", None)
        or getattr(message, "reply", None)
        or getattr(message, "respond", None)
    )
    if callable(fn):
        await fn(text)
    else:
        logger.warning("_reply: cannot find a send method on %r", type(message))


def _sender_id(message) -> Optional[int]:
    """Extract the sender's Telegram user-id from either framework."""
    # aiogram
    from_user = getattr(message, "from_user", None)
    if from_user is not None:
        return getattr(from_user, "id", None)
    # Telethon
    sender_id = getattr(message, "sender_id", None)
    if sender_id is not None:
        return int(sender_id)
    return None


async def _check_permission(message) -> bool:
    """Return True if the sender is allowed to use ERP commands.

    Reads WHITELIST_IDS from project settings when available.
    Falls back to permitting all senders so the module works in
    dev/test environments without access-control configuration.
    """
    try:
        from src.settings import settings  # type: ignore[import]
        whitelist = getattr(settings, "WHITELIST_IDS", None) or []
        if not whitelist:
            return True
        sender = _sender_id(message)
        return sender in whitelist
    except Exception:
        # settings not importable (test context, etc.) — allow
        return True


def _current_period() -> str:
    return date.today().strftime("%Y-%m")


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------

async def cmd_erp_holat(message, db) -> None:
    """Umumiy ERP holati — /erp_holat

    Sends a one-line health summary followed by the complete monthly
    ERP report (Finance + HR + Projects).
    """
    if not await _check_permission(message):
        await _reply(message, "⛔ Sizda bu buyruq uchun ruxsat yo'q.")
        return

    try:
        dashboard = ERPDashboard(db)
        quick = await dashboard.format_quick_status()
        full = await dashboard.format_full_report()
        await _reply(message, f"{quick}\n\n{full}")
    except Exception as exc:
        logger.exception("cmd_erp_holat error: %s", exc)
        await _reply(
            message,
            "❌ ERP holati yuklanmadi. Iltimos, keyinroq urinib ko'ring.",
        )


async def cmd_moliya(message, db, period: Optional[str] = None) -> None:
    """Moliya hisoboti — /moliya [2025-06]

    Sends a detailed cash-flow and expense report.
    *period* defaults to the current calendar month (YYYY-MM).
    """
    if not await _check_permission(message):
        await _reply(message, "⛔ Sizda bu buyruq uchun ruxsat yo'q.")
        return

    try:
        eff_period = period or _current_period()
        dashboard = ERPDashboard(db)
        report = await dashboard.finance.format_cash_flow_report(eff_period)
        await _reply(message, report)
    except Exception as exc:
        logger.exception("cmd_moliya error: %s", exc)
        await _reply(
            message,
            "❌ Moliya hisoboti yuklanmadi. Iltimos, keyinroq urinib ko'ring.",
        )


async def cmd_jamoa(message, db, period: Optional[str] = None) -> None:
    """Jamoa KPI hisoboti — /jamoa [2025-06]

    Sends the full team and KPI report.
    *period* defaults to the current calendar month (YYYY-MM).
    """
    if not await _check_permission(message):
        await _reply(message, "⛔ Sizda bu buyruq uchun ruxsat yo'q.")
        return

    try:
        eff_period = period or _current_period()
        dashboard = ERPDashboard(db)
        report = await dashboard.hr.format_team_report(eff_period)
        await _reply(message, report)
    except Exception as exc:
        logger.exception("cmd_jamoa error: %s", exc)
        await _reply(
            message,
            "❌ Jamoa hisoboti yuklanmadi. Iltimos, keyinroq urinib ko'ring.",
        )


async def cmd_loyihalar(message, db) -> None:
    """Faol loyihalar — /loyihalar

    Sends the full project report with deadline status and payment
    progress for every non-completed project.
    """
    if not await _check_permission(message):
        await _reply(message, "⛔ Sizda bu buyruq uchun ruxsat yo'q.")
        return

    try:
        dashboard = ERPDashboard(db)
        report = await dashboard.projects.format_projects_report()
        await _reply(message, report)
    except Exception as exc:
        logger.exception("cmd_loyihalar error: %s", exc)
        await _reply(
            message,
            "❌ Loyihalar hisoboti yuklanmadi. Iltimos, keyinroq urinib ko'ring.",
        )


async def cmd_erp_salomatlik(message, db) -> None:
    """ERP sog'liqlik balli — /erp_salomatlik

    Computes a 0–100 health score across all ERP dimensions and
    reports identified issues with actionable recommendations.
    """
    if not await _check_permission(message):
        await _reply(message, "⛔ Sizda bu buyruq uchun ruxsat yo'q.")
        return

    try:
        dashboard = ERPDashboard(db)
        result = await dashboard.get_health_score()

        score: int = result["score"]
        status: str = result["status"]
        issues: list[str] = result["issues"]
        recommendations: list[str] = result["recommendations"]

        # Score bar (10 blocks, each = 10 pts)
        filled = score // 10
        bar = "█" * filled + "░" * (10 - filled)

        lines: list[str] = [
            "🏥 *ERP SOG'LIQLIK BAHOSI*",
            "",
            f"📊 Ball: *{score} / 100*",
            f"[{bar}]",
            f"🎯 Holat: {status}",
        ]

        if issues:
            lines += ["", "⚠️ *Muammolar:*"]
            for issue in issues:
                lines.append(f"  • {issue}")

        if recommendations:
            lines += ["", "💡 *Tavsiyalar:*"]
            for rec in recommendations:
                lines.append(f"  • {rec}")

        if not issues:
            lines += ["", "✅ Hech qanday muammo aniqlanmadi. Davom eting!"]

        await _reply(message, "\n".join(lines))
    except Exception as exc:
        logger.exception("cmd_erp_salomatlik error: %s", exc)
        await _reply(
            message,
            "❌ Sog'liqlik bahosi yuklanmadi. Iltimos, keyinroq urinib ko'ring.",
        )


async def cmd_qo_shish_loyiha(
    message,
    db,
    title: str,
    client: str,
    budget: int,
    deadline: str,
) -> None:
    """Yangi loyiha qo'shish — /loyiha_qosh [sarlavha] | [mijoz] | [byudjet] | [muddat]

    Creates a new project and confirms creation with the assigned ID.

    Callers are responsible for parsing the command arguments before
    calling this function.  Typical dispatcher wiring:

        text = message.text.removeprefix("/loyiha_qosh").strip()
        parts = [p.strip() for p in text.split("|")]
        if len(parts) == 4:
            await cmd_qo_shish_loyiha(
                message, db,
                title=parts[0], client=parts[1],
                budget=int(parts[2]), deadline=parts[3],
            )
    """
    if not await _check_permission(message):
        await _reply(message, "⛔ Sizda bu buyruq uchun ruxsat yo'q.")
        return

    try:
        if not title or not client:
            await _reply(
                message,
                "❌ Noto'g'ri format.\n"
                "Namuna: /loyiha_qosh Brend identifikatsiya | Tex Corp | 5000000 | 2025-08-01",
            )
            return

        if budget <= 0:
            await _reply(message, "❌ Byudjet musbat son bo'lishi kerak.")
            return

        dashboard = ERPDashboard(db)
        project_id = await dashboard.projects.create_project(
            title=title,
            client_name=client,
            amo_lead_id=None,
            budget=budget,
            deadline=deadline if deadline else None,
            assigned_to=None,
        )

        await _reply(
            message,
            f"✅ Yangi loyiha yaratildi!\n"
            f"🆔 ID: *{project_id}*\n"
            f"📌 Sarlavha: {title}\n"
            f"👤 Mijoz: {client}\n"
            f"💰 Byudjet: {budget:,} UZS\n"
            f"📅 Muddat: {deadline or 'belgilanmagan'}",
        )
    except ValueError as exc:
        logger.warning("cmd_qo_shish_loyiha validation error: %s", exc)
        await _reply(message, f"❌ Xatolik: {exc}")
    except Exception as exc:
        logger.exception("cmd_qo_shish_loyiha error: %s", exc)
        await _reply(
            message,
            "❌ Loyiha yaratilmadi. Iltimos, keyinroq urinib ko'ring.",
        )


async def cmd_xarajat_qosh(
    message,
    db,
    category: str,
    description: str,
    amount: int,
) -> None:
    """Xarajat qo'shish — /xarajat [kategoriya] | [tavsif] | [miqdor]

    Records a new expense and confirms with the assigned ID.

    Callers are responsible for parsing the command arguments before
    calling this function.  Typical dispatcher wiring:

        text = message.text.removeprefix("/xarajat").strip()
        parts = [p.strip() for p in text.split("|")]
        if len(parts) == 3:
            await cmd_xarajat_qosh(
                message, db,
                category=parts[0], description=parts[1],
                amount=int(parts[2]),
            )
    """
    if not await _check_permission(message):
        await _reply(message, "⛔ Sizda bu buyruq uchun ruxsat yo'q.")
        return

    try:
        if not category:
            await _reply(
                message,
                "❌ Noto'g'ri format.\n"
                "Namuna: /xarajat ofis | Printer qog'oz | 150000",
            )
            return

        if amount <= 0:
            await _reply(message, "❌ Miqdor musbat son bo'lishi kerak.")
            return

        sender = _sender_id(message)
        dashboard = ERPDashboard(db)
        expense_id = await dashboard.finance.add_expense(
            category=category,
            description=description or None,
            amount=amount,
            expense_date=None,   # defaults to today inside FinanceEngine
            recorded_by=sender,
        )

        await _reply(
            message,
            f"✅ Xarajat qo'shildi!\n"
            f"🆔 ID: *{expense_id}*\n"
            f"📂 Kategoriya: {category.capitalize()}\n"
            f"📝 Tavsif: {description or '—'}\n"
            f"💸 Miqdor: {amount:,} UZS",
        )
    except ValueError as exc:
        logger.warning("cmd_xarajat_qosh validation error: %s", exc)
        await _reply(message, f"❌ Xatolik: {exc}")
    except Exception as exc:
        logger.exception("cmd_xarajat_qosh error: %s", exc)
        await _reply(
            message,
            "❌ Xarajat qo'shilmadi. Iltimos, keyinroq urinib ko'ring.",
        )


# ---------------------------------------------------------------------------
# Command registry
# ---------------------------------------------------------------------------

COMMAND_REGISTRY: dict[str, object] = {
    "/erp_holat":      cmd_erp_holat,
    "/moliya":         cmd_moliya,
    "/jamoa":          cmd_jamoa,
    "/loyihalar":      cmd_loyihalar,
    "/erp_salomatlik": cmd_erp_salomatlik,
    "/loyiha_qosh":    cmd_qo_shish_loyiha,
    "/xarajat":        cmd_xarajat_qosh,
}

# ---------------------------------------------------------------------------
# Help text (Uzbek)
# ---------------------------------------------------------------------------

ERP_HELP_TEXT = """
🏢 *OISHA ERP — BUYRUQLAR RO'YXATI*

📊 *Holat va hisobotlar:*
  /erp_holat           — Umumiy ERP holati (moliya + jamoa + loyihalar)
  /erp_salomatlik      — ERP sog'liqlik balli (0–100) va tavsiyalar

💰 *Moliya:*
  /moliya              — Joriy oy moliyaviy hisoboti
  /moliya 2025-06      — Muayyan oy uchun moliyaviy hisobot
  /xarajat [kategoriya] | [tavsif] | [miqdor]
                       — Yangi xarajat qo'shish

👥 *Jamoa:*
  /jamoa               — Joriy oy jamoa va KPI hisoboti
  /jamoa 2025-06       — Muayyan oy uchun jamoa hisoboti

📁 *Loyihalar:*
  /loyihalar           — Barcha faol loyihalar ro'yxati
  /loyiha_qosh [sarlavha] | [mijoz] | [byudjet] | [muddat]
                       — Yangi loyiha yaratish

ℹ️ *Misollar:*
  /xarajat ofis | Printer qog'oz | 150000
  /loyiha_qosh Brend identifikatsiya | Tex Corp | 5000000 | 2025-08-01
  /moliya 2025-05
""".strip()
