"""Read-only finance source contract for the owner dashboard."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Protocol, Sequence

from src.services.core.hisobchi_gsheets import SHEET_PUL_OQIMI
from src.services.core.finance.accounting_period import (
    DEFAULT_TRACKING_START_DATE,
    is_on_or_after_start,
    parse_tracking_start_date,
)
import logging
logger = logging.getLogger(__name__)


class FinanceSourceUnavailable(RuntimeError):
    """The finance source cannot provide live or acceptably stale data."""


@dataclass(frozen=True)
class FinanceTransaction:
    id: str
    direction: str
    amount: Decimal
    currency: str
    description: str
    occurred_at: str


@dataclass(frozen=True)
class FinanceSnapshot:
    balance: Decimal
    monthly_income: Decimal
    monthly_expense: Decimal
    transactions: tuple[FinanceTransaction, ...]
    source: str
    source_status: str
    fetched_at: datetime


class FinanceSource(Protocol):
    async def get_snapshot(self) -> FinanceSnapshot:
        """Return a fresh or explicitly stale finance snapshot."""


def _decimal(value: Any) -> Decimal:
    if value is None or value == "":
        return Decimal("0")
    normalized = str(value).strip().replace("\u00a0", "").replace(" ", "")
    if normalized.count(",") == 1 and "." not in normalized:
        normalized = normalized.replace(",", ".")
    else:
        normalized = normalized.replace(",", "")
    try:
        return Decimal(normalized)
    except InvalidOperation as exc:
        raise ValueError(f"invalid finance amount: {value!r}") from exc


def _row_value(row: dict[str, Any], *names: str, default: Any = "") -> Any:
    for name in names:
        if name in row:
            return row[name]
    return default


def _parse_time(value: Any) -> datetime:
    text = str(value or "").strip()
    if "T" in text:
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
            return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed
        except ValueError:
            pass
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d.%m.%Y %H:%M", "%d.%m.%Y"):
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return datetime.min.replace(tzinfo=timezone.utc)


class GoogleSheetsFinanceSource:
    """FinanceSource backed by Hisobchi's live ``Pul oqimi`` worksheet."""

    def __init__(
        self,
        store: Any,
        *,
        stale_ttl_seconds: int = 900,
        tracking_start_date: str = DEFAULT_TRACKING_START_DATE,
    ) -> None:
        self._store = store
        self._stale_ttl_seconds = max(0, stale_ttl_seconds)
        self._tracking_start_date = parse_tracking_start_date(tracking_start_date)
        self._cached: FinanceSnapshot | None = None

    async def get_snapshot(self) -> FinanceSnapshot:
        try:
            snapshot = await asyncio.to_thread(self._read_live)
        except Exception as exc:
            logger.error("Exception handled in %s", __name__, exc_info=True)
            now = datetime.now(timezone.utc)
            if (
                self._cached is not None
                and (now - self._cached.fetched_at).total_seconds()
                <= self._stale_ttl_seconds
            ):
                return replace(self._cached, source_status="stale")
            raise FinanceSourceUnavailable("Hisobchi Google Sheets is unavailable") from exc
        self._cached = snapshot
        return snapshot

    def _read_live(self) -> FinanceSnapshot:
        worksheet = self._store._worksheets.get(SHEET_PUL_OQIMI)
        if worksheet is None:
            raise FinanceSourceUnavailable("Hisobchi Pul oqimi worksheet is unavailable")
        rows: Sequence[dict[str, Any]] = worksheet.get_all_records()
        fetched_at = datetime.now(timezone.utc)
        month = fetched_at.strftime("%Y-%m")
        income = Decimal("0")
        expense = Decimal("0")
        transactions: list[FinanceTransaction] = []

        for index, row in enumerate(rows, start=1):
            direction = str(
                _row_value(row, "Yonalish", "Yo'nalish", "direction")
            ).strip()
            amount = _decimal(_row_value(row, "Summa", "amount"))
            occurred_at = str(_row_value(row, "Sana", "date")).strip()
            parsed_tx_time = _parse_time(occurred_at)
            if not is_on_or_after_start(
                parsed_tx_time, self._tracking_start_date
            ):
                continue
            normalized_direction = direction.casefold()
            currency = str(
                _row_value(row, "Valyuta", "currency", default="UZS")
            ).strip().upper() or "UZS"
            is_current_month = (
                occurred_at.startswith(month)
                or (parsed_tx_time.year == fetched_at.year and parsed_tx_time.month == fetched_at.month)
            )
            if is_current_month and currency == "UZS":
                if normalized_direction in {"kirim", "in"}:
                    income += amount
                elif normalized_direction in {"chiqim", "out"}:
                    expense += amount

            transactions.append(
                FinanceTransaction(
                    id=str(_row_value(row, "#", "id", default=index)),
                    direction="Kirim"
                    if normalized_direction in {"kirim", "in"}
                    else "Chiqim",
                    amount=amount,
                    currency=currency,
                    description=str(
                        _row_value(
                            row,
                            "Izoh",
                            "Nomi",
                            "reason",
                            "merchant",
                            default="",
                        )
                    ).strip(),
                    occurred_at=occurred_at,
                )
            )

        transactions.sort(key=lambda item: _parse_time(item.occurred_at), reverse=True)
        all_income = sum(
            (
                tx.amount
                for tx in transactions
                if tx.direction == "Kirim" and tx.currency == "UZS"
            ),
            Decimal("0"),
        )
        all_expense = sum(
            (
                tx.amount
                for tx in transactions
                if tx.direction == "Chiqim" and tx.currency == "UZS"
            ),
            Decimal("0"),
        )
        return FinanceSnapshot(
            balance=all_income - all_expense,
            monthly_income=income,
            monthly_expense=expense,
            transactions=tuple(transactions),
            source="hisobchi_google_sheets",
            source_status="fresh",
            fetched_at=fetched_at,
        )


class DatabaseFinanceSource:
    """FinanceSource backed by Turso libSQL / SQLite hisobchi_transactions table."""

    def __init__(
        self,
        db: Any,
        *,
        tracking_start_date: str = DEFAULT_TRACKING_START_DATE,
    ) -> None:
        self._db = db
        self._tracking_start_date = parse_tracking_start_date(tracking_start_date)

    async def _read_transactions(self) -> tuple[FinanceTransaction, ...]:
        try:
            conn = await self._db.get_connection()
            if conn is None:
                raise FinanceSourceUnavailable('Hisobchi database connection is unavailable')
            cursor = await conn.execute(
                'SELECT id, direction, amount, merchant, tx_time, category, currency, reason '
                'FROM hisobchi_transactions ORDER BY id DESC'
            )
            rows = await cursor.fetchall()
            return tuple(tx for row in rows if (tx := self._transaction(row)) is not None)
        except FinanceSourceUnavailable:
            raise
        except Exception as exc:
            logger.warning('[DatabaseFinanceSource] Query failed: %s', type(exc).__name__)
            raise FinanceSourceUnavailable('Hisobchi database is unavailable') from exc

    def _transaction(self, row) -> FinanceTransaction | None:
        occurred_at = str(row[4] or '').strip()
        if not is_on_or_after_start(_parse_time(occurred_at), self._tracking_start_date):
            return None
        currency = str(row[6] or 'UZS').strip().upper()
        direction = str(row[1] or '').strip().casefold()
        if currency != 'UZS':
            raise FinanceSourceUnavailable('Hisobchi database currency conversion is unavailable')
        if direction not in {'kirim', 'in', 'chiqim', 'out'}:
            raise FinanceSourceUnavailable('Hisobchi transaction direction is unknown')
        amount = _decimal(row[2])
        if row[2] is None or row[2] == '' or not amount.is_finite():
            raise FinanceSourceUnavailable('Hisobchi transaction amount is unknown')
        return FinanceTransaction(
            id=str(row[0]), direction='Kirim' if direction in {'kirim', 'in'} else 'Chiqim',
            amount=amount, currency=currency,
            description=str(row[7] or row[3] or row[5] or 'Tranzaksiya').strip(),
            occurred_at=occurred_at,
        )

    async def get_snapshot(self) -> FinanceSnapshot:
        fetched_at = datetime.now(timezone.utc)
        transactions = await self._read_transactions()
        current = [tx for tx in transactions if (
            _parse_time(tx.occurred_at).year, _parse_time(tx.occurred_at).month
        ) == (fetched_at.year, fetched_at.month)]
        def total(rows, direction):
            return sum((tx.amount for tx in rows if tx.direction == direction), Decimal('0'))
        return FinanceSnapshot(
            balance=total(transactions, 'Kirim') - total(transactions, 'Chiqim'),
            monthly_income=total(current, 'Kirim'),
            monthly_expense=total(current, 'Chiqim'),
            transactions=transactions, source='hisobchi_turso_db',
            source_status='fresh', fetched_at=fetched_at,
        )
