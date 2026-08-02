"""Shared accounting-period rules for every Hisobchi data backend."""

from __future__ import annotations

from datetime import date, datetime


DEFAULT_TRACKING_START_DATE = "2026-08-01"


def parse_tracking_start_date(value: str) -> date:
    """Parse the inclusive Hisobchi start date from an ISO date string."""
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("HISOBCHI_TRACKING_START_DATE must use YYYY-MM-DD") from exc


def is_on_or_after_start(value: datetime, start_date: date) -> bool:
    """Return whether a transaction belongs to the configured ledger."""
    return value.date() >= start_date
