"""Turso/SQLite jadvallari: kanonik shaxslar, snapshotlar, Telegram navbati, konfliktlar."""

import json
from datetime import datetime
from typing import Any, Awaitable, Callable, Optional

from .merge import Conflict
from .models import Person

Execute = Callable[[str, Optional[list]], Awaitable[list]]

_SCHEMA = (
    "CREATE TABLE IF NOT EXISTS community_people ("
    "key TEXT PRIMARY KEY, data TEXT NOT NULL, updated_at TEXT)",
    "CREATE TABLE IF NOT EXISTS community_snapshots ("
    "system TEXT NOT NULL, key TEXT NOT NULL, data TEXT NOT NULL, "
    "PRIMARY KEY (system, key))",
    "CREATE TABLE IF NOT EXISTS community_tg_queue ("
    "key TEXT PRIMARY KEY, username TEXT, phone TEXT, status TEXT NOT NULL, "
    "wait_until TEXT, added_at TEXT)",
    "CREATE TABLE IF NOT EXISTS community_conflicts ("
    "key TEXT NOT NULL, field TEXT NOT NULL, vals TEXT NOT NULL, "
    "status TEXT NOT NULL, value TEXT, PRIMARY KEY (key, field))",
)


def _default_execute() -> Execute:
    from src.database_pool import DatabasePool

    return DatabasePool().execute


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


class SyncStore:
    def __init__(self, execute: Optional[Execute] = None):
        self._exec = execute or _default_execute()

    async def ensure_schema(self) -> None:
        for sql in _SCHEMA:
            await self._exec(sql, [])

    async def load_people(self) -> dict[str, Person]:
        rows = await self._exec("SELECT key, data FROM community_people", [])
        out = {}
        for r in rows:
            d = json.loads(r["data"])
            d["cohorts"] = set(d.get("cohorts", []))
            out[r["key"]] = Person(**d)
        return out

    async def upsert_person(self, p: Person) -> None:
        d = dict(p.__dict__, cohorts=sorted(p.cohorts))
        await self._exec(
            "INSERT INTO community_people (key, data, updated_at) VALUES (?, ?, ?) "
            "ON CONFLICT(key) DO UPDATE SET data=excluded.data, updated_at=excluded.updated_at",
            [p.key, json.dumps(d, ensure_ascii=False), _now()],
        )

    async def load_snapshots(self) -> dict[str, dict[str, dict[str, str]]]:
        rows = await self._exec("SELECT system, key, data FROM community_snapshots", [])
        out: dict[str, dict[str, dict[str, str]]] = {}
        for r in rows:
            out.setdefault(r["system"], {})[r["key"]] = json.loads(r["data"])
        return out

    async def save_snapshot(self, system: str, key: str, fields: dict[str, Any]) -> None:
        await self._exec(
            "INSERT INTO community_snapshots (system, key, data) VALUES (?, ?, ?) "
            "ON CONFLICT(system, key) DO UPDATE SET data=excluded.data",
            [system, key, json.dumps(fields, ensure_ascii=False)],
        )

    async def enqueue_tg(self, key: str, username: str, phone: str) -> None:
        await self._exec(
            "INSERT OR IGNORE INTO community_tg_queue "
            "(key, username, phone, status, added_at) VALUES (?, ?, ?, 'pending', ?)",
            [key, username, phone, _now()],
        )

    async def due_tg(self, limit: int, now: datetime) -> list[dict]:
        return await self._exec(
            "SELECT key, username, phone FROM community_tg_queue "
            "WHERE status IN ('pending', 'deferred') "
            "AND (wait_until IS NULL OR wait_until <= ?) ORDER BY added_at, key LIMIT ?",
            [now.isoformat(timespec="seconds"), int(limit)],
        )

    async def mark_tg(self, key: str, status: str, wait_until: Optional[datetime] = None) -> None:
        await self._exec(
            "UPDATE community_tg_queue SET status=?, wait_until=? WHERE key=?",
            [status, wait_until.isoformat(timespec="seconds") if wait_until else None, key],
        )

    async def add_conflict(self, c: Conflict) -> None:
        await self._exec(
            "INSERT INTO community_conflicts (key, field, vals, status) VALUES (?, ?, ?, 'open') "
            "ON CONFLICT(key, field) DO UPDATE SET vals=excluded.vals, status='open'",
            [c.key, c.field, json.dumps(c.values, ensure_ascii=False)],
        )

    async def open_conflicts(self) -> list[Conflict]:
        rows = await self._exec(
            "SELECT key, field, vals FROM community_conflicts WHERE status='open'", []
        )
        return [Conflict(r["key"], r["field"], json.loads(r["vals"])) for r in rows]

    async def resolve_conflict(self, key: str, field: str, value: str) -> None:
        await self._exec(
            "UPDATE community_conflicts SET status='resolved', value=? WHERE key=? AND field=?",
            [value, key, field],
        )

    async def resolved_values(self) -> dict[str, dict[str, str]]:
        rows = await self._exec(
            "SELECT key, field, value FROM community_conflicts WHERE status='resolved'", []
        )
        out: dict[str, dict[str, str]] = {}
        for r in rows:
            out.setdefault(r["key"], {})[r["field"]] = r["value"]
        return out

    async def clear_resolved(self) -> None:
        await self._exec(
            "UPDATE community_conflicts SET status='applied' WHERE status='resolved'", []
        )
