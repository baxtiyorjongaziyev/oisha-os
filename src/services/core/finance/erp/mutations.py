"""
Mutation commands for ERP (creating projects, adding expenses).
"""
from __future__ import annotations

import logging
from src.services.core.finance.erp_dashboard import ERPDashboard
from src.services.core.finance.erp.helpers import (
    _check_permission,
    _reply,
    _sender_id,
)

logger = logging.getLogger(__name__)


async def cmd_qo_shish_loyiha(
    message,
    db,
    title: str,
    client: str,
    budget: int,
    deadline: str,
) -> None:
    """Yangi loyiha qo'shish — /loyiha_qosh [sarlavha] | [mijoz] | [byudjet] | [muddat]"""
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
    """Xarajat qo'shish — /xarajat [kategoriya] | [tavsif] | [miqdor]"""
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
            expense_date=None,
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
