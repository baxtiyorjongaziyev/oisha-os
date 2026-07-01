"""
Hisobchi MCP Server — AI integration (Claude/ChatGPT/Gemini).
Exposes financial data via MCP protocol for external AI assistants.

Start: python -m src.services.core.hisobchi_mcp
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from src.settings import settings
from src.services.core.hisobchi_gsheets import HisobchiGsheetStore

logger = logging.getLogger(__name__)


def _fmt(amount: int) -> str:
    return f"{amount:,}".replace(",", " ")


class HisobchiMCPServer:
    """MCP server that exposes Hisobchi data for AI assistants."""

    def __init__(self) -> None:
        gs_id = getattr(settings, "HISOBCHI_GSHEET_ID", None) or ""
        gs_creds = getattr(settings, "HISOBCHI_GSHEET_CREDS_FILE", "service_account.json")
        self._gs = HisobchiGsheetStore(gs_id, gs_creds) if gs_id else None

    async def handle_query(self, query: str) -> str:
        """Handle natural language queries about finances."""
        if not self._gs:
            return "Google Sheets backend not configured."

        period = datetime.now(timezone.utc).strftime("%Y-%m")
        query_lower = query.lower().strip()

        if any(w in query_lower for w in ["qancha", "balans", "qoldiq", "pul"]):
            return await self._balance_report()

        if any(w in query_lower for w in ["oxirgi", "eng so'nggi", "kechagi"]):
            return await self._recent_tx(5)

        if any(w in query_lower for w in ["xarajat", "chiqim", "sarfla", "kategori"]):
            return await self._expense_report(period)

        if any(w in query_lower for w in ["kirim", "tushum", "daromad"]):
            return await self._income_report(period)

        if any(w in query_lower for w in ["qarz"]):
            return await self._debt_report()

        if any(w in query_lower for w in ["byudjet", "budget", "limit"]):
            return await self._budget_report(period)

        if any(w in query_lower for w in ["maosh", "avans", "oylik"]):
            return await self._salary_report(period)

        if any(w in query_lower for w in ["foyda", "zarar", "umumiy"]):
            return await self._pnl_report(period)

        if any(w in query_lower for w in ["valyuta", "kurs", "dollar"]):
            return await self._rate_report()

        return "Tushunmadim. Savollarga misol:\n- Qancha pulim bor?\n- Bu oy qancha sarfladim?\n- Eng katta xarajatlar\n- Qarzlarim qancha?\n- Foyda/zarar hisoboti"

    async def handle_tool(self, tool_name: str, args: dict) -> str:
        """Handle tool calls from MCP clients."""
        if not self._gs:
            return json.dumps({"error": "Google Sheets not configured"})

        if tool_name == "get_transactions":
            period = args.get("period", datetime.now(timezone.utc).strftime("%Y-%m"))
            summary = await self._gs.get_monthly_summary(period)
            return json.dumps(summary, ensure_ascii=False, indent=2)

        if tool_name == "get_summary":
            period = args.get("period", datetime.now(timezone.utc).strftime("%Y-%m"))
            summary = await self._gs.get_monthly_summary(period)
            business = summary.get("business", {})
            personal = summary.get("personal", {})
            return json.dumps({
                "period": period,
                "business": {
                    "income": business.get("income", 0),
                    "expense": business.get("expense", 0),
                    "net": business.get("net", 0),
                },
                "personal": {
                    "income": personal.get("income", 0),
                    "expense": personal.get("expense", 0),
                    "net": personal.get("net", 0),
                },
            }, ensure_ascii=False)

        if tool_name == "get_debts":
            debts = await self._gs.get_debts()
            return json.dumps(debts, ensure_ascii=False, indent=2)

        if tool_name == "get_rates":
            rates = await self._gs.get_rates()
            return json.dumps(rates, ensure_ascii=False, indent=2)

        if tool_name == "get_kassa":
            kassa = await self._gs.get_kassa()
            return json.dumps(kassa, ensure_ascii=False, indent=2)

        return json.dumps({"error": f"Unknown tool: {tool_name}"})

    async def _balance_report(self) -> str:
        if not self._gs:
            return "Backend yoq."
        kassa = await self._gs.get_kassa()
        if not kassa:
            return "Kassa hisobi yo'q."
        lines = ["<b>💰 Balanslar:</b>\n"]
        total_uzs = 0
        for w in kassa:
            cur = w.get("currency", "UZS")
            bal = w.get("balance", 0)
            icon = {"Naqd": "💵", "Karta": "💳", "Jamg'arma": "🏦", "Valyuta": "💱"}.get(w.get("type", ""), "💰")
            lines.append(f"{icon} {w['name']}: <b>{_fmt(bal)} {cur}</b> ({w['type']})")
            if cur == "UZS":
                total_uzs += bal
        lines.append(f"\n📊 Jami UZS: <b>{_fmt(total_uzs)} UZS</b>")
        return "\n".join(lines)

    async def _recent_tx(self, limit: int = 5) -> str:
        if not self._gs:
            return "Backend yoq."
        rows = []
        if self._gs._worksheets:
            for sheet in ("Pul oqimi", "Shaxsiy"):
                ws = self._gs._worksheets.get(sheet)
                if ws:
                    try:
                        rows += ws.get_all_records()
                    except Exception:
                        pass
        recent = sorted(rows, key=lambda r: str(r.get("Sana", "")), reverse=True)[:limit]
        if not recent:
            return "Tranzaksiyalar yo'q."
        lines = ["<b>🔄 Oxirgi tranzaksiyalar:</b>\n"]
        for r in recent:
            cat = r.get("Kategoriya", "") or r.get("category", "Noma'lum")
            amt = r.get("Summa", 0) or r.get("amount", 0)
            cur = r.get("Valyuta", "UZS") or "UZS"
            mer = r.get("Nomi", "") or r.get("merchant", "")
            date = r.get("Sana", "")[:10]
            icon = "➖" if "Chiqim" in str(r.get("Yonalish", "")) else "➕"
            lines.append(f"{icon} {_fmt(int(amt))} {cur} — {cat} ({mer}) {date}")
        return "\n".join(lines)

    async def _expense_report(self, period: str) -> str:
        if not self._gs:
            return "Backend yoq."
        summary = await self._gs.get_monthly_summary(period)
        b = summary.get("business", {})
        p = summary.get("personal", {})
        total_expense = b.get("expense", 0) + p.get("expense", 0)
        lines = [f"<b>📉 Xarajatlar {period}:</b>\n"]
        lines.append(f"💰 Biznes: <b>{_fmt(b.get('expense', 0))} UZS</b>")
        for cat, total in list(b.get("categories", {}).items())[:5]:
            lines.append(f"  • {cat}: {_fmt(total)} UZS")
        lines.append(f"\n👤 Shaxsiy: <b>{_fmt(p.get('expense', 0))} UZS</b>")
        for cat, total in list(p.get("categories", {}).items())[:3]:
            lines.append(f"  • {cat}: {_fmt(total)} UZS")
        lines.append(f"\n📊 Jami: <b>{_fmt(total_expense)} UZS</b>")
        return "\n".join(lines)

    async def _income_report(self, period: str) -> str:
        if not self._gs:
            return "Backend yoq."
        summary = await self._gs.get_monthly_summary(period)
        b = summary.get("business", {})
        p = summary.get("personal", {})
        lines = [f"<b>📈 Kirimlar {period}:</b>\n"]
        lines.append(f"💼 Biznes: <b>{_fmt(b.get('income', 0))} UZS</b>")
        lines.append(f"👤 Shaxsiy: <b>{_fmt(p.get('income', 0))} UZS</b>")
        total = b.get("income", 0) + p.get("income", 0)
        lines.append(f"\n📊 Jami kirim: <b>{_fmt(total)} UZS</b>")
        return "\n".join(lines)

    async def _debt_report(self) -> str:
        if not self._gs:
            return "Backend yoq."
        debts = await self._gs.get_debts()
        if not debts:
            return "✅ Faol qarzlar yo'q."
        lines = ["<b>📋 Qarzlar:</b>\n"]
        for d in debts:
            icon = "🔴" if d["debt_type"] == "Berilgan" else "🟡"
            lines.append(f"{icon} {d['person']}: {_fmt(d['remaining'])} UZS ({d['debt_type']})")
        return "\n".join(lines)

    async def _budget_report(self, period: str) -> str:
        if not self._gs:
            return "Backend yoq."
        budgets = await self._gs.get_budget_status(period)
        if not budgets:
            return f"{period} uchun byudjet belgilanmagan."
        lines = [f"<b>📊 Byudjet {period}:</b>\n"]
        for b in budgets:
            icon = {"yaxshi": "✅", "ogohlantirish": "⚠️", "yomon": "🚫"}.get(b["status"], "➖")
            lines.append(f"{icon} {b['category']}: {_fmt(b['spent'])} / {_fmt(b['budget_limit'])} UZS")
        return "\n".join(lines)

    async def _salary_report(self, period: str) -> str:
        if not self._gs:
            return "Backend yoq."
        salary = await self._gs.get_salary_summary(period)
        if not salary.get("entries"):
            return f"{period} uchun maosh ma'lumoti yo'q."
        lines = [f"<b>💰 Maosh {period}:</b>\n"]
        lines.append(f"Oylik: {_fmt(salary['oylik'])} UZS")
        lines.append(f"Avans: {_fmt(salary['avans'])} UZS")
        lines.append(f"Bonus: {_fmt(salary['bonus'])} UZS")
        lines.append(f"\nJami: <b>{_fmt(salary['total'])} UZS</b>")
        return "\n".join(lines)

    async def _pnl_report(self, period: str) -> str:
        if not self._gs:
            return "Backend yoq."
        summary = await self._gs.get_monthly_summary(period)
        b = summary.get("business", {})
        p = summary.get("personal", {})
        b_icon = "📈" if b.get("net", 0) >= 0 else "📉"
        p_icon = "📈" if p.get("net", 0) >= 0 else "📉"
        return (
            f"<b>📊 Foyda/Zarar {period}</b>\n\n"
            f"💼 <b>Biznes:</b>\n"
            f"  ➕ Kirim: {_fmt(b.get('income', 0))} UZS\n"
            f"  ➖ Chiqim: {_fmt(b.get('expense', 0))} UZS\n"
            f"  {b_icon} Sof: <b>{_fmt(b.get('net', 0))} UZS</b>\n\n"
            f"👤 <b>Shaxsiy:</b>\n"
            f"  ➕ Kirim: {_fmt(p.get('income', 0))} UZS\n"
            f"  ➖ Chiqim: {_fmt(p.get('expense', 0))} UZS\n"
            f"  {p_icon} Sof: <b>{_fmt(p.get('net', 0))} UZS</b>"
        )

    async def _rate_report(self) -> str:
        if not self._gs:
            return "Backend yoq."
        rates = await self._gs.get_rates()
        if not rates:
            return "Valyuta kurslari mavjud emas. /valyuta buyrug'ini ishlating."
        lines = ["<b>💱 Valyuta kurslari:</b>\n"]
        for cur, info in rates.items():
            lines.append(f"{cur}: Sotib olish {info.get('buy', 0)} | Sotish {info.get('sell', 0)}")
            if info.get("cb"):
                lines.append(f"  MB kursi: {info['cb']}")
        return "\n".join(lines)


# FastAPI MCP endpoint
try:
    from fastapi import APIRouter, FastAPI

    mcp_router = APIRouter(prefix="/mcp", tags=["mcp"])
    _mcp_server_instance: Optional[HisobchiMCPServer] = None

    async def _get_mcp():
        global _mcp_server_instance
        if _mcp_server_instance is None:
            _mcp_server_instance = HisobchiMCPServer()
        return _mcp_server_instance

    @mcp_router.post("/query")
    async def mcp_query(query: str):
        srv = await _get_mcp()
        result = await srv.handle_query(query)
        return {"result": result}

    @mcp_router.post("/tool/{tool_name}")
    async def mcp_tool(tool_name: str, args: dict = {}):
        srv = await _get_mcp()
        result = await srv.handle_tool(tool_name, args)
        return {"result": result}

except ImportError:
    mcp_router = None


if __name__ == "__main__":
    import uvicorn
    from fastapi import FastAPI

    app = FastAPI(title="Hisobchi MCP Server")
    if mcp_router is not None:
        app.include_router(mcp_router)

    uvicorn.run(app, host="0.0.0.0", port=8088)
