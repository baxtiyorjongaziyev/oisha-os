"""Persistence for AI ROP: per-seller targets + key/value tuning config."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from src.db.repositories.base import BaseRepository

_TARGET_COLUMNS = (
    "seller_name", "telegram_user_id", "expected_sales", "calls", "follow_ups",
    "meetings", "proposals", "payments", "max_overdue", "active",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class RopRepository(BaseRepository):
    async def init_table(self) -> None:
        await self._execute(
            """CREATE TABLE IF NOT EXISTS rop_targets (
                responsible_user_id INTEGER PRIMARY KEY,
                seller_name TEXT,
                telegram_user_id INTEGER,
                expected_sales INTEGER NOT NULL DEFAULT 1,
                calls INTEGER NOT NULL DEFAULT 10,
                follow_ups INTEGER NOT NULL DEFAULT 20,
                meetings INTEGER NOT NULL DEFAULT 2,
                proposals INTEGER NOT NULL DEFAULT 0,
                payments INTEGER NOT NULL DEFAULT 1,
                max_overdue INTEGER NOT NULL DEFAULT 0,
                active INTEGER NOT NULL DEFAULT 1,
                updated_at TEXT NOT NULL
            )"""
        )
        await self._execute(
            """CREATE TABLE IF NOT EXISTS rop_config (
                key TEXT PRIMARY KEY,
                value_json TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )"""
        )
        conn = await self._get_conn()
        await conn.commit()

    async def upsert_target(
        self,
        responsible_user_id: int,
        *,
        seller_name: str,
        telegram_user_id: int | None,
        expected_sales: int = 1,
        calls: int = 10,
        follow_ups: int = 20,
        meetings: int = 2,
        proposals: int = 0,
        payments: int = 1,
        max_overdue: int = 0,
        active: int = 1,
    ) -> None:
        conn = await self._get_conn()
        await conn.execute(
            """INSERT INTO rop_targets (
                   responsible_user_id, seller_name, telegram_user_id, expected_sales,
                   calls, follow_ups, meetings, proposals, payments, max_overdue,
                   active, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(responsible_user_id) DO UPDATE SET
                   seller_name = excluded.seller_name,
                   telegram_user_id = excluded.telegram_user_id,
                   expected_sales = excluded.expected_sales,
                   calls = excluded.calls,
                   follow_ups = excluded.follow_ups,
                   meetings = excluded.meetings,
                   proposals = excluded.proposals,
                   payments = excluded.payments,
                   max_overdue = excluded.max_overdue,
                   active = excluded.active,
                   updated_at = excluded.updated_at""",
            (
                responsible_user_id, seller_name, telegram_user_id, expected_sales,
                calls, follow_ups, meetings, proposals, payments, max_overdue,
                active, _now(),
            ),
        )
        await conn.commit()

    async def list_active_targets(self) -> list[dict]:
        rows = await self._fetch_all(
            "SELECT * FROM rop_targets WHERE active = 1 ORDER BY responsible_user_id"
        )
        return rows

    async def get_config(self, key: str, default: Any = None) -> Any:
        row = await self._fetch_one(
            "SELECT value_json FROM rop_config WHERE key = ?", (key,)
        )
        if row is None:
            return default
        raw = row["value_json"] if isinstance(row, dict) else row[0]
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return default

    async def set_config(self, key: str, value: Any) -> None:
        conn = await self._get_conn()
        await conn.execute(
            """INSERT INTO rop_config (key, value_json, updated_at)
               VALUES (?, ?, ?)
               ON CONFLICT(key) DO UPDATE SET
                   value_json = excluded.value_json,
                   updated_at = excluded.updated_at""",
            (key, json.dumps(value), _now()),
        )
        await conn.commit()

    async def all_config(self) -> dict[str, Any]:
        rows = await self._fetch_all("SELECT key, value_json FROM rop_config")
        out: dict[str, Any] = {}
        for r in rows:
            k = r["key"] if isinstance(r, dict) else r[0]
            v = r["value_json"] if isinstance(r, dict) else r[1]
            try:
                out[k] = json.loads(v)
            except (json.JSONDecodeError, TypeError):
                continue
        return out
