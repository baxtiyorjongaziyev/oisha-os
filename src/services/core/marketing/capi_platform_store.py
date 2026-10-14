"""Durable CAPI intake with atomic leases and masked operator projections."""
from __future__ import annotations

import datetime
import json
import uuid


def _pool():
    from src.database_pool import db_pool
    return db_pool


def now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


async def ensure_table():
    await _pool().execute(
        "CREATE TABLE IF NOT EXISTS capi_platform_events ("
        "event_id TEXT NOT NULL, event_name TEXT NOT NULL, source TEXT NOT NULL, "
        "dataset_id TEXT NOT NULL, mode TEXT NOT NULL, payload TEXT NOT NULL, "
        "status TEXT NOT NULL DEFAULT 'queued', attempts INTEGER NOT NULL DEFAULT 0, "
        "error TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL, updated_at TEXT NOT NULL, "
        "lease TEXT, next_attempt_at TEXT NOT NULL, sent_at TEXT, "
        "PRIMARY KEY(dataset_id, mode, event_name, event_id))"
    )
    await _pool().commit()


async def enqueue(event: dict, source: str, dataset_id: str, mode: str):
    await ensure_table()
    stamp = now()
    rows = await _pool().execute(
        "INSERT INTO capi_platform_events "
        "(event_id,event_name,source,dataset_id,mode,payload,created_at,updated_at,next_attempt_at) "
        "VALUES (?,?,?,?,?,?,?,?,?) ON CONFLICT DO NOTHING RETURNING event_id",
        [event["event_id"], event["event_name"], source, dataset_id, mode,
         json.dumps(event, separators=(",", ":")), stamp, stamp, stamp],
    )
    await _pool().commit()
    if rows:
        return True
    existing = await _pool().execute(
        "SELECT payload FROM capi_platform_events WHERE dataset_id=? AND mode=? AND event_name=? AND event_id=?",
        [dataset_id, mode, event["event_name"], event["event_id"]],
    )
    if existing:
        existing_payload = json.loads(existing[0]["payload"])
        if existing_payload != event:
            raise ValueError("event_id_conflict")
    return False


async def claim(event_id: str, event_name: str, dataset_id: str, mode: str):
    stamp = now()
    stale = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=10)).isoformat()
    lease = uuid.uuid4().hex
    rows = await _pool().execute(
        "UPDATE capi_platform_events SET status='pending', lease=?, "
        "attempts=attempts+1, updated_at=? WHERE event_id=? AND event_name=? "
        "AND dataset_id=? AND mode=? AND ((status IN ('queued','failed') AND next_attempt_at<=?) "
        "OR (status='pending' AND updated_at<?)) RETURNING payload, attempts",
        [lease, stamp, event_id, event_name, dataset_id, mode, stamp, stale],
    )
    await _pool().commit()
    return (lease, dict(rows[0])) if rows else None


async def finish(key: tuple, lease: str, ok: bool, error: str, attempts: int):
    delay = min(3600, 30 * 2 ** min(attempts, 7))
    next_at = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=delay)).isoformat()
    if ok:
        status = "sent"
    elif error == "event_expired":
        status = "expired"
    elif error.startswith("HTTP 4"):
        status = "rejected"
    else:
        status = "failed"
    await _pool().execute(
        "UPDATE capi_platform_events SET status=?,error=?,updated_at=?,next_attempt_at=?,"
        "sent_at=? WHERE event_id=? AND event_name=? AND dataset_id=? AND mode=? AND lease=?",
        [status, error, now(), next_at, now() if ok else None, *key, lease],
    )
    await _pool().commit()


async def events(limit: int = 100):
    await ensure_table()
    rows = await _pool().execute(
        "SELECT event_id,event_name,source,dataset_id,mode,status,attempts,error,"
        "created_at,updated_at,sent_at FROM capi_platform_events ORDER BY created_at DESC LIMIT ?",
        [limit],
    )
    return [dict(row) for row in rows]


async def due(dataset_id: str, mode: str):
    await ensure_table()
    stale = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=10)).isoformat()
    return await _pool().execute(
        "SELECT event_id,event_name FROM capi_platform_events WHERE dataset_id=? AND mode=? "
        "AND ((status IN ('queued','failed') AND next_attempt_at<=?) "
        "OR (status='pending' AND updated_at<?)) ORDER BY created_at LIMIT 20",
        [dataset_id, mode, now(), stale],
    )
