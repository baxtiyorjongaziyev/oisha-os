"""
Read-only report commands for ERP.
"""
from __future__ import annotations

import logging
from typing import Optional

from src.services.core.finance.erp_dashboard import ERPDashboard
from src.services.core.finance.erp.helpers import (
    _check_permission,
    _current_period,
    _reply,
)

logger = logging.getLogger(__name__)


async def cmd_erp_holat(message, db) -> None:
    """Umumiy ERP holati — /erp_holat"""
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
    """Moliya hisoboti — /moliya [2025-06]"""
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
    """Jamoa KPI hisoboti — /jamoa [2025-06]"""
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
    """Faol loyihalar — /loyihalar"""
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
    """ERP sog'liqlik balli — /erp_salomatlik"""
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
