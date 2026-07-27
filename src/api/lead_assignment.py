"""Canonical lead assignment writes and explicit existing-data backfill."""
from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any


def _clean_subject(value: Any) -> str:
    subject = str(value or "").strip()
    if not subject or len(subject) > 128:
        raise ValueError("seller subject must be between 1 and 128 characters")
    return subject


def parse_assignment_map(raw: str) -> dict[int, str]:
    """Parse ``{lead_user_id: seller_subject}`` JSON and fail closed."""
    try:
        payload = json.loads(str(raw or "").strip() or "{}")
    except (TypeError, ValueError) as exc:
        raise ValueError("invalid lead assignment JSON") from exc
    if not isinstance(payload, Mapping):
        raise ValueError("lead assignment JSON must be an object")

    assignments: dict[int, str] = {}
    for raw_user_id, raw_subject in payload.items():
        try:
            user_id = int(str(raw_user_id).strip())
        except (TypeError, ValueError) as exc:
            raise ValueError("lead assignment keys must be integer user IDs") from exc
        if user_id <= 0:
            raise ValueError("lead assignment user IDs must be positive")
        assignments[user_id] = _clean_subject(raw_subject)
    return assignments


async def apply_assignment_backfill(connection, assignments: Mapping[int, str]) -> int:
    """Populate only currently unassigned rows from an explicit mapping."""
    changed = 0
    for user_id, seller_subject in assignments.items():
        subject = _clean_subject(seller_subject)
        if int(user_id) <= 0:
            raise ValueError("lead assignment user IDs must be positive")
        result = await connection.execute(
            """
            UPDATE users
            SET assigned_to = ?
            WHERE user_id = ?
              AND (assigned_to IS NULL OR TRIM(assigned_to) = '')
            """,
            (subject, int(user_id)),
        )
        changed += max(0, int(getattr(result, "rowcount", 0) or 0))
    if assignments:
        await connection.commit()
    return changed


async def assign_lead(connection, *, user_id: int, seller_subject: str) -> bool:
    """Explicitly assign or reassign one lead through the canonical write path."""
    if int(user_id) <= 0:
        raise ValueError("user_id must be positive")
    subject = _clean_subject(seller_subject)
    result = await connection.execute(
        "UPDATE users SET assigned_to = ? WHERE user_id = ?",
        (subject, int(user_id)),
    )
    await connection.commit()
    return int(getattr(result, "rowcount", 0) or 0) > 0
