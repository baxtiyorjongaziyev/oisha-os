"""Append-only audit jurnali (``attendance_audit_logs``)."""
from __future__ import annotations

import json
from typing import Any


async def log(db, *, actor: str, action: str, entity: str, entity_id: Any = None,
              details: dict | None = None, ip: str | None = None) -> None:
    await db.execute(
        "INSERT INTO attendance_audit_logs (actor, action, entity, entity_id, details, ip)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        [actor, action, entity, None if entity_id is None else str(entity_id),
         json.dumps(details or {}, ensure_ascii=False, default=str), ip],
    )
