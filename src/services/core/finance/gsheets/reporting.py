import logging
from typing import Optional
from src.services.core.finance.gsheets.constants import *

logger = logging.getLogger(__name__)

class GsheetReportingMixin:
    async def get_known_category(self, merchant: str) -> Optional[str]:
        if not self._loaded:
            self._load_cache()
        return self._cache_mm.get(_normalize_merchant(merchant))

    async def learn_category(self, merchant: str, category: str) -> None:
        pat = _normalize_merchant(merchant)
        if pat in self._cache_mm:
            self._cache_mm[pat] = category
            ws = self._worksheets.get(SHEET_XOTIRA)
            if ws:
                row = self._find_row_by_col(
                    ws, _k2h(SHEET_XOTIRA, "merchant_pattern"), pat
                )
                if row:
                    self._update_row(SHEET_XOTIRA, row, {
                        "merchant_pattern": pat,
                        "category": category,
                    })
                    return
        self._cache_mm[pat] = category
        nid = self._next_id(SHEET_XOTIRA)
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._append_row(SHEET_XOTIRA, {
            "id": nid, "merchant_pattern": pat, "category": category,
            "use_count": 1, "updated_at": now,
        })

    async def get_known_rule(
        self, merchant: str, card_suffix: str, direction: str, amount: int
    ) -> Optional[dict]:
        if not self._loaded:
            self._load_cache()
        pat = _normalize_merchant(merchant)
        suf = _normalize_card_suffix(card_suffix)
        for r in self._cache_rules:
            if (
                (_get(SHEET_QOIDALAR, r, "merchant_pattern") or "").strip() == pat
                and (_get(SHEET_QOIDALAR, r, "card_suffix") or "").strip() == suf
                and (_get(SHEET_QOIDALAR, r, "direction") or "").strip() == direction
                and str(_get(SHEET_QOIDALAR, r, "amount") or "0").strip() == str(amount)
                and str(_get(SHEET_QOIDALAR, r, "active") or "1").strip() == "1"
                and str(_get(SHEET_QOIDALAR, r, "conflicts") or "0").strip() == "0"
                and int(_get(SHEET_QOIDALAR, r, "confirmations") or 0) >= 1
            ):
                return {
                    "category": (_get(SHEET_QOIDALAR, r, "category") or "").strip(),
                    "ownership": (_get(SHEET_QOIDALAR, r, "ownership") or "business").strip(),
                }
        return None

    async def learn_rule(
        self,
        *,
        merchant: str,
        card_suffix: str,
        direction: str,
        amount: int,
        category: str,
        ownership: str,
    ) -> None:
        pat = _normalize_merchant(merchant)
        suf = _normalize_card_suffix(card_suffix)
        ws = self._worksheets.get(SHEET_QOIDALAR)
        if not ws:
            return

        rows = ws.get_all_records()
        found = None
        for i, r in enumerate(rows):
            if (
                (_get(SHEET_QOIDALAR, r, "merchant_pattern") or "").strip() == pat
                and (_get(SHEET_QOIDALAR, r, "card_suffix") or "").strip() == suf
                and (_get(SHEET_QOIDALAR, r, "direction") or "").strip() == direction
                and str(_get(SHEET_QOIDALAR, r, "amount") or "").strip() == str(amount)
            ):
                found = (i + 2, r)
                break

        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if found:
            row_num, existing = found
            existing_cat = (_get(SHEET_QOIDALAR, existing, "category") or "").strip()
            existing_own = (_get(SHEET_QOIDALAR, existing, "ownership") or "business").strip()
            if existing_cat != category or existing_own != ownership:
                conflicts = int(_get(SHEET_QOIDALAR, existing, "conflicts") or 0) + 1
                self._update_row(SHEET_QOIDALAR, row_num, {
                    "merchant_pattern": pat, "card_suffix": suf,
                    "direction": direction, "amount": int(amount),
                    "category": existing_cat, "ownership": existing_own,
                    "confirmations": int(_get(SHEET_QOIDALAR, existing, "confirmations") or 1),
                    "conflicts": conflicts, "active": 0, "updated_at": now,
                })
                for r in self._cache_rules:
                    if (
                        (_get(SHEET_QOIDALAR, r, "merchant_pattern") or "").strip() == pat
                        and (_get(SHEET_QOIDALAR, r, "card_suffix") or "").strip() == suf
                    ):
                        r[_k2h(SHEET_QOIDALAR, "conflicts")] = str(conflicts)
                        r[_k2h(SHEET_QOIDALAR, "active")] = "0"
            else:
                confirmations = int(_get(SHEET_QOIDALAR, existing, "confirmations") or 1) + 1
                self._update_row(SHEET_QOIDALAR, row_num, {
                    "merchant_pattern": pat, "card_suffix": suf,
                    "direction": direction, "amount": int(amount),
                    "category": category, "ownership": ownership,
                    "confirmations": confirmations, "conflicts": 0,
                    "active": 1, "updated_at": now,
                })
        else:
            nid = self._next_id(SHEET_QOIDALAR)
            self._append_row(SHEET_QOIDALAR, {
                "id": nid, "merchant_pattern": pat, "card_suffix": suf,
                "direction": direction, "amount": int(amount),
                "category": category, "ownership": ownership,
                "confirmations": 1, "conflicts": 0, "active": 1,
                "updated_at": now,
            })
            self._cache_rules.append({
                _k2h(SHEET_QOIDALAR, "merchant_pattern"): pat,
                _k2h(SHEET_QOIDALAR, "card_suffix"): suf,
                _k2h(SHEET_QOIDALAR, "direction"): direction,
                _k2h(SHEET_QOIDALAR, "amount"): str(amount),
                _k2h(SHEET_QOIDALAR, "category"): category,
                _k2h(SHEET_QOIDALAR, "ownership"): ownership,
                _k2h(SHEET_QOIDALAR, "confirmations"): "1",
                _k2h(SHEET_QOIDALAR, "conflicts"): "0",
                _k2h(SHEET_QOIDALAR, "active"): "1",
                _k2h(SHEET_QOIDALAR, "updated_at"): now,
            })

    async def get_monthly_summary(
        self, period: str, *, tracking_start_date: str = "2026-08-01"
    ) -> dict:
        summary = {
            "business": {"income": 0, "expense": 0, "net": 0, "categories": {},
                         "usd_income": 0, "usd_expense": 0},
            "personal": {"income": 0, "expense": 0, "net": 0, "categories": {},
                         "usd_income": 0, "usd_expense": 0},
        }
        for tx in self._cache_transactions.values():
            tx_date = str(tx.get("date", ""))
            if not tx_date.startswith(period) or tx_date < tracking_start_date:
                continue
            own = tx.get("ownership", "business")
            if own not in summary:
                own = "business"
            direc = "in" if tx.get("direction") == "Kirim" else "out"
            try:
                total = int(tx.get("amount", 0))
            except (ValueError, TypeError):
                continue
            cur = str(tx.get("currency", "UZS")).upper()
            cat = tx.get("category") or "Nomalum"
            if direc == "in":
                summary[own]["income"] += total
                if cur == "USD":
                    summary[own]["usd_income"] += total
            else:
                summary[own]["expense"] += total
                if cur == "USD":
                    summary[own]["usd_expense"] += total
                summary[own]["categories"][cat] = (
                    summary[own]["categories"].get(cat, 0) + total
                )

        for own in ["business", "personal"]:
            summary[own]["net"] = summary[own]["income"] - summary[own]["expense"]
            summary[own]["categories"] = dict(
                sorted(summary[own]["categories"].items(), key=lambda x: -x[1])
            )
        return summary

    async def save_monthly_pnl(self, period: str, summary: dict) -> None:
        ws = self._worksheets.get(SHEET_FOYDA_ZARAR)
        if not ws:
            return
        b = summary.get("business", {})
        p = summary.get("personal", {})
        rows = ws.get_all_records()
        for i, r in enumerate(rows):
            if (_get(SHEET_FOYDA_ZARAR, r, "period") or "").strip() == period:
                row_num = i + 2
                self._update_row(SHEET_FOYDA_ZARAR, row_num, {
                    "id": _get(SHEET_FOYDA_ZARAR, r, "id"),
                    "period": period,
                    "business_income": b.get("income", 0),
                    "business_expense": b.get("expense", 0),
                    "business_net": b.get("net", 0),
                    "personal_income": p.get("income", 0),
                    "personal_expense": p.get("expense", 0),
                    "personal_net": p.get("net", 0),
                    "created_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                })
                return
        nid = self._next_id(SHEET_FOYDA_ZARAR)
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._append_row(SHEET_FOYDA_ZARAR, {
            "id": nid, "period": period,
            "business_income": b.get("income", 0),
            "business_expense": b.get("expense", 0),
            "business_net": b.get("net", 0),
            "personal_income": p.get("income", 0),
            "personal_expense": p.get("expense", 0),
            "personal_net": p.get("net", 0),
            "created_at": now,
        })

    async def update_balance(
        self, card_suffix: str, card_type: str, balance: int
    ) -> None:
        ws = self._worksheets.get(SHEET_BALANS)
        if not ws:
            return
        rows = ws.get_all_records()
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for i, r in enumerate(rows):
            if (_get(SHEET_BALANS, r, "card_suffix") or "").strip() == card_suffix:
                row_num = i + 2
                self._update_row(SHEET_BALANS, row_num, {
                    "id": _get(SHEET_BALANS, r, "id"),
                    "card_suffix": card_suffix,
                    "card_type": card_type,
                    "balance": balance,
                    "updated_at": now,
                })
                return
        nid = self._next_id(SHEET_BALANS)
        self._append_row(SHEET_BALANS, {
            "id": nid, "card_suffix": card_suffix,
            "card_type": card_type, "balance": balance,
            "updated_at": now,
        })

    async def add_debt(
        self, debt_type: str, person: str, amount: int,
        date: str = "", due_date: str = "", note: str = "",
    ) -> int:
        ws = self._worksheets.get(SHEET_QARZ)
        if not ws:
            return 0
        nid = self._next_id(SHEET_QARZ)
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._append_row(SHEET_QARZ, {
            "id": nid, "debt_type": debt_type, "person": person,
            "amount": int(amount), "date": date or now,
            "repaid": 0, "remaining": int(amount),
            "due_date": due_date, "note": note,
            "status": "faol", "updated_at": now,
        })
        return nid

    async def get_debts(self, active_only: bool = True) -> list[dict]:
        ws = self._worksheets.get(SHEET_QARZ)
        if not ws:
            return []
        try:
            rows = ws.get_all_records()
        except Exception:
            logger.error("Exception handled in %s", __name__, exc_info=True)
            return []
        result = []
        for r in rows:
            status = _get(SHEET_QARZ, r, "status", "faol").strip().lower()
            if active_only and status not in ("faol", "muddati o'tgan"):
                continue
            result.append({
                "id": int(_get(SHEET_QARZ, r, "id", 0)),
                "debt_type": _get(SHEET_QARZ, r, "debt_type", ""),
                "person": _get(SHEET_QARZ, r, "person", ""),
                "amount": int(_get(SHEET_QARZ, r, "amount", 0)),
                "repaid": int(_get(SHEET_QARZ, r, "repaid", 0)),
                "remaining": int(_get(SHEET_QARZ, r, "remaining", 0)),
                "date": _get(SHEET_QARZ, r, "date", ""),
                "due_date": _get(SHEET_QARZ, r, "due_date", ""),
                "note": _get(SHEET_QARZ, r, "note", ""),
                "status": status,
            })
        return result

    async def repay_debt(self, debt_id: int, amount: int) -> Optional[dict]:
        ws = self._worksheets.get(SHEET_QARZ)
        if not ws:
            return None
        rows = ws.get_all_records()
        for i, r in enumerate(rows):
            rid = int(_get(SHEET_QARZ, r, "id", 0))
            if rid != debt_id:
                continue
            row_num = i + 2
            current_repaid = int(_get(SHEET_QARZ, r, "repaid", 0))
            total = int(_get(SHEET_QARZ, r, "amount", 0))
            new_repaid = current_repaid + int(amount)
            remaining = total - new_repaid
            status = "yopilgan" if remaining <= 0 else _get(SHEET_QARZ, r, "status", "faol")
            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self._update_row(SHEET_QARZ, row_num, {
                "id": rid,
                "debt_type": _get(SHEET_QARZ, r, "debt_type", ""),
                "person": _get(SHEET_QARZ, r, "person", ""),
                "amount": total,
                "date": _get(SHEET_QARZ, r, "date", ""),
                "repaid": new_repaid,
                "remaining": max(0, remaining),
                "due_date": _get(SHEET_QARZ, r, "due_date", ""),
                "note": _get(SHEET_QARZ, r, "note", ""),
                "status": status,
                "updated_at": now,
            })
            return {"id": rid, "repaid": new_repaid, "remaining": max(0, remaining), "status": status}
        return None
