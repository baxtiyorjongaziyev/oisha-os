"""Qo'ng'iroqni PULGA bog'laydigan qatlam.

MUAMMO: `call_analyses` da sifat ballari bor, `sales_analytics` da AmoCRM
tushumi bor — lekin ular orasida hech qanday bog'lanish yo'q edi. Shuning
uchun "bu qo'ng'iroq qancha pul keltirdi" yoki "qaysi bosqich qancha pul
yo'qotmoqda" degan savolga javob berib bo'lmasdi.

Bu modul `call_analyses.lead_id` orqali AmoCRM bitimining narxi va
yakunini (yutilgan/yutqazilgan) shu jadvalga ko'chiradi. Shundan keyin
`metasell_conversion` konversiyani nafaqat foizda, balki so'mda ham
ko'rsata oladi.

MUHIM — IKKI KARRA SANASH XAVFI:
    Bitta bitimga bir nechta qo'ng'iroq bo'ladi. Pulni qo'ng'iroq bo'yicha
    yig'sak, 3 marta qo'ng'iroq qilingan bitim 3 barobar ko'p daromad
    ko'rsatadi. Shuning uchun pul HAR DOIM `lead_id` bo'yicha yagonalanadi
    (`aggregate_revenue` ga qarang), qo'ng'iroq bo'yicha emas.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Set

from src.services.core.call_analyses_schema import ensure_call_analysis_schema
from src.services.utils.db_rows import fetch_rows
from src.time_utils import get_local_now

logger = logging.getLogger(__name__)

# AmoCRM standart yakuniy statuslari.
STATUS_WON = 142
STATUS_LOST = 143

# Bir seansda nechta bitim so'ralsin — AmoCRM API'ni bo'g'ib qo'ymaslik uchun.
DEFAULT_SYNC_LIMIT = 200
_REQUEST_DELAY_SECONDS = 0.2


async def _maybe_await(value: Any) -> Any:
    if hasattr(value, "__await__"):
        return await value
    return value


def _row_get(row: Any, key: str, default: Any = None) -> Any:
    if isinstance(row, dict):
        value = row.get(key, default)
    else:
        value = getattr(row, key, default)
    return default if value is None else value


def _to_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


@dataclass
class RevenueSyncResult:
    """Sinxronizatsiya hisoboti."""

    checked: int = 0
    updated: int = 0
    won: int = 0
    lost: int = 0
    still_open: int = 0
    failed: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "checked": self.checked,
            "updated": self.updated,
            "won": self.won,
            "lost": self.lost,
            "still_open": self.still_open,
            "failed": self.failed,
        }


@dataclass
class SellerRevenue:
    """Bitta sotuvchining pul ko'rsatkichlari (bitim bo'yicha yagonalangan)."""

    manager_name: str
    deals_total: int = 0
    deals_won: int = 0
    deals_lost: int = 0
    deals_open: int = 0
    revenue_won: float = 0.0
    revenue_lost: float = 0.0
    revenue_open: float = 0.0
    lost_lead_ids: Set[int] = field(default_factory=set)

    @property
    def win_rate(self) -> float:
        closed = self.deals_won + self.deals_lost
        return (self.deals_won / closed * 100) if closed else 0.0

    @property
    def avg_deal_size(self) -> float:
        return (self.revenue_won / self.deals_won) if self.deals_won else 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "manager_name": self.manager_name,
            "deals_total": self.deals_total,
            "deals_won": self.deals_won,
            "deals_lost": self.deals_lost,
            "deals_open": self.deals_open,
            "revenue_won": round(self.revenue_won),
            "revenue_lost": round(self.revenue_lost),
            "revenue_open": round(self.revenue_open),
            "win_rate": round(self.win_rate, 1),
            "avg_deal_size": round(self.avg_deal_size),
        }


def format_money(amount: float) -> str:
    """So'mni o'qishga qulay ko'rinishda (bo'sh joy bilan)."""
    return f"{round(amount):,}".replace(",", " ") + " so'm"


def aggregate_revenue(rows: Sequence[Any]) -> Dict[str, SellerRevenue]:
    """Qo'ng'iroq qatorlaridan sotuvchi kesimida pul ko'rsatkichlari.

    Pul BITIM bo'yicha yagonalanadi: bir bitimga nechta qo'ng'iroq
    bo'lishidan qat'i nazar, narxi bir marta hisoblanadi. Bitim bir necha
    menejerga tegishli bo'lsa — eng oxirgi qo'ng'iroq qilgani oladi
    (amalda bitimni kim yopgan bo'lsa, o'sha).
    """
    # lead_id -> (manager_name, price, won) — oxirgi qo'ng'iroq g'olib
    by_lead: Dict[int, Dict[str, Any]] = {}
    for row in rows:
        try:
            lead_id = int(_row_get(row, "lead_id", 0) or 0)
        except (TypeError, ValueError):
            continue
        if not lead_id:
            continue
        manager = str(_row_get(row, "manager_name", "") or "").strip()
        if not manager:
            continue
        created_at = str(_row_get(row, "created_at", "") or "")
        existing = by_lead.get(lead_id)
        if existing and existing["created_at"] >= created_at:
            continue
        won_raw = _row_get(row, "lead_won", None)
        by_lead[lead_id] = {
            "manager": manager,
            "price": _to_float(_row_get(row, "lead_price", 0)),
            "won": None if won_raw in (None, "") else bool(int(won_raw)),
            "created_at": created_at,
        }

    sellers: Dict[str, SellerRevenue] = {}
    for lead_id, info in by_lead.items():
        seller = sellers.setdefault(
            info["manager"], SellerRevenue(manager_name=info["manager"])
        )
        seller.deals_total += 1
        price = info["price"]
        if info["won"] is True:
            seller.deals_won += 1
            seller.revenue_won += price
        elif info["won"] is False:
            seller.deals_lost += 1
            seller.revenue_lost += price
            seller.lost_lead_ids.add(lead_id)
        else:
            seller.deals_open += 1
            seller.revenue_open += price
    return sellers


class MetaSellRevenueSync:
    """AmoCRM bitim narxi va yakunini `call_analyses` ga ko'chiradi."""

    def __init__(self, db: Any, amocrm: Any):
        self.db = db
        self.amocrm = amocrm

    async def pending_lead_ids(
        self, days: int = 90, limit: int = DEFAULT_SYNC_LIMIT
    ) -> List[int]:
        """Yangilanishi kerak bo'lgan bitim ID'lari.

        Yakunlanган bitimlar qayta so'ralmaydi (`lead_won` to'lgan) — ular
        o'zgarmaydi. Ochiq bitimlar esa keyin yopilishi mumkin, shuning
        uchun har safar qayta tekshiriladi.
        """
        if self.db is None:
            return []
        try:
            rows = await fetch_rows(
                self.db,
                "SELECT DISTINCT lead_id FROM call_analyses "
                "WHERE lead_id IS NOT NULL AND lead_id > 0 "
                "AND overall_score > 0 "
                "AND lead_won IS NULL "
                "AND created_at >= datetime('now', ?) "
                "ORDER BY created_at DESC LIMIT ?",
                [f"-{int(days)} days", int(limit)],
            )
        except Exception as exc:
            logger.error("[REVENUE] Bitim ID'larini o'qib bo'lmadi: %s", exc)
            return []
        ids: List[int] = []
        for row in rows:
            try:
                ids.append(int(_row_get(row, "lead_id", 0)))
            except (TypeError, ValueError):
                continue
        return [i for i in ids if i]

    async def sync(
        self, days: int = 90, limit: int = DEFAULT_SYNC_LIMIT
    ) -> RevenueSyncResult:
        """Bitim narxi va yakunini yangilaydi."""
        result = RevenueSyncResult()
        if self.db is None or self.amocrm is None:
            return result

        await ensure_call_analysis_schema(self.db)
        lead_ids = await self.pending_lead_ids(days=days, limit=limit)
        if not lead_ids:
            return result

        for lead_id in lead_ids:
            result.checked += 1
            try:
                lead = await _maybe_await(self.amocrm.get_lead(lead_id))
            except Exception as exc:
                logger.warning("[REVENUE] Bitim %s olinmadi: %s", lead_id, exc)
                result.failed += 1
                continue
            if not lead:
                result.failed += 1
                continue

            price = _to_float(lead.get("price"))
            status_id = lead.get("status_id")
            if status_id == STATUS_WON:
                won: Optional[int] = 1
                result.won += 1
            elif status_id == STATUS_LOST:
                won = 0
                result.lost += 1
            else:
                # Bitim hali ochiq — yakunini TAXMIN QILMAYMIZ. NULL qolsa,
                # keyingi sinxronizatsiyada qayta tekshiriladi.
                won = None
                result.still_open += 1

            if await self._write(lead_id, price, won):
                result.updated += 1
            await asyncio.sleep(_REQUEST_DELAY_SECONDS)

        logger.info("[REVENUE] Sinxronizatsiya: %s", result.to_dict())
        return result

    async def _write(
        self, lead_id: int, price: float, won: Optional[int]
    ) -> bool:
        try:
            conn = await _maybe_await(self.db.get_connection())
            await _maybe_await(
                conn.execute(
                    "UPDATE call_analyses SET lead_price = ?, lead_won = ?, "
                    "revenue_synced_at = ? WHERE lead_id = ?",
                    (price, won, get_local_now().isoformat(), lead_id),
                )
            )
            await _maybe_await(conn.commit())
            return True
        except Exception as exc:
            logger.warning("[REVENUE] Bitim %s yozilmadi: %s", lead_id, exc)
            return False
