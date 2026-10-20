"""Durable mirror, checkpoints, edit journal and cross-process sync lease."""
from __future__ import annotations

import json
import time


class Store:
    def __init__(self, pool):
        self.pool = pool

    async def sql(self, query, params=None):
        rows = await self.pool.execute(query, params or [])
        await self.pool.commit()
        return rows

    async def init(self):
        statements = [
            """CREATE TABLE IF NOT EXISTS parallel_crm_entities (
                kind TEXT NOT NULL, id INTEGER NOT NULL, owner_id INTEGER,
                payload TEXT NOT NULL, observed_at INTEGER NOT NULL,
                PRIMARY KEY(kind,id))""",
            """CREATE TABLE IF NOT EXISTS parallel_crm_meta (
                key TEXT PRIMARY KEY, value TEXT NOT NULL)""",
            """CREATE TABLE IF NOT EXISTS parallel_crm_outbox (
                id TEXT PRIMARY KEY, lead_id INTEGER NOT NULL, actor TEXT NOT NULL,
                base TEXT NOT NULL, patch TEXT NOT NULL, state TEXT NOT NULL,
                reason TEXT, created_at INTEGER NOT NULL, changed_at INTEGER NOT NULL)""",
            """CREATE UNIQUE INDEX IF NOT EXISTS parallel_crm_one_edit
                ON parallel_crm_outbox(lead_id)
                WHERE state IN ('queued','sending','uncertain','conflict')""",
            """CREATE TABLE IF NOT EXISTS parallel_crm_audit (
                seq INTEGER PRIMARY KEY AUTOINCREMENT, operation_id TEXT NOT NULL,
                actor TEXT NOT NULL, state TEXT NOT NULL, reason TEXT,
                changed_at INTEGER NOT NULL)""",
            """CREATE TRIGGER IF NOT EXISTS parallel_crm_insert_audit
                AFTER INSERT ON parallel_crm_outbox BEGIN
                INSERT INTO parallel_crm_audit
                (operation_id,actor,state,reason,changed_at)
                VALUES(NEW.id,NEW.actor,NEW.state,NEW.reason,NEW.changed_at); END""",
            """CREATE TRIGGER IF NOT EXISTS parallel_crm_update_audit
                AFTER UPDATE ON parallel_crm_outbox BEGIN
                INSERT INTO parallel_crm_audit
                (operation_id,actor,state,reason,changed_at)
                VALUES(NEW.id,NEW.actor,NEW.state,NEW.reason,NEW.changed_at); END""",
            """CREATE TABLE IF NOT EXISTS parallel_crm_lease (
                id INTEGER PRIMARY KEY, token TEXT NOT NULL, expires INTEGER NOT NULL)""",
        ]
        for statement in statements:
            await self.sql(statement)

    async def meta(self, key, default=None):
        rows = await self.sql("SELECT value FROM parallel_crm_meta WHERE key=?", [key])
        return json.loads(rows[0]["value"]) if rows else default

    async def set_meta(self, key, value):
        await self.sql(
            """INSERT INTO parallel_crm_meta(key,value) VALUES(?,?)
            ON CONFLICT(key) DO UPDATE SET value=excluded.value""",
            [key, json.dumps(value, ensure_ascii=False)],
        )

    async def upsert(self, kind, item, now):
        await self.sql(
            """INSERT INTO parallel_crm_entities
            (kind,id,owner_id,payload,observed_at) VALUES(?,?,?,?,?)
            ON CONFLICT(kind,id) DO UPDATE SET owner_id=excluded.owner_id,
            payload=excluded.payload,observed_at=excluded.observed_at""",
            [kind, item["id"], item.get("responsible_user_id"),
             json.dumps(item, ensure_ascii=False), now],
        )

    async def get(self, kind, entity_id):
        rows = await self.sql(
            "SELECT payload FROM parallel_crm_entities WHERE kind=? AND id=?",
            [kind, entity_id],
        )
        return json.loads(rows[0]["payload"]) if rows else None

    async def entities(self, kind, *, owner=None, limit=200, offset=0, query=""):
        escaped = query.lower().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        params = [kind, owner, owner, "%" + escaped + "%"]
        total = await self.sql(
            """SELECT COUNT(*) AS n FROM parallel_crm_entities WHERE kind=?
            AND (? IS NULL OR owner_id=?)
            AND COALESCE(LOWER(json_extract(payload,'$.name')),'') LIKE ? ESCAPE '\\'""",
            params,
        )
        rows = await self.sql(
            """SELECT payload FROM parallel_crm_entities WHERE kind=?
            AND (? IS NULL OR owner_id=?)
            AND COALESCE(LOWER(json_extract(payload,'$.name')),'') LIKE ? ESCAPE '\\'
            ORDER BY id DESC LIMIT ? OFFSET ?""", params + [limit, offset],
        )
        return [json.loads(row["payload"]) for row in rows], total[0]["n"]

    async def operations(self, *, owner=None):
        sql = "SELECT o.* FROM parallel_crm_outbox o"
        params = []
        if owner is not None:
            sql += """ JOIN parallel_crm_entities e ON e.kind='leads'
                AND e.id=o.lead_id WHERE e.owner_id=?"""
            params.append(owner)
        sql += " ORDER BY o.created_at DESC LIMIT 100"
        return [dict(row) for row in await self.sql(sql, params)]

    async def operation(self, request_id):
        rows = await self.sql("SELECT * FROM parallel_crm_outbox WHERE id=?", [request_id])
        return dict(rows[0]) if rows else None

    async def tasks_for(self, lead_id):
        rows = await self.sql(
            """SELECT payload FROM parallel_crm_entities
            WHERE kind='tasks' AND json_extract(payload,'$.entity_type')='leads'
            AND json_extract(payload,'$.entity_id')=?
            ORDER BY COALESCE(json_extract(payload,'$.is_completed'),0),
            json_extract(payload,'$.complete_till') LIMIT 100""", [lead_id],
        )
        return [json.loads(row["payload"]) for row in rows]

    async def task_count(self, lead_id):
        rows = await self.sql(
            """SELECT COUNT(*) AS n FROM parallel_crm_entities
            WHERE kind='tasks' AND json_extract(payload,'$.entity_type')='leads'
            AND json_extract(payload,'$.entity_id')=?""", [lead_id],
        )
        return rows[0]["n"]

    async def enqueue(self, request_id, lead_id, actor, base, patch):
        now = int(time.time())
        await self.sql(
            """INSERT INTO parallel_crm_outbox
            (id,lead_id,actor,base,patch,state,created_at,changed_at)
            VALUES(?,?,?,?,?,'queued',?,?)""",
            [request_id, lead_id, actor, json.dumps(base), json.dumps(patch), now, now],
        )
        return await self.operation(request_id)

    async def state(self, operation_id, state, reason=None):
        await self.sql(
            "UPDATE parallel_crm_outbox SET state=?,reason=?,changed_at=? WHERE id=?",
            [state, reason, int(time.time()), operation_id],
        )

    async def transition(self, operation_id, previous, state, reason=None):
        return bool(await self.sql(
            """UPDATE parallel_crm_outbox SET state=?,reason=?,changed_at=?
            WHERE id=? AND state=? RETURNING id""",
            [state, reason, int(time.time()), operation_id, previous],
        ))

    async def discard(self, operation_id):
        return await self.sql(
            """UPDATE parallel_crm_outbox SET state='discarded',reason='operator_discarded',
            changed_at=? WHERE id=? AND state IN ('queued','conflict','uncertain')
            RETURNING id""", [int(time.time()), operation_id],
        )

    async def lease(self, token):
        now = int(time.time())
        return bool(await self.sql(
            """INSERT INTO parallel_crm_lease(id,token,expires) VALUES(1,?,?)
            ON CONFLICT(id) DO UPDATE SET token=excluded.token,expires=excluded.expires
            WHERE parallel_crm_lease.expires<? OR parallel_crm_lease.token=excluded.token
            RETURNING token""", [token, now + 180, now],
        ))

    async def release(self, token):
        await self.sql("DELETE FROM parallel_crm_lease WHERE token=?", [token])

    async def recover(self):
        # Called only after acquiring the global sync lease.
        await self.sql(
            """UPDATE parallel_crm_outbox SET state='uncertain',
            reason='interrupted_write',changed_at=? WHERE state='sending'""",
            [int(time.time())],
        )

    async def due(self):
        rows = await self.sql(
            """SELECT * FROM parallel_crm_outbox WHERE state IN ('queued','uncertain')
            ORDER BY changed_at,id LIMIT 20"""
        )
        return [dict(row) for row in rows]
