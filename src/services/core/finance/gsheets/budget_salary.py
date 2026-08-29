import logging
from typing import Any, Dict, List, Optional
from src.services.core.finance.gsheets.constants import *

logger = logging.getLogger(__name__)

class GsheetBudgetSalaryMixin:
    async def set_budget(
        self, category: str, period: str, budget_limit: int
    ) -> int:
        ws = self._worksheets.get(SHEET_BYUDJET)
        if not ws:
            return 0
        rows = ws.get_all_records()
        for i, r in enumerate(rows):
            if (_get(SHEET_BYUDJET, r, "category", "") == category
                and _get(SHEET_BYUDJET, r, "period", "") == period):
                row_num = i + 2
                now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                self._update_row(SHEET_BYUDJET, row_num, {
                    "id": _get(SHEET_BYUDJET, r, "id"),
                    "category": category, "period": period,
                    "budget_limit": budget_limit,
                    "spent": _get(SHEET_BYUDJET, r, "spent", 0),
                    "remaining": budget_limit - int(_get(SHEET_BYUDJET, r, "spent", 0)),
                    "status": _get(SHEET_BYUDJET, r, "status", "yaxshi"),
                    "updated_at": now,
                })
                return int(_get(SHEET_BYUDJET, r, "id", 0))
        nid = self._next_id(SHEET_BYUDJET)
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._append_row(SHEET_BYUDJET, {
            "id": nid, "category": category, "period": period,
            "budget_limit": budget_limit, "spent": 0,
            "remaining": budget_limit, "status": "yaxshi",
            "updated_at": now,
        })
        return nid

    async def get_budget_status(self, period: str) -> list[dict]:
        ws = self._worksheets.get(SHEET_BYUDJET)
        if not ws:
            return []
        try:
            rows = ws.get_all_records()
        except Exception:
            logger.error("Exception handled in %s", __name__, exc_info=True)
            return []
        result = []
        for r in rows:
            if _get(SHEET_BYUDJET, r, "period", "") != period:
                continue
            result.append({
                "id": int(_get(SHEET_BYUDJET, r, "id", 0)),
                "category": _get(SHEET_BYUDJET, r, "category", ""),
                "period": _get(SHEET_BYUDJET, r, "period", ""),
                "budget_limit": int(_get(SHEET_BYUDJET, r, "budget_limit", 0)),
                "spent": int(_get(SHEET_BYUDJET, r, "spent", 0)),
                "remaining": int(_get(SHEET_BYUDJET, r, "remaining", 0)),
                "status": _get(SHEET_BYUDJET, r, "status", "yaxshi"),
            })
        return result

    async def update_budget_spent(self, period: str, category: str, spent: int) -> None:
        ws = self._worksheets.get(SHEET_BYUDJET)
        if not ws:
            return
        rows = ws.get_all_records()
        for i, r in enumerate(rows):
            if (_get(SHEET_BYUDJET, r, "category", "") == category
                and _get(SHEET_BYUDJET, r, "period", "") == period):
                row_num = i + 2
                limit = int(_get(SHEET_BYUDJET, r, "budget_limit", 0))
                remaining = limit - spent
                if remaining < 0:
                    status = "yomon"
                elif remaining < limit * 0.2:
                    status = "ogohlantirish"
                else:
                    status = "yaxshi"
                now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                self._update_row(SHEET_BYUDJET, row_num, {
                    "id": _get(SHEET_BYUDJET, r, "id"),
                    "category": category, "period": period,
                    "budget_limit": limit, "spent": spent,
                    "remaining": max(0, remaining),
                    "status": status, "updated_at": now,
                })
                return

    async def add_salary_entry(
        self, employee_name: str, entry_type: str, amount: int,
        period: str, note: str = "",
    ) -> int:
        ws = self._worksheets.get(SHEET_MAOSH)
        if not ws:
            return 0
        nid = self._next_id(SHEET_MAOSH)
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._append_row(SHEET_MAOSH, {
            "id": nid, "employee_name": employee_name,
            "type": entry_type, "amount": int(amount),
            "date": now, "period": period, "note": note,
            "status": "to'langan", "updated_at": now,
        })
        return nid

    async def get_salary_summary(self, period: str) -> dict:
        ws = self._worksheets.get(SHEET_MAOSH)
        if not ws:
            return {"total": 0, "oylik": 0, "avans": 0, "bonus": 0, "entries": []}
        try:
            rows = ws.get_all_records()
        except Exception:
            logger.error("Exception handled in %s", __name__, exc_info=True)
            return {"total": 0, "oylik": 0, "avans": 0, "bonus": 0, "entries": []}
        total = 0
        oylik = 0
        avans = 0
        bonus = 0
        entries = []
        for r in rows:
            if _get(SHEET_MAOSH, r, "period", "") != period:
                continue
            amt = int(_get(SHEET_MAOSH, r, "amount", 0))
            tp = _get(SHEET_MAOSH, r, "type", "").strip().lower()
            total += amt
            if tp == "oylik":
                oylik += amt
            elif tp == "avans":
                avans += amt
            elif tp == "bonus":
                bonus += amt
            entries.append({
                "id": int(_get(SHEET_MAOSH, r, "id", 0)),
                "employee": _get(SHEET_MAOSH, r, "employee_name", ""),
                "type": tp, "amount": amt,
                "note": _get(SHEET_MAOSH, r, "note", ""),
                "status": _get(SHEET_MAOSH, r, "status", ""),
            })
        return {"total": total, "oylik": oylik, "avans": avans, "bonus": bonus, "entries": entries}

    async def update_rate(
        self, currency: str, buy_rate: float, sell_rate: float, cb_rate: float = 0
    ) -> None:
        ws = self._worksheets.get(SHEET_VALYUTA)
        if not ws:
            return
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        rows = ws.get_all_records()
        for i, r in enumerate(rows):
            if _get(SHEET_VALYUTA, r, "currency", "").upper() == currency.upper():
                row_num = i + 2
                self._update_row(SHEET_VALYUTA, row_num, {
                    "id": _get(SHEET_VALYUTA, r, "id"),
                    "currency": currency.upper(),
                    "buy_rate": buy_rate,
                    "sell_rate": sell_rate,
                    "cb_rate": cb_rate,
                    "date": today,
                    "updated_at": now,
                })
                return
        nid = self._next_id(SHEET_VALYUTA)
        self._append_row(SHEET_VALYUTA, {
            "id": nid, "currency": currency.upper(),
            "buy_rate": buy_rate, "sell_rate": sell_rate,
            "cb_rate": cb_rate, "date": today, "updated_at": now,
        })

    async def get_rates(self) -> dict:
        ws = self._worksheets.get(SHEET_VALYUTA)
        if not ws:
            return {}
        try:
            rows = ws.get_all_records()
        except Exception:
            logger.error("Exception handled in %s", __name__, exc_info=True)
            return {}
        rates = {}
        for r in rows:
            cur = (_get(SHEET_VALYUTA, r, "currency") or "").upper()
            if cur:
                rates[cur] = {
                    "buy": float(_get(SHEET_VALYUTA, r, "buy_rate", 0)),
                    "sell": float(_get(SHEET_VALYUTA, r, "sell_rate", 0)),
                    "cb": float(_get(SHEET_VALYUTA, r, "cb_rate", 0)),
                    "date": _get(SHEET_VALYUTA, r, "date", ""),
                }
        return rates

    async def add_xodim(
        self, name: str, role: str, telegram_id: str = "", phone: str = "",
        permission: str = "kuzatish",
    ) -> int:
        ws = self._worksheets.get(SHEET_XODIMLAR)
        if not ws:
            return 0
        nid = self._next_id(SHEET_XODIMLAR)
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._append_row(SHEET_XODIMLAR, {
            "id": nid, "name": name, "role": role,
            "telegram_id": telegram_id, "phone": phone,
            "permission": permission, "active": "1", "updated_at": now,
        })
        return nid

    async def get_xodimlar(self, active_only: bool = True) -> list[dict]:
        ws = self._worksheets.get(SHEET_XODIMLAR)
        if not ws:
            return []
        try:
            rows = ws.get_all_records()
        except Exception:
            logger.error("Exception handled in %s", __name__, exc_info=True)
            return []
        result = []
        for r in rows:
            active = _get(SHEET_XODIMLAR, r, "active", "1")
            if active_only and str(active) != "1":
                continue
            result.append({
                "id": int(_get(SHEET_XODIMLAR, r, "id", 0)),
                "name": _get(SHEET_XODIMLAR, r, "name", ""),
                "role": _get(SHEET_XODIMLAR, r, "role", ""),
                "telegram_id": _get(SHEET_XODIMLAR, r, "telegram_id", ""),
                "phone": _get(SHEET_XODIMLAR, r, "phone", ""),
                "permission": _get(SHEET_XODIMLAR, r, "permission", "kuzatish"),
            })
        return result

    async def add_kassa(
        self, name: str, currency: str = "UZS", balance: int = 0,
        wallet_type: str = "Naqd", note: str = "",
    ) -> int:
        ws = self._worksheets.get(SHEET_KASSA)
        if not ws:
            return 0
        nid = self._next_id(SHEET_KASSA)
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._append_row(SHEET_KASSA, {
            "id": nid, "name": name, "currency": currency.upper(),
            "balance": int(balance), "type": wallet_type,
            "note": note, "active": "1", "updated_at": now,
        })
        return nid

    async def get_kassa(self, active_only: bool = True) -> list[dict]:
        ws = self._worksheets.get(SHEET_KASSA)
        if not ws:
            return []
        try:
            rows = ws.get_all_records()
        except Exception:
            logger.error("Exception handled in %s", __name__, exc_info=True)
            return []
        result = []
        for r in rows:
            active = _get(SHEET_KASSA, r, "active", "1")
            if active_only and str(active) != "1":
                continue
            result.append({
                "id": int(_get(SHEET_KASSA, r, "id", 0)),
                "name": _get(SHEET_KASSA, r, "name", ""),
                "currency": _get(SHEET_KASSA, r, "currency", "UZS"),
                "balance": int(_get(SHEET_KASSA, r, "balance", 0)),
                "type": _get(SHEET_KASSA, r, "type", ""),
                "note": _get(SHEET_KASSA, r, "note", ""),
            })
        return result

    async def transfer_balance(
        self, from_kassa_id: int, to_kassa_id: int, amount: int, note: str = ""
    ) -> Optional[dict]:
        """Transfer between wallets (supports different currencies)."""
        wallets = await self.get_kassa(active_only=True)
        from_w = next((w for w in wallets if w["id"] == from_kassa_id), None)
        to_w = next((w for w in wallets if w["id"] == to_kassa_id), None)
        if not from_w or not to_w:
            return None

        rates = await self.get_rates()
        cur_from = from_w["currency"]
        cur_to = to_w["currency"]

        if cur_from == cur_to:
            converted = amount
        else:
            rate_info = rates.get(cur_to, {})
            rate = rate_info.get("buy", 0) or rate_info.get("cb", 0)
            if rate <= 0:
                # Try inverse
                inv_rate_info = rates.get(cur_from, {})
                inv_sell = inv_rate_info.get("sell", 0)
                if inv_sell > 0:
                    converted = int(amount * inv_sell)
                else:
                    return None
            else:
                converted = int(amount * rate)

        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        ws = self._worksheets.get(SHEET_KASSA)
        rows = ws.get_all_records()
        for i, r in enumerate(rows):
            rid = int(_get(SHEET_KASSA, r, "id", 0))
            if rid == from_kassa_id:
                bal = int(_get(SHEET_KASSA, r, "balance", 0))
                self._update_row(SHEET_KASSA, i + 2, {
                    "id": rid, "name": _get(SHEET_KASSA, r, "name", ""),
                    "currency": _get(SHEET_KASSA, r, "currency", "UZS"),
                    "balance": bal - amount,
                    "type": _get(SHEET_KASSA, r, "type", ""),
                    "note": _get(SHEET_KASSA, r, "note", ""),
                    "active": "1", "updated_at": now,
                })
            elif rid == to_kassa_id:
                bal = int(_get(SHEET_KASSA, r, "balance", 0))
                self._update_row(SHEET_KASSA, i + 2, {
                    "id": rid, "name": _get(SHEET_KASSA, r, "name", ""),
                    "currency": _get(SHEET_KASSA, r, "currency", "UZS"),
                    "balance": bal + converted,
                    "type": _get(SHEET_KASSA, r, "type", ""),
                    "note": _get(SHEET_KASSA, r, "note", ""),
                    "active": "1", "updated_at": now,
                })
        return {
            "from": from_w["name"], "to": to_w["name"],
            "amount": amount, "converted": converted,
            "rate": rate if cur_from != cur_to else 1,
            "note": note,
        }
