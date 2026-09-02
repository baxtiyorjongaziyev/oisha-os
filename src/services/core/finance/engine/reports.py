"""
Finance question generation, Telegram messages, debt, budget, and kassa mixin.
"""
from __future__ import annotations

import html
import logging
from typing import Optional

from src.services.core.finance.engine.helpers import _fmt_money

logger = logging.getLogger(__name__)


class ReportsMixin:
    """Handles notification message generation, debts, budgets, and balance transfers."""

    def build_finance_question(self, tx, tx_id: int) -> str:
        dir_icon = "➖ Chiqim" if tx.direction == "out" else "➕ Kirim"
        card_label = "HUMO" if tx.source_bot == "humo" else "UZCARD"
        question = (
            "Bu to'lov nima uchun ketdi?"
            if tx.direction == "out"
            else "Bu pul nima uchun keldi?"
        )
        balance_line = (
            f"\n💰 Qoldiq: {_fmt_money(tx.balance)} UZS" if tx.balance is not None else ""
        )
        return (
            f"💳 <b>Yangi to'lov #{tx_id}</b>\n\n"
            f"{dir_icon}: <b>{_fmt_money(tx.amount)} UZS</b>\n"
            f"📍 {html.escape(tx.merchant)}\n"
            f"🏦 {card_label} {html.escape(tx.card_suffix)}\n"
            f"🕓 {html.escape(tx.tx_time)}"
            f"{balance_line}\n\n"
            f"❓ <b>{question}</b>\n"
            f"Javob bering yoki <code>/skip {tx_id}</code>"
        )

    def build_auto_msg(self, tx, category: str, ownership: str = "business") -> str:
        dir_icon = "➖" if tx.direction == "out" else "➕"
        card_label = "HUMO" if tx.source_bot == "humo" else "UZCARD"
        own_label = "Biznes" if ownership == "business" else "Shaxsiy"
        return (
            f"✅ <b>Avtomatik saqlandi ({own_label})</b>\n"
            f"{dir_icon} {_fmt_money(tx.amount)} UZS — {card_label} {tx.card_suffix}\n"
            f"📍 {html.escape(tx.merchant)}\n"
            f"🗂 <b>{html.escape(category)}</b>"
        )

    def build_monthly_report(self, period: str, summary: dict) -> str:
        if "business" in summary:
            b_sum = summary["business"]
            p_sum = summary["personal"]
            b_net_icon = "📈" if b_sum["net"] >= 0 else "📉"
            p_net_icon = "📈" if p_sum["net"] >= 0 else "📉"
            b_cat_lines = "\n".join(
                f"  • {cat}: {_fmt_money(total)} UZS"
                for cat, total in list(b_sum["categories"].items())[:10]
            )
            p_cat_lines = "\n".join(
                f"  • {cat}: {_fmt_money(total)} UZS"
                for cat, total in list(p_sum["categories"].items())[:10]
            )
            return (
                f"📊 <b>Hisobchi hisoboti — {period}</b>\n\n"
                f"💼 <b>Biznes moliyasi:</b>\n"
                f"  ➕ Kirim:   <b>{_fmt_money(b_sum['income'])} UZS</b>\n"
                f"  ➖ Chiqim:  <b>{_fmt_money(b_sum['expense'])} UZS</b>\n"
                f"  {b_net_icon} Balans:  <b>{_fmt_money(b_sum['net'])} UZS</b>\n"
                f"  🗂 <b>Kategoriyalar:</b>\n{b_cat_lines or '  —'}\n\n"
                f"👤 <b>Shaxsiy moliya:</b>\n"
                f"  ➕ Kirim:   <b>{_fmt_money(p_sum['income'])} UZS</b>\n"
                f"  ➖ Chiqim:  <b>{_fmt_money(p_sum['expense'])} UZS</b>\n"
                f"  {p_net_icon} Balans:  <b>{_fmt_money(p_sum['net'])} UZS</b>\n"
                f"  🗂 <b>Kategoriyalar:</b>\n{p_cat_lines or '  —'}"
            )
        else:
            cat_lines = "\n".join(
                f"  • {cat}: {_fmt_money(total)} UZS"
                for cat, total in list(summary.get("categories", {}).items())[:10]
            )
            net_val = summary.get("net", 0)
            net_icon = "📈" if net_val >= 0 else "📉"
            return (
                f"📊 <b>Hisobchi hisoboti — {period}</b>\n\n"
                f"➕ Kirim:   <b>{_fmt_money(summary.get('income', 0))} UZS</b>\n"
                f"➖ Chiqim:  <b>{_fmt_money(summary.get('expense', 0))} UZS</b>\n"
                f"{net_icon} Balans:  <b>{_fmt_money(net_val)} UZS</b>\n\n"
                f"🗂 <b>Kategoriyalar:</b>\n{cat_lines or '  —'}"
            )

    # ── QARZ (DEBT) ────────────────────────────────────────────────────────

    async def add_debt(
        self, debt_type: str, person: str, amount: int,
        date: str = "", due_date: str = "", note: str = "",
    ) -> int:
        if self._gs:
            return await self._gs.add_debt(debt_type, person, amount, date, due_date, note)
        logger.warning("[HISOBCHI] add_debt not supported on SQL backend")
        return 0

    async def get_debts(self, active_only: bool = True) -> list[dict]:
        if self._gs:
            return await self._gs.get_debts(active_only)
        return []

    async def repay_debt(self, debt_id: int, amount: int) -> Optional[dict]:
        if self._gs:
            return await self._gs.repay_debt(debt_id, amount)
        return None

    # ── BYUDJET (BUDGET) ───────────────────────────────────────────────────

    async def set_budget(self, category: str, period: str, budget_limit: int) -> int:
        if self._gs:
            return await self._gs.set_budget(category, period, budget_limit)
        logger.warning("[HISOBCHI] set_budget not supported on SQL backend")
        return 0

    async def get_budget_status(self, period: str) -> list[dict]:
        if self._gs:
            return await self._gs.get_budget_status(period)
        return []

    async def update_budget_spent(self, period: str, category: str, spent: int) -> None:
        if self._gs:
            await self._gs.update_budget_spent(period, category, spent)

    # ── MAOSH (SALARY) ─────────────────────────────────────────────────────

    async def add_salary_entry(
        self, employee_name: str, entry_type: str, amount: int,
        period: str, note: str = "",
    ) -> int:
        if self._gs:
            return await self._gs.add_salary_entry(employee_name, entry_type, amount, period, note)
        logger.warning("[HISOBCHI] add_salary_entry not supported on SQL backend")
        return 0

    async def get_salary_summary(self, period: str) -> dict:
        if self._gs:
            return await self._gs.get_salary_summary(period)
        return {"total": 0, "oylik": 0, "avans": 0, "bonus": 0, "entries": []}

    # ── VALYUTA ────────────────────────────────────────────────────────────

    async def update_rate(self, currency: str, buy_rate: float, sell_rate: float, cb_rate: float = 0) -> None:
        if self._gs:
            return await self._gs.update_rate(currency, buy_rate, sell_rate, cb_rate)

    async def get_rates(self) -> dict:
        if self._gs:
            return await self._gs.get_rates()
        return {}

    # ── XODIMLAR ──────────────────────────────────────────────────────────

    async def add_xodim(self, name: str, role: str, telegram_id: str = "", phone: str = "", permission: str = "kuzatish") -> int:
        if self._gs:
            return await self._gs.add_xodim(name, role, telegram_id, phone, permission)
        return 0

    async def get_xodimlar(self, active_only: bool = True) -> list[dict]:
        if self._gs:
            return await self._gs.get_xodimlar(active_only)
        return []

    # ── KASSA & TRANSFER ──────────────────────────────────────────────────

    async def add_kassa(self, name: str, currency: str = "UZS", balance: int = 0, wallet_type: str = "Naqd", note: str = "") -> int:
        if self._gs:
            return await self._gs.add_kassa(name, currency, balance, wallet_type, note)
        return 0

    async def get_kassa(self, active_only: bool = True) -> list[dict]:
        if self._gs:
            return await self._gs.get_kassa(active_only)
        return []

    async def transfer_balance(self, from_kassa_id: int, to_kassa_id: int, amount: int, note: str = "") -> Optional[dict]:
        if self._gs:
            return await self._gs.transfer_balance(from_kassa_id, to_kassa_id, amount, note)
        return None
