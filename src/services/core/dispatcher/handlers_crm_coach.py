"""
CRM reporting and psychological sales coach aiogram message/command handlers.
"""
from __future__ import annotations

import logging
from typing import Any, Callable, Optional

from src.services.core.admin_command_router import (
    build_psychological_coach_response,
    build_sparring_response,
)

logger = logging.getLogger("AdminAiogramCRMCoach")

async def handle_aiogram_crm_report(
    message: Any,
    *,
    is_admin: Callable[[int], bool],
    get_amocrm_client: Optional[Callable[[], Any]] = None,
) -> None:
    sender = getattr(message, "from_user", None)
    sender_id = int(getattr(sender, "id", 0) or 0)
    if not is_admin(sender_id):
        return
    await message.answer("⏳ Oisha-OS: Kunlik hisobot (Reportagram) tayyorlanmoqda...")
    try:
        from src.services.core.crm.crm_daily_report import CRMDailyReporter

        amocrm_client = get_amocrm_client() if get_amocrm_client else None
        if not amocrm_client:
            from src.controllers.surgical_integration import get_surgical_integration
            surg = get_surgical_integration()
            if surg:
                amocrm_client = getattr(surg, "amocrm", None)

        reporter = CRMDailyReporter(amocrm=amocrm_client)
        stats = await reporter.fetch_stats()
        prev = reporter._load_prev_stats()
        report_text = reporter.format_report(stats, prev)
        await message.answer(report_text)
    except Exception as e:
        logger.error("Aiogram crm_report failed", exc_info=True)
        await message.answer(f"❌ Hisobot tayyorlashda xatolik: {e}")


async def handle_aiogram_crm_stats(
    message: Any,
    *,
    is_admin: Callable[[int], bool],
    get_amocrm_client: Optional[Callable[[], Any]] = None,
) -> None:
    sender = getattr(message, "from_user", None)
    sender_id = int(getattr(sender, "id", 0) or 0)
    if not is_admin(sender_id):
        return
    await message.answer("⏳ Joriy statistika olinmoqda...")
    try:
        from src.services.core.crm.crm_daily_report import CRMDailyReporter

        amocrm_client = get_amocrm_client() if get_amocrm_client else None
        if not amocrm_client:
            from src.controllers.surgical_integration import get_surgical_integration
            surg = get_surgical_integration()
            if surg:
                amocrm_client = getattr(surg, "amocrm", None)

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
        await message.answer(text, parse_mode="markdown")
    except Exception as e:
        logger.error("Aiogram crm_stats failed", exc_info=True)
        await message.answer(f"❌ Statistika olishda xatolik: {e}")


async def handle_aiogram_crm_history(
    message: Any,
    *,
    is_admin: Callable[[int], bool],
) -> None:
    sender = getattr(message, "from_user", None)
    sender_id = int(getattr(sender, "id", 0) or 0)
    if not is_admin(sender_id):
        return
    try:
        from src.services.core.crm.crm_daily_report import CRMDailyReporter

        reporter = CRMDailyReporter(amocrm=None)
        history = reporter.get_history(7)
        if not history:
            await message.answer("📅 Tarix topilmadi. Hisobotlar hali keshga yozilmagan.")
            return
        lines = ["📅 **So'nggi 7 kunlik hisobotlar tarixi:**"]
        for s in history:
            lines.append(
                f"• {s.date_label}: {s.total_leads} lead | {s.won} won | ${s.revenue:,.0f}"
            )
        await message.answer("\n".join(lines), parse_mode="markdown")
    except Exception:
        logger.error("Aiogram crm_history failed", exc_info=True)
async def handle_aiogram_psychological_coach(
    message: Any,
    *,
    is_admin: Callable[[int], bool],
    role_default: str = "sales",
) -> None:
    sender = getattr(message, "from_user", None)
    sender_id = int(getattr(sender, "id", 0) or 0)
    if not is_admin(sender_id):
        return
    text = (getattr(message, "text", "") or "").strip()
    parts = text.split(maxsplit=1)
    query = parts[1] if len(parts) > 1 else "telefon qilishga ikkilanyapman"
    role = "pm" if "/pm" in text.lower() else role_default
    response = build_psychological_coach_response(query, role=role)
    await message.answer(response.text, parse_mode=response.parse_mode)


async def handle_aiogram_sparring(
    message: Any,
    *,
    is_admin: Callable[[int], bool],
) -> None:
    sender = getattr(message, "from_user", None)
    sender_id = int(getattr(sender, "id", 0) or 0)
    if not is_admin(sender_id):
        return
    text = (getattr(message, "text", "") or "").strip()
    parts = text.split(maxsplit=1)
    scenario = parts[1] if len(parts) > 1 else "Mijoz qimmat deyapti"
    role = "pm" if "pm" in text.lower() else "sales"
    response = build_sparring_response(scenario, role=role)
    await message.answer(response.text, parse_mode=response.parse_mode)


async def handle_aiogram_fear_message(
    message: Any,
    *,
    is_admin: Callable[[int], bool],
) -> None:
    sender = getattr(message, "from_user", None)
    sender_id = int(getattr(sender, "id", 0) or 0)
    if not is_admin(sender_id):
        return
    text = (getattr(message, "text", "") or "").strip()
    response = build_psychological_coach_response(text)
    await message.answer(response.text, parse_mode=response.parse_mode)

