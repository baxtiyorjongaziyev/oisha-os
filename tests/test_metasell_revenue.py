"""Daromadni qo'ng'iroqqa bog'lash testlari.

ENG MUHIM XAVF: bitta bitimga bir nechta qo'ng'iroq bo'ladi. Pulni
qo'ng'iroq bo'yicha yig'sak, 3 marta qo'ng'iroq qilingan bitim 3 barobar
ko'p daromad ko'rsatadi. Quyidagi testlar pul HAR DOIM bitim bo'yicha
yagonalanishini ta'minlaydi.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.services.core.metasell_revenue import (
    STATUS_LOST,
    STATUS_WON,
    MetaSellRevenueSync,
    aggregate_revenue,
    format_money,
)


def row(lead_id, manager="Aziz", price=1_000_000, won=None, created="2026-08-01"):
    return {
        "lead_id": lead_id,
        "manager_name": manager,
        "lead_price": price,
        "lead_won": won,
        "created_at": created,
    }


# ── Yagonalash ───────────────────────────────────────────────────────────


def test_one_deal_counted_once_across_many_calls():
    rows = [
        row(1, price=5_000_000, won=1, created="2026-08-01"),
        row(1, price=5_000_000, won=1, created="2026-08-02"),
        row(1, price=5_000_000, won=1, created="2026-08-03"),
    ]

    seller = aggregate_revenue(rows)["Aziz"]

    assert seller.deals_won == 1
    assert seller.revenue_won == 5_000_000  # 15 mln EMAS


def test_open_deals_are_not_counted_as_won_or_lost():
    seller = aggregate_revenue([row(1, price=9_000_000, won=None)])["Aziz"]

    assert seller.deals_open == 1
    assert seller.revenue_won == 0
    assert seller.revenue_lost == 0
    assert seller.revenue_open == 9_000_000


def test_lost_revenue_tracked_separately():
    rows = [row(1, price=3_000_000, won=1), row(2, price=7_000_000, won=0)]

    seller = aggregate_revenue(rows)["Aziz"]

    assert seller.revenue_won == 3_000_000
    assert seller.revenue_lost == 7_000_000
    assert seller.win_rate == pytest.approx(50.0)
    assert seller.avg_deal_size == 3_000_000


def test_latest_call_owns_the_deal():
    """Bitimga ikki menejer qo'ng'iroq qilgan bo'lsa — oxirgisi oladi."""
    rows = [
        row(1, manager="Aziz", price=4_000_000, won=1, created="2026-08-01"),
        row(1, manager="Bek", price=4_000_000, won=1, created="2026-08-05"),
    ]

    sellers = aggregate_revenue(rows)

    assert "Aziz" not in sellers
    assert sellers["Bek"].revenue_won == 4_000_000


def test_rows_without_manager_or_lead_are_skipped():
    assert aggregate_revenue([row(1, manager="")]) == {}
    assert aggregate_revenue([row(0)]) == {}


def test_win_rate_ignores_open_deals():
    rows = [row(1, won=1), row(2, won=0), row(3, won=None)]

    assert aggregate_revenue(rows)["Aziz"].win_rate == pytest.approx(50.0)


def test_format_money_is_readable():
    assert format_money(15_000_000) == "15 000 000 so'm"
    assert format_money(0) == "0 so'm"


# ── Sinxronizatsiya ──────────────────────────────────────────────────────


class _Conn:
    def __init__(self):
        self.writes = []

    def execute(self, sql, params=None):
        if sql.strip().upper().startswith("UPDATE"):
            self.writes.append(params)

        async def _r():
            cur = MagicMock()
            cur.fetchall = AsyncMock(return_value=[])
            return cur

        return _r()

    async def commit(self):
        return None


def _db(conn, pending_rows):
    db = MagicMock()
    db.get_connection = AsyncMock(return_value=conn)
    db.execute = AsyncMock(return_value=pending_rows)
    return db


def _amocrm(leads):
    amocrm = MagicMock()
    amocrm.get_lead = AsyncMock(side_effect=lambda lead_id: leads.get(lead_id))
    return amocrm


@pytest.mark.asyncio
async def test_sync_classifies_won_lost_and_open():
    conn = _Conn()
    db = _db(conn, [{"lead_id": 1}, {"lead_id": 2}, {"lead_id": 3}])
    amocrm = _amocrm({
        1: {"price": 5_000_000, "status_id": STATUS_WON},
        2: {"price": 2_000_000, "status_id": STATUS_LOST},
        3: {"price": 8_000_000, "status_id": 12345},  # hali ochiq
    })

    result = await MetaSellRevenueSync(db=db, amocrm=amocrm).sync()

    assert (result.won, result.lost, result.still_open) == (1, 1, 1)
    assert result.updated == 3


@pytest.mark.asyncio
async def test_open_deal_written_as_null_not_zero():
    """Ochiq bitimni 'yutqazilgan' deb yozish — yolg'on ma'lumot."""
    conn = _Conn()
    db = _db(conn, [{"lead_id": 3}])
    amocrm = _amocrm({3: {"price": 8_000_000, "status_id": 999}})

    await MetaSellRevenueSync(db=db, amocrm=amocrm).sync()

    price, won, _synced, lead_id = conn.writes[0]
    assert won is None
    assert price == 8_000_000
    assert lead_id == 3


@pytest.mark.asyncio
async def test_amocrm_failure_does_not_abort_the_run():
    conn = _Conn()
    db = _db(conn, [{"lead_id": 1}, {"lead_id": 2}])
    amocrm = MagicMock()
    amocrm.get_lead = AsyncMock(
        side_effect=[RuntimeError("amocrm down"), {"price": 1, "status_id": STATUS_WON}]
    )

    result = await MetaSellRevenueSync(db=db, amocrm=amocrm).sync()

    assert result.failed == 1
    assert result.won == 1


@pytest.mark.asyncio
async def test_sync_noop_without_dependencies():
    assert (await MetaSellRevenueSync(db=None, amocrm=MagicMock()).sync()).checked == 0
    assert (await MetaSellRevenueSync(db=MagicMock(), amocrm=None).sync()).checked == 0
