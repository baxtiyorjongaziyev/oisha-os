"""Bounded pull and verified write-back; no deletes, creates or workflow side effects."""
from __future__ import annotations

import json
import re
import time
from uuid import uuid4

from src.time_utils import is_quiet_hours

from .schema import RemoteLead, baseline, matches
from .remote import RemoteMissing


class Sync:
    def __init__(self, store, remote, *, writeback=False, clock=time.time,
                 can_dispatch=None):
        self.store, self.remote = store, remote
        self.writeback, self.clock = writeback, clock
        self.token = str(uuid4())
        self.can_dispatch = can_dispatch or (lambda: not is_quiet_hours())

    async def renew(self):
        if not await self.store.lease(self.token):
            raise RuntimeError("sync_lease_lost")

    async def bind(self):
        account = await self.remote.account()
        account_id = account.get("id")
        if not isinstance(account_id, int) or account_id <= 0:
            raise ValueError("invalid_account")
        previous = await self.store.meta("account")
        if previous and previous["id"] != account_id:
            raise ValueError("account_changed")
        await self.store.set_meta("account", {
            "id": account_id, "currency": account.get("currency"),
            "source_url": ("https://" + account["subdomain"] + ".amocrm.ru")
            if re.fullmatch(r"[a-z0-9-]+", str(account.get("subdomain", ""))) else None,
        })

    async def pull(self, kind, max_pages=20):
        cursor = await self.store.meta("cursor_" + kind, 0)
        progress = await self.store.meta("progress_" + kind)
        if progress is None:
            last_full = await self.store.meta("full_" + kind, 0)
            start = 0 if int(self.clock()) - last_full >= 86400 else cursor
            progress = {"page": 1, "start": start, "end": int(self.clock())}
        for _ in range(max_pages):
            await self.renew()
            rows, more = await self.remote.page(
                kind, progress["page"], progress["start"], progress["end"],
            )
            for item in rows:
                if kind == "leads":
                    item = RemoteLead.model_validate(item).model_dump()
                if not isinstance(item, dict) or not isinstance(item.get("id"), int):
                    raise ValueError("invalid_entity")
                await self.store.upsert(kind, item, int(self.clock()))
            if not more:
                await self.store.set_meta("cursor_" + kind, progress["end"])
                await self.store.set_meta("progress_" + kind, None)
                await self.store.set_meta("checked_" + kind, int(self.clock()))
                if progress["start"] == 0:
                    await self.store.set_meta("full_" + kind, int(self.clock()))
                return True
            if not rows:
                raise ValueError("empty_page_with_next")
            progress["page"] += 1
            await self.store.set_meta("progress_" + kind, progress)
        return False

    async def dispatch_one(self, operation):
        lead_id, op_id = operation["lead_id"], operation["id"]
        patch, base = json.loads(operation["patch"]), json.loads(operation["base"])
        await self.renew()
        current = await self.remote.lead(lead_id)
        await self.store.upsert("leads", current, int(self.clock()))
        if current.get("is_deleted"):
            await self.store.transition(op_id, operation["state"], "conflict", "remote_deleted")
            return
        if matches(current, patch):
            await self.store.transition(op_id, operation["state"], "applied", "verified_by_readback")
            return
        if operation["state"] == "uncertain":
            await self.store.transition(op_id, "uncertain", "conflict", "ambiguous_write_review_required")
            return
        if baseline(current) != base:
            await self.store.transition(op_id, "queued", "conflict", "remote_changed")
            return
        await self.renew()
        if not await self.store.transition(op_id, "queued", "sending"):
            return
        try:
            await self.remote.patch(lead_id, patch)
            actual = await self.remote.lead(lead_id)
            await self.store.upsert("leads", actual, int(self.clock()))
            state = "applied" if matches(actual, patch) else "conflict"
            await self.store.state(op_id, state, "verified_by_readback" if state == "applied"
                                   else "readback_mismatch")
        except Exception:
            await self.store.state(op_id, "uncertain", "write_outcome_unknown")
            raise

    async def dispatch(self):
        failures = 0
        for operation in await self.store.due():
            if operation["state"] == "queued" and not self.can_dispatch():
                await self.store.transition(operation["id"], "queued", "queued",
                                            "quiet_hours_deferred")
                continue
            try:
                await self.dispatch_one(operation)
            except RemoteMissing:
                current = await self.store.operation(operation["id"])
                await self.store.transition(operation["id"], current["state"],
                                            "conflict", "remote_deleted")
            except Exception:
                failures += 1
                # Rotate failed pre-write reads without pretending delivery.
                await self.store.transition(operation["id"], "queued", "queued",
                                            "remote_read_unavailable")
        return failures

    async def run(self):
        if not await self.store.lease(self.token):
            return {"state": "busy"}
        try:
            await self.bind()
            await self.store.recover()
            failures = await self.dispatch() if self.writeback else 0
            completed = []
            for kind in ("pipelines", "users", "leads", "contacts", "tasks"):
                completed.append(await self.pull(kind))
            state = "ready" if all(completed) and not failures else "partial"
            result = {"state": state, "checked_at": int(self.clock()),
                      "outbox_errors": failures}
            await self.store.set_meta("sync", result)
            return result
        except Exception as exc:
            result = {"state": "unavailable", "error": type(exc).__name__,
                      "checked_at": int(self.clock())}
            await self.store.set_meta("sync", result)
            return result
        finally:
            await self.store.release(self.token)
