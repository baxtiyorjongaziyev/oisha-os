"""Durable prospect review queue through the canonical database pool."""
from __future__ import annotations

import json

from src.services.core.leads.prospect_signals import Prospect


class ProspectStore:
    def __init__(self, pool):
        self.pool = pool

    async def initialize(self):
        for sql in (
            "CREATE TABLE IF NOT EXISTS prospect_sources (chat_id INTEGER PRIMARY KEY, title TEXT NOT NULL, enabled INTEGER NOT NULL DEFAULT 1, last_status TEXT, last_scan TEXT)",
            "CREATE TABLE IF NOT EXISTS prospect_queue (candidate_key TEXT PRIMARY KEY, payload TEXT NOT NULL, created_at TEXT NOT NULL)",
            "CREATE TABLE IF NOT EXISTS prospect_config (name TEXT PRIMARY KEY, value TEXT NOT NULL)",
        ):
            await self.pool.execute(sql)
        await self.pool.commit()

    async def add_source(self, chat_id: int, title: str):
        await self.pool.execute(
            "INSERT INTO prospect_sources(chat_id,title) VALUES (?,?) ON CONFLICT(chat_id) DO UPDATE SET title=excluded.title, enabled=1",
            [chat_id, title],
        )
        await self.pool.commit()

    async def disable_source(self, chat_id: int):
        await self.pool.execute("UPDATE prospect_sources SET enabled=0 WHERE chat_id=?", [chat_id])
        await self.pool.commit()

    async def sources(self):
        return await self.pool.execute("SELECT * FROM prospect_sources WHERE enabled=1 ORDER BY chat_id")

    async def set_auto(self, enabled: bool):
        await self.pool.execute(
            "INSERT INTO prospect_config(name,value) VALUES ('auto',?) ON CONFLICT(name) DO UPDATE SET value=excluded.value",
            ["on" if enabled else "off"],
        )
        await self.pool.commit()

    async def auto_enabled(self):
        rows = await self.pool.execute("SELECT value FROM prospect_config WHERE name='auto'")
        return bool(rows and rows[0]["value"] == "on")

    async def save(self, prospect: Prospect):
        rows = await self.pool.execute(
            "INSERT INTO prospect_queue(candidate_key,payload,created_at) VALUES (?,?,?) ON CONFLICT(candidate_key) DO NOTHING RETURNING candidate_key",
            [prospect.key, prospect.model_dump_json(), prospect.observed_at.isoformat()],
        )
        await self.pool.commit()
        return bool(rows)

    async def record_scan(self, chat_id: int, status: str, observed_at: str):
        await self.pool.execute(
            "UPDATE prospect_sources SET last_status=?, last_scan=? WHERE chat_id=?",
            [status, observed_at, chat_id],
        )
        await self.pool.commit()

    async def recent(self, limit: int = 10):
        rows = await self.pool.execute(
            "SELECT payload FROM prospect_queue ORDER BY created_at DESC LIMIT ?", [min(max(limit, 1), 20)]
        )
        return [json.loads(row["payload"]) for row in rows]


def get_prospect_store():
    from src.database_pool import db_pool

    return ProspectStore(db_pool)
