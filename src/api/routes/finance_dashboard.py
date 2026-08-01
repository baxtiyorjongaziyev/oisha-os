"""Finance Dashboard API.

The dashboard must never present sample values as real company finances. Until a
real, production-backed finance source is wired in, these endpoints fail closed
with an explicit service-unavailable response.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any

from fastapi import APIRouter, HTTPException, status

from src.api.rbac import Permission, require_permissions
from src.api.routes.state import api_state
from src.services.core.finance.finance_source import (
    FinanceSnapshot,
    FinanceSourceUnavailable,
)

router = APIRouter(tags=["finance-dashboard"])

_SOURCE_NOT_CONFIGURED = {
    "code": "finance_source_not_configured",
    "message": "Real finance data source is not configured",
}


def _raise_source_not_configured() -> None:
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=_SOURCE_NOT_CONFIGURED,
    )


def _money(value: Decimal) -> int | float:
    integral = value.to_integral_value()
    return int(integral) if value == integral else float(value)


def _snapshot_payload(snapshot: FinanceSnapshot) -> dict[str, Any]:
    return {
        "balance": _money(snapshot.balance),
        "monthly_income": _money(snapshot.monthly_income),
        "monthly_expense": _money(snapshot.monthly_expense),
        "source": snapshot.source,
        "source_status": snapshot.source_status,
        "fetched_at": snapshot.fetched_at.isoformat(),
    }


def _transaction_payload(transaction: Any) -> dict[str, Any]:
    return {
        "id": transaction.id,
        "direction": transaction.direction,
        "amount": _money(transaction.amount),
        "currency": transaction.currency,
        "description": transaction.description,
        "occurred_at": transaction.occurred_at,
    }


async def _get_snapshot() -> FinanceSnapshot:
    source = api_state.finance_source
    if source is None:
        _raise_source_not_configured()
    try:
        return await source.get_snapshot()
    except FinanceSourceUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "finance_source_unavailable",
                "message": "Real finance data source is temporarily unavailable",
            },
        ) from exc


@router.get(
    "/api/finance/dashboard",
    dependencies=[require_permissions(Permission.FINANCE_READ)],
)
async def finance_dashboard():
    """Return finance KPIs from the configured real source."""
    return _snapshot_payload(await _get_snapshot())


@router.get(
    "/api/finance/transactions",
    dependencies=[require_permissions(Permission.FINANCE_READ)],
)
async def finance_transactions():
    """Return finance transactions from the configured real source."""
    snapshot = await _get_snapshot()
    payload = _snapshot_payload(snapshot)
    payload["transactions"] = [
        _transaction_payload(transaction) for transaction in snapshot.transactions
    ]
    return payload
