"""Synthetic ledger reads must not fabricate fresh zeroes or mixed-currency totals."""
import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.services.core.finance.finance_source import (
    DatabaseFinanceSource, FinanceSourceUnavailable,
)


def source_for(rows=None, failure=None):
    cursor = SimpleNamespace(fetchall=AsyncMock(return_value=rows or []))
    connection = SimpleNamespace(execute=AsyncMock(return_value=cursor, side_effect=failure))
    db = SimpleNamespace(get_connection=AsyncMock(return_value=connection))
    return DatabaseFinanceSource(db), connection


@pytest.mark.parametrize("db", [object(), SimpleNamespace(get_connection=AsyncMock(return_value=None))])
def test_missing_database_is_unavailable(db):
    with pytest.raises(FinanceSourceUnavailable):
        asyncio.run(DatabaseFinanceSource(db).get_snapshot())


def test_query_failure_is_unavailable():
    source, _ = source_for(failure=RuntimeError("synthetic offline"))
    with pytest.raises(FinanceSourceUnavailable):
        asyncio.run(source.get_snapshot())


def row(direction="in", currency="UZS", amount="10"):
    return (1, direction, amount, "synthetic",
            datetime.now(timezone.utc).isoformat(), "test", currency, "test")


@pytest.mark.parametrize("values", [[row(currency="USD")], [row(direction="unknown")]])
def test_unconvertible_or_unclassified_transaction_is_unavailable(values):
    source, _ = source_for(values)
    with pytest.raises(FinanceSourceUnavailable):
        asyncio.run(source.get_snapshot())


def test_empty_success_is_real_zero():
    source, _ = source_for()
    snapshot = asyncio.run(source.get_snapshot())
    assert snapshot.balance == Decimal("0")
    assert snapshot.source_status == "fresh"


def test_totals_include_more_than_last_hundred_rows():
    async def read_ledger():
        import aiosqlite
        async with aiosqlite.connect(":memory:") as connection:
            await connection.execute(
                "CREATE TABLE hisobchi_transactions (id INTEGER, direction TEXT, amount TEXT, "
                "merchant TEXT, tx_time TEXT, category TEXT, currency TEXT, reason TEXT)"
            )
            await connection.executemany(
                "INSERT INTO hisobchi_transactions VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                [(i, "in", "10", "synthetic", datetime.now(timezone.utc).isoformat(),
                  "test", "UZS", "test") for i in range(101)],
            )
            db = SimpleNamespace(get_connection=AsyncMock(return_value=connection))
            return await DatabaseFinanceSource(db).get_snapshot()

    snapshot = asyncio.run(read_ledger())
    assert snapshot.monthly_income == Decimal("1010")
    assert len(snapshot.transactions) == 101
