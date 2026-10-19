"""Stable source -> Twenty id mapping with per-record sync state.

States:
  synced     Twenty record exists and matches ``digest``.
  pending    A write is about to be sent (crash here => treated as uncertain).
  uncertain  Write outcome unknown; must be reconciled before any new write.
  failed     Definite failure; safe to retry after ``attempts`` backoff.
  blocked    Retry limit reached; needs operator review.
"""
from __future__ import annotations

import hashlib
import json
import time

MAX_ATTEMPTS = 5


def digest(payload: dict) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str).encode()
    ).hexdigest()


class MapStore:
    def __init__(self, pool, *, clock=time.time):
        self.pool, self.clock = pool, clock

    async def sql(self, query, params=None):
        rows = await self.pool.execute(query, params or [])
        await self.pool.commit()
        return rows

    async def init(self):
        await self.sql(
            """CREATE TABLE IF NOT EXISTS twenty_sync_map (
                source_system TEXT NOT NULL, kind TEXT NOT NULL, source_id TEXT NOT NULL,
                twenty_id TEXT, digest TEXT, state TEXT NOT NULL,
                attempts INTEGER NOT NULL DEFAULT 0, last_error TEXT,
                updated_at INTEGER NOT NULL,
                PRIMARY KEY(source_system, kind, source_id))"""
        )
        await self.sql(
            """CREATE UNIQUE INDEX IF NOT EXISTS twenty_sync_map_target
                ON twenty_sync_map(kind, twenty_id) WHERE twenty_id IS NOT NULL"""
        )

    async def get(self, kind: str, source_id, system: str = "amocrm") -> dict | None:
        rows = await self.sql(
            """SELECT * FROM twenty_sync_map
            WHERE source_system=? AND kind=? AND source_id=?""",
            [system, kind, str(source_id)],
        )
        return dict(rows[0]) if rows else None

    async def put(self, kind, source_id, *, state, twenty_id=None, dig=None,
                  error=None, attempts=None, system="amocrm"):
        current = await self.get(kind, source_id, system)
        if attempts is None:
            attempts = 0 if state == "synced" else (current or {}).get("attempts", 0)
        await self.sql(
            """INSERT INTO twenty_sync_map
            (source_system,kind,source_id,twenty_id,digest,state,attempts,last_error,updated_at)
            VALUES(?,?,?,?,?,?,?,?,?)
            ON CONFLICT(source_system,kind,source_id) DO UPDATE SET
              twenty_id=COALESCE(excluded.twenty_id, twenty_sync_map.twenty_id),
              digest=COALESCE(excluded.digest, twenty_sync_map.digest),
              state=excluded.state, attempts=excluded.attempts,
              last_error=excluded.last_error, updated_at=excluded.updated_at""",
            [system, kind, str(source_id), twenty_id, dig, state, attempts, error,
             int(self.clock())],
        )

    async def fail(self, kind, source_id, error, *, uncertain=False, system="amocrm"):
        current = await self.get(kind, source_id, system) or {}
        attempts = current.get("attempts", 0) + 1
        if attempts >= MAX_ATTEMPTS:
            state = "blocked"
        else:
            state = "uncertain" if uncertain else "failed"
        await self.put(kind, source_id, state=state, error=error,
                       attempts=attempts, system=system)
        return state

    async def claim(self, kind, source_id, allowed=("failed", "uncertain"),
                    system="amocrm", stale_after=300) -> bool:
        """Atomically elect one writer. A fresh 'pending' row means another
        writer is in flight; a stale one is treated as an interrupted write."""
        now = int(self.clock())
        first, second = (tuple(allowed) + ("", ""))[:2]
        rows = await self.sql(
            """INSERT INTO twenty_sync_map
            (source_system,kind,source_id,state,attempts,updated_at)
            VALUES(?,?,?,'pending',0,?)
            ON CONFLICT(source_system,kind,source_id) DO UPDATE SET
              state='pending', updated_at=excluded.updated_at
            WHERE twenty_sync_map.state IN (?,?)
               OR (twenty_sync_map.state='pending' AND twenty_sync_map.updated_at<?)
            RETURNING source_id""",
            [system, kind, str(source_id), now, first, second, now - stale_after],
        )
        return bool(rows)

    async def recover_interrupted(self, system="amocrm"):
        """A crash between 'pending' and the result leaves the outcome unknown.
        Scoped to one source system so live webhook writes are not disturbed."""
        await self.sql(
            """UPDATE twenty_sync_map SET state='uncertain', last_error='interrupted_write',
            updated_at=? WHERE state='pending' AND source_system=?""",
            [int(self.clock()), system],
        )

    async def counts(self) -> dict[str, dict[str, int]]:
        rows = await self.sql(
            "SELECT kind, state, COUNT(*) AS n FROM twenty_sync_map GROUP BY kind, state"
        )
        out: dict[str, dict[str, int]] = {}
        for row in rows:
            out.setdefault(row["kind"], {})[row["state"]] = row["n"]
        return out

    async def problems(self, limit: int = 50) -> list[dict]:
        rows = await self.sql(
            """SELECT kind, source_id, state, attempts, last_error FROM twenty_sync_map
            WHERE state IN ('uncertain','failed','blocked')
            ORDER BY updated_at LIMIT ?""", [limit],
        )
        return [dict(r) for r in rows]
