"""Finance Dashboard API.

The dashboard must never present sample values as real company finances. Until a
real, production-backed finance source is wired in, these endpoints fail closed
with an explicit service-unavailable response.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

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


@router.get("/api/finance/dashboard")
async def finance_dashboard():
    """Return finance KPIs only after a real source is connected."""
    _raise_source_not_configured()


@router.get("/api/finance/transactions")
async def finance_transactions():
    """Return finance transactions only after a real source is connected."""
    _raise_source_not_configured()
