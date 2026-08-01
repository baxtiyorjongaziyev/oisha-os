"""Hisobchi AI Analyst — Cleo-like financial insights, recommendations, forecasting."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from src.settings import settings
from src.services.utils.gemini_fallback import generate_content_with_fallback

logger = logging.getLogger(__name__)


def _month_name(period: str) -> str:
    names = {
        "01": "Yanvar", "02": "Fevral", "03": "Mart", "04": "Aprel",
        "05": "May", "06": "Iyun", "07": "Iyul", "08": "Avgust",
        "09": "Sentabr", "10": "Oktabr", "11": "Noyabr", "12": "Dekabr",
    }
    parts = period.split("-")
    if len(parts) == 2:
        return f"{names.get(parts[1], parts[1])} {parts[0]}"
    return period


def _fmt(amount: int) -> str:
    return f"{amount:,}".replace(",", " ")


def _uzs_line(label: str, amount: int, usd_amount: int = 0, rate: float = 0) -> str:
    """Format a line with UZS and optional USD equivalent."""
    if usd_amount and rate:
        usd_total = usd_amount
        uzs_equiv = int(usd_total * rate)
        total_uzs = amount
        return f"{label} <b>{_fmt(total_uzs)} UZS</b> (~{_fmt(uzs_equiv)} UZS + {_fmt(usd_total)}$)"
    return f"{label} <b>{_fmt(amount)} UZS</b>"


class HisobchiAnalyst:
    def __init__(self, engine: Any, gemini_client: Any) -> None:
        self.engine = engine
        self.client = gemini_client

    async def _get_usd_rate(self) -> float:
        try:
            if hasattr(self.engine, "_gs") and self.engine._gs:
                rates = await self.engine._gs.get_rates()
                if "USD" in rates:
                    return float(rates["USD"].get("cb_rate", 0) or rates["USD"].get("sell_rate", 0) or 0)
        except Exception:
            logger.error("Exception handled in %s", __name__, exc_info=True)
        return 0

    async def analyze_month(self, period: str) -> str:
        summary = await self.engine.get_monthly_summary(period)
        b = summary.get("business", {})
        p = summary.get("personal", {})
        rate = await self._get_usd_rate()
        data = {
            "month": _month_name(period),
            "period": period,
            "usd_rate": rate,
            "business": {
                "income": b.get("income", 0),
                "expense": b.get("expense", 0),
                "net": b.get("net", 0),
                "usd_income": b.get("usd_income", 0),
                "usd_expense": b.get("usd_expense", 0),
                "categories": dict(list(b.get("categories", {}).items())[:10]),
            },
            "personal": {
                "income": p.get("income", 0),
                "expense": p.get("expense", 0),
                "net": p.get("net", 0),
                "usd_income": p.get("usd_income", 0),
                "usd_expense": p.get("usd_expense", 0),
                "categories": dict(list(p.get("categories", {}).items())[:5]),
            },
        }

        parts = period.split("-")
        prev_period = f"{parts[0]}-{int(parts[1]) - 1:02d}" if int(parts[1]) > 1 else f"{int(parts[0]) - 1}-12"
        prev_summary = await self.engine.get_monthly_summary(prev_period)

        debt_info = ""
        if hasattr(self.engine, "_gs") and self.engine._gs:
            try:
                debts = await self.engine._gs.get_debts(active_only=True)
                if debts:
                    debt_info = "\nFaol qarzlar:\n" + "\n".join(
                        f"  - {d['person']}: {_fmt(d['remaining'])} UZS ({d['debt_type']})"
                        for d in debts[:5]
                    )
            except Exception:
                logger.error("Exception handled in %s", __name__, exc_info=True)

        budget_info = ""
        if hasattr(self.engine, "_gs") and self.engine._gs:
            try:
                budgets = await self.engine._gs.get_budget_status(period)
                if budgets:
                    budget_info = "\nByudjet holati:\n" + "\n".join(
                        f"  - {b['category']}: {_fmt(b['spent'])} / {_fmt(b['budget_limit'])} UZS [{b['status']}]"
                        for b in budgets[:5]
                    )
            except Exception:
                logger.error("Exception handled in %s", __name__, exc_info=True)

        salary_info = ""
        if hasattr(self.engine, "_gs") and self.engine._gs:
            try:
                salary = await self.engine._gs.get_salary_summary(period)
                if salary["total"] > 0:
                    salary_info = f"\nMaosh xarajati: {_fmt(salary['total'])} UZS"
            except Exception:
                logger.error("Exception handled in %s", __name__, exc_info=True)

        prev_b = prev_summary.get("business", {})
        prev_p = prev_summary.get("personal", {})
        prev_data = {
            "business": {"income": prev_b.get("income", 0), "expense": prev_b.get("expense", 0), "net": prev_b.get("net", 0)},
            "personal": {"income": prev_p.get("income", 0), "expense": prev_p.get("expense", 0), "net": prev_p.get("net", 0)},
        }

        system_prompt = (
            "Sen Hisobchi — Oisha OS ning Cleo uslubidagi AI moliyaviy analizatorisan. "
            "O'zbek tilida jonli, tushunarli va foydali tahlil ber. "
            "Ma'lumotlarni JSON formatida olasan va chiroyli matnli tahlil qaytarasiz.\n\n"
            "Tahlilda quyidagilarni ko'rsat:\n"
            "1. Jami kirim/chiqim/sof balans (Biznes va Shaxsiy alohida)\n"
            "   - USD va UZS valyutalarida alohida ko'rsat (USD summalarni UZS ga kurs bo'yicha o'tkazib qo'shma summani ham hisobla)\n"
            "2. Eng katta xarajat kategoriyalari (top 3)\n"
            "3. O'tgan oy bilan solishtirma (foiz o'zgarishi)\n"
            "4. Qiziqarli insight: eng ko'p sarflangan kun, eng katta to'lov, trendlar\n"
            "5. Tavsiya: nimani kamaytirish mumkin, qanday tejash mumkin\n"
            "6. Agar qarz yoki byudjet ma'lumoti bo'lsa, ularni ham tahlilga qo'sh\n\n"
            "Uslub: do'stona, lekin professional. Qisqa va aniq. 3-5 paragraf.\n"
            "Oxirida 1 ta '💡 Tavsiya' qo'y."
        )

        user_prompt = (
            f"📊 {_month_name(period)} oyi moliyaviy ma'lumotlari (USD kursi: {rate:,.0f} UZS):\n"
            f"{json.dumps(data, ensure_ascii=False, indent=2)}\n"
            f"\nO'tgan oy ({_month_name(prev_period)}) ma'lumotlari:\n"
            f"{json.dumps(prev_data, ensure_ascii=False, indent=2)}"
            f"{debt_info}"
            f"{budget_info}"
            f"{salary_info}"
        )

        try:
            response, model = await generate_content_with_fallback(
                client=self.client,
                primary_model=settings.GEMINI_CALL_MODEL,
                contents=[system_prompt, user_prompt],
                env_name="GEMINI_GLOBAL_FALLBACK_MODELS",
                log_prefix="[HISOBCHI-ANALYST]",
            )
            if response and response.text:
                return response.text.strip()
        except Exception as exc:
            logger.error("[HISOBCHI-ANALYST] Analysis failed: %s", exc)

        return await self._fallback_report(period, summary)

    async def ask(self, question: str, period: Optional[str] = None) -> str:
        now = datetime.now(timezone.utc)
        period = period or now.strftime("%Y-%m")
        summary = await self.engine.get_monthly_summary(period)
        b = summary.get("business", {})
        p = summary.get("personal", {})
        rate = await self._get_usd_rate()

        context = json.dumps({
            "period": period,
            "usd_rate": rate,
            "business_income": b.get("income", 0),
            "business_expense": b.get("expense", 0),
            "business_net": b.get("net", 0),
            "business_usd_income": b.get("usd_income", 0),
            "business_usd_expense": b.get("usd_expense", 0),
            "personal_income": p.get("income", 0),
            "personal_expense": p.get("expense", 0),
            "personal_net": p.get("net", 0),
            "personal_usd_income": p.get("usd_income", 0),
            "personal_usd_expense": p.get("usd_expense", 0),
            "top_categories": dict(list(b.get("categories", {}).items())[:10]),
        }, ensure_ascii=False)

        system_prompt = (
            "Sen Hisobchi — AI moliyaviy yordamchi. "
            "Foydalanuvchi moliyasi haqida savol beradi, sen ma'lumotlar asosida javob berasan. "
            "O'zbek tilida, qisqa va aniq javob ber. JSON formatida ma'lumot beriladi."
        )

        try:
            response, model = await generate_content_with_fallback(
                client=self.client,
                primary_model=settings.GEMINI_CALL_MODEL,
                contents=[system_prompt, f"Ma'lumotlar:\n{context}\n\nSavol: {question}"],
                env_name="GEMINI_GLOBAL_FALLBACK_MODELS",
                log_prefix="[HISOBCHI-ASK]",
            )
            if response and response.text:
                return response.text.strip()
        except Exception as exc:
            logger.error("[HISOBCHI-ASK] Failed: %s", exc)

        return "Kechirasiz, savolingizga javob berishda xatolik yuz berdi."

    async def forecast(self, months: int = 3) -> str:
        now = datetime.now(timezone.utc)
        current = now.strftime("%Y-%m")
        summaries = []
        rate = await self._get_usd_rate()
        for i in range(months):
            parts = current.split("-")
            m = int(parts[1]) - i
            y = int(parts[0])
            while m < 1:
                m += 12
                y -= 1
            period = f"{y}-{m:02d}"
            s = await self.engine.get_monthly_summary(period)
            b = s.get("business", {})
            summaries.append({
                "period": period,
                "income": b.get("income", 0),
                "expense": b.get("expense", 0),
                "net": b.get("net", 0),
                "usd_income": b.get("usd_income", 0),
                "usd_expense": b.get("usd_expense", 0),
            })

        system_prompt = (
            "Sen Hisobchi — AI moliyaviy analitik. "
            "Oxirgi oylar ma'lumotlari asosida kelajakdagi 3 oy uchun prognoz qil. "
            "Trendlarni aniqlab, taxminiy kirim/chiqim/balansni ko'rsat. "
            "O'zbek tilida, qisqa va aniq. 2-3 paragraf."
        )

        try:
            response, model = await generate_content_with_fallback(
                client=self.client,
                primary_model=settings.GEMINI_CALL_MODEL,
                contents=[system_prompt, json.dumps(summaries, ensure_ascii=False)],
                env_name="GEMINI_GLOBAL_FALLBACK_MODELS",
                log_prefix="[HISOBCHI-FORECAST]",
            )
            if response and response.text:
                return response.text.strip()
        except Exception as exc:
            logger.error("[HISOBCHI-FORECAST] Failed: %s", exc)

        return "Prognoz tayyorlashda xatolik."

    async def _fallback_report(self, period: str, summary: dict) -> str:
        b = summary.get("business", {})
        p = summary.get("personal", {})
        rate = await self._get_usd_rate()
        b_icon = "📈" if b.get("net", 0) >= 0 else "📉"
        p_icon = "📈" if p.get("net", 0) >= 0 else "📉"
        b_cats = "\n".join(
            f"  • {cat}: {_fmt(total)} UZS"
            for cat, total in list(b.get("categories", {}).items())[:5]
        )
        p_cats = "\n".join(
            f"  • {cat}: {_fmt(total)} UZS"
            for cat, total in list(p.get("categories", {}).items())[:5]
        )
        b_usd_note = ""
        if b.get("usd_income") or b.get("usd_expense"):
            b_usd_note = (
                f"\n  💵 USD: +{_fmt(b.get('usd_income', 0))}$ / -{_fmt(b.get('usd_expense', 0))}$"
                f" (kurs: {_fmt(int(rate))} UZS)"
            )
        p_usd_note = ""
        if p.get("usd_income") or p.get("usd_expense"):
            p_usd_note = f"\n  💵 USD: +{_fmt(p.get('usd_income', 0))}$ / -{_fmt(p.get('usd_expense', 0))}$"
        return (
            f"📊 <b>Hisobchi tahlili — {_month_name(period)}</b>\n\n"
            f"💼 <b>Biznes:</b>\n"
            f"  ➕ Kirim: <b>{_fmt(b.get('income', 0))} UZS</b>\n"
            f"  ➖ Chiqim: <b>{_fmt(b.get('expense', 0))} UZS</b>\n"
            f"  {b_icon} Sof: <b>{_fmt(b.get('net', 0))} UZS</b>{b_usd_note}\n"
            f"  🗂 Kategoriyalar:\n{b_cats or '  —'}\n\n"
            f"👤 <b>Shaxsiy:</b>\n"
            f"  ➕ Kirim: <b>{_fmt(p.get('income', 0))} UZS</b>\n"
            f"  ➖ Chiqim: <b>{_fmt(p.get('expense', 0))} UZS</b>\n"
            f"  {p_icon} Sof: <b>{_fmt(p.get('net', 0))} UZS</b>{p_usd_note}\n"
            f"  🗂 Kategoriyalar:\n{p_cats or '  —'}"
        )
