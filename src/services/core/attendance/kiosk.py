"""Ofis monitori kalitlari: HR panelidan bir bosishda yaratiladi, xeshi saqlanadi."""
from __future__ import annotations

import hashlib
import secrets

from src.services.core.attendance import audit, repo

PREFIX = "oak_"


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


async def create(db, *, actor: str, label: str, ip: str | None = None) -> str:
    token = PREFIX + secrets.token_urlsafe(32)
    rows = await db.execute(
        "INSERT INTO attendance_kiosk_tokens (token_hash, label, created_by) VALUES (?, ?, ?) RETURNING id",
        [_hash(token), label, actor])
    await audit.log(db, actor=actor, action="kiosk_token_created", entity="kiosk_token",
                    entity_id=rows[0][0], details={"label": label}, ip=ip)
    await db.commit()
    return token


async def verify(db, token: str) -> bool:
    if not token.startswith(PREFIX) or len(token) > 128:
        return False
    rows = await db.execute(
        "UPDATE attendance_kiosk_tokens SET last_used_at = CURRENT_TIMESTAMP"
        " WHERE token_hash = ? AND revoked_at IS NULL RETURNING id", [_hash(token)])
    await db.commit()
    return bool(rows)


async def list_tokens(db) -> list[dict]:
    rows = await db.execute("SELECT id, label, created_by, created_at, last_used_at, revoked_at"
                            " FROM attendance_kiosk_tokens ORDER BY id DESC", [])
    return [{k: r[k] for k in ("id", "label", "created_by", "created_at", "last_used_at", "revoked_at")}
            for r in rows]


async def revoke(db, *, actor: str, token_id: int, ip: str | None = None) -> bool:
    rows = await db.execute("UPDATE attendance_kiosk_tokens SET revoked_at = CURRENT_TIMESTAMP"
                            " WHERE id = ? AND revoked_at IS NULL RETURNING id", [token_id])
    if rows:
        await audit.log(db, actor=actor, action="kiosk_token_revoked", entity="kiosk_token",
                        entity_id=token_id, ip=ip)
    await db.commit()
    return bool(rows)


async def has_any_active(db) -> bool:
    return bool(await repo.one(db, "SELECT 1 FROM attendance_kiosk_tokens WHERE revoked_at IS NULL", []))
