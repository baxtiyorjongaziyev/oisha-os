"""Bounded read-only scanning using the already-running Oracle client."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from src.services.core.leads.prospect_signals import classify_message

SCAN_LOCK = asyncio.Lock()


async def scan_prospects(client, store, *, now=None):
    if SCAN_LOCK.locked():
        return {"status": "busy", "new": None, "sources": []}
    async with SCAN_LOCK:
        await store.initialize()
        sources = await store.sources()
        if not sources or client is None or not client.is_connected():
            for source in sources:
                await store.record_scan(source["chat_id"], "source_unavailable", datetime.now(timezone.utc).isoformat())
            return {"status": "source_unavailable", "new": None, "sources": []}
        now = now or datetime.now(timezone.utc)
        new = 0
        reports = []
        for source in sources:
            report = await _scan_source(client, store, source, now)
            new += report["new"] or 0
            reports.append(report)
        failures = sum(r["status"] == "source_unavailable" for r in reports)
        incomplete = any(r["status"] != "ok" for r in reports)
        status = "source_unavailable" if failures == len(reports) else "partial" if incomplete else "ok"
        return {"status": status, "new": None if failures == len(reports) else new, "sources": reports}


async def _scan_source(client, store, source, now):
    count = 0
    new = 0
    chat_id = source["chat_id"]
    status = "ok"
    try:
        async with asyncio.timeout(60):
            async for message in client.iter_messages(chat_id, limit=200):
                count += 1
                published = getattr(message, "date", None)
                if published and published.tzinfo and published < now - timedelta(days=7):
                    break
                for prospect in classify_message(message, chat_id, now):
                    if await store.save(prospect):
                        new += 1
                if count == 200:
                    status = "window_limited"
    except Exception as exc:
        # Do not persist external exception messages (may contain request credentials).
        status = "source_unavailable"
        await store.record_scan(chat_id, status, now.isoformat())
        return {"chat_id": chat_id, "status": status, "new": new or None, "error_type": type(exc).__name__}
    await store.record_scan(chat_id, status, now.isoformat())
    return {"chat_id": chat_id, "status": status, "new": new, "messages": count}
