import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from src.api.routes.finance_dashboard import finance_dashboard, finance_transactions
from src.api.routes.state import api_state
from src.services.core.finance.finance_source import (
    FinanceSnapshot,
    FinanceSourceUnavailable,
    FinanceTransaction,
    GoogleSheetsFinanceSource,
)


class _Source:
    def __init__(self, snapshot=None, error=None):
        self.snapshot = snapshot
        self.error = error

    async def get_snapshot(self):
        if self.error:
            raise self.error
        return self.snapshot


def test_finance_dashboard_fails_closed_when_real_source_is_not_configured():
    with patch.object(api_state, "finance_source", None):
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(finance_dashboard())

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == {
        "code": "finance_source_not_configured",
        "message": "Real finance data source is not configured",
    }


def test_finance_transactions_do_not_return_sample_records():
    with patch.object(api_state, "finance_source", None):
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(finance_transactions())

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail["code"] == "finance_source_not_configured"


def test_finance_dashboard_uses_real_source_and_decimal_calculations():
    snapshot = FinanceSnapshot(
        balance=Decimal("750.25"),
        monthly_income=Decimal("1000.50"),
        monthly_expense=Decimal("250.25"),
        transactions=(),
        source="hisobchi_google_sheets",
        source_status="fresh",
        fetched_at=datetime(2026, 7, 31, tzinfo=timezone.utc),
    )
    with patch.object(api_state, "finance_source", _Source(snapshot=snapshot)):
        result = asyncio.run(finance_dashboard())

    assert result["balance"] == 750.25
    assert result["monthly_income"] == 1000.5
    assert result["source_status"] == "fresh"


def test_finance_transactions_include_source_state_and_no_demo_rows():
    snapshot = FinanceSnapshot(
        balance=Decimal("100"),
        monthly_income=Decimal("100"),
        monthly_expense=Decimal("0"),
        transactions=(
            FinanceTransaction(
                id="real-1",
                direction="Kirim",
                amount=Decimal("100"),
                currency="UZS",
                description="Real payment",
                occurred_at="2026-07-31",
            ),
        ),
        source="hisobchi_google_sheets",
        source_status="stale",
        fetched_at=datetime(2026, 7, 31, tzinfo=timezone.utc),
    )
    with patch.object(api_state, "finance_source", _Source(snapshot=snapshot)):
        result = asyncio.run(finance_transactions())

    assert result["source_status"] == "stale"
    assert result["transactions"][0]["amount"] == 100
    assert result["transactions"][0]["id"] == "real-1"


def test_finance_source_unavailable_has_exact_503_contract():
    source = _Source(error=FinanceSourceUnavailable("offline"))
    with patch.object(api_state, "finance_source", source):
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(finance_dashboard())

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == {
        "code": "finance_source_unavailable",
        "message": "Real finance data source is temporarily unavailable",
    }


class _Worksheet:
    def __init__(self, rows):
        self.rows = rows

    def get_all_records(self):
        if isinstance(self.rows, Exception):
            raise self.rows
        return self.rows


class _Store:
    def __init__(self, rows):
        self._worksheets = {"Pul oqimi": _Worksheet(rows)}


def test_google_sheets_source_marks_cached_snapshot_stale_on_temporary_error():
    store = _Store([{"#": 1, "Yonalish": "Kirim", "Summa": "10.50", "Sana": "2026-08-01"}])
    source = GoogleSheetsFinanceSource(store, stale_ttl_seconds=900)
    fresh = asyncio.run(source.get_snapshot())
    store._worksheets["Pul oqimi"].rows = RuntimeError("offline")

    stale = asyncio.run(source.get_snapshot())

    assert fresh.balance == Decimal("10.50")
    assert fresh.source_status == "fresh"
    assert stale.source_status == "stale"
    assert stale.balance == fresh.balance


def test_google_sheets_source_raises_when_unavailable_without_cache():
    source = GoogleSheetsFinanceSource(_Store(RuntimeError("offline")))

    with pytest.raises(FinanceSourceUnavailable):
        asyncio.run(source.get_snapshot())


def test_google_sheets_source_counts_only_transactions_from_august_first():
    store = _Store([
        {"#": 1, "Yonalish": "Kirim", "Summa": "900", "Sana": "2026-07-31"},
        {"#": 2, "Yonalish": "Kirim", "Summa": "1000.50", "Sana": "2026-08-01"},
        {"#": 3, "Yonalish": "Chiqim", "Summa": "250.25", "Sana": "2026-08-02"},
        {"#": 4, "Yonalish": "Kirim", "Summa": "999", "Sana": "noto'g'ri"},
    ])
    source = GoogleSheetsFinanceSource(
        store, tracking_start_date="2026-08-01"
    )

    with patch("src.services.core.finance.finance_source.datetime") as clock:
        clock.now.return_value = datetime(2026, 8, 2, tzinfo=timezone.utc)
        clock.strptime.side_effect = datetime.strptime
        clock.min = datetime.min
        snapshot = asyncio.run(source.get_snapshot())

    assert snapshot.balance == Decimal("750.25")
    assert snapshot.monthly_income == Decimal("1000.50")
    assert snapshot.monthly_expense == Decimal("250.25")
    assert [tx.id for tx in snapshot.transactions] == ["3", "2"]


def test_google_sheets_source_rejects_invalid_tracking_start_date():
    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        GoogleSheetsFinanceSource(_Store([]), tracking_start_date="01.08.2026")
