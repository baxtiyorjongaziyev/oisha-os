"""Project the amoCRM mirror (PR #923 ``parallel_crm_entities``) into Twenty.

One-way, idempotent, resumable:
- every source record maps to exactly one Twenty record via ``twenty_sync_map``;
- unchanged records (same digest) are skipped;
- a per-kind id cursor is checkpointed after every record;
- unknown write outcomes are reconciled by ``amoId`` lookup, never re-posted blindly;
- deletions are NOT propagated (counted in the report for review).
"""
from __future__ import annotations

import json
import logging

from . import builders
from .client import TwentyError, TwentyUncertain
from .mapping import digest

logger = logging.getLogger(__name__)

KINDS = {  # mirror kind -> (map kind, Twenty plural, Twenty singular)
    "contacts": ("person", "people", "person"),
    "leads": ("opportunity", "opportunities", "opportunity"),
    "tasks": ("task", "tasks", "task"),
    "notes": ("note", "notes", "note"),
}
TARGETS = {"task": ("taskTargets", "taskTarget", "taskId"),
           "note": ("noteTargets", "noteTarget", "noteId")}


class Projector:
    def __init__(self, mirror, maps, client, *, stage_map: dict, member_map: dict,
                 batch: int = 200):
        self.mirror, self.maps, self.client = mirror, maps, client
        self.stage_map = {int(k): v for k, v in stage_map.items()}
        self.member_map = {int(k): v for k, v in member_map.items()}
        self.batch = batch
        self.report: dict = {}

    def _count(self, kind, key):
        bucket = self.report.setdefault(kind, {})
        bucket[key] = bucket.get(key, 0) + 1

    async def _rows_after(self, kind, cursor):
        rows = await self.mirror.sql(
            """SELECT id, payload FROM parallel_crm_entities WHERE kind=? AND id>?
            ORDER BY id LIMIT ?""", [kind, cursor, self.batch],
        )
        return [(r["id"], json.loads(r["payload"])) for r in rows]

    async def project_kind(self, kind: str, max_batches: int = 50) -> bool:
        """Returns True when a full pass finished (cursor reset)."""
        key = "twenty_cursor_" + kind
        cursor = await self.mirror.meta(key, 0)
        for _ in range(max_batches):
            rows = await self._rows_after(kind, cursor)
            if not rows:
                await self.mirror.set_meta(key, 0)
                return True
            for row_id, item in rows:
                await self.sync_one(kind, item)
                cursor = row_id
                await self.mirror.set_meta(key, cursor)
        return False

    async def _body(self, kind, item):
        if kind == "contacts":
            return builders.person(item)
        if kind == "leads":
            stage = self.stage_map.get(item.get("status_id"))
            if stage is None:
                return None, "unmapped_stage"
            contact = builders.first_contact_id(item)
            cmap = await self.maps.get("person", contact) if contact else None
            account = await self.mirror.meta("account", {}) or {}
            return builders.opportunity(
                item, stage=stage,
                owner_id=self.member_map.get(item.get("responsible_user_id")),
                contact_twenty_id=(cmap or {}).get("twenty_id"),
                currency=account.get("currency"))
        if kind == "tasks":
            return builders.task(item, assignee_id=self.member_map.get(
                item.get("responsible_user_id")))
        return builders.note(item)

    async def sync_one(self, kind: str, item: dict) -> str:
        map_kind, plural, singular = KINDS[kind]
        if item.get("is_deleted"):
            self._count(map_kind, "source_deleted_not_propagated")
            return "skipped"
        body = await self._body(kind, item)
        if isinstance(body, tuple):
            self._count(map_kind, body[1])
            return "skipped"
        if kind == "leads" and body.get("ownerId") is None:
            self._count(map_kind, "unmapped_owner")
        source_id, dig = item["id"], digest(body)
        current = await self.maps.get(map_kind, source_id)
        if current and current["state"] == "blocked":
            self._count(map_kind, "blocked")
            return "blocked"
        twenty_id = (current or {}).get("twenty_id")
        if current and current["state"] == "uncertain":
            found = await self._reconcile(plural, "amoId", source_id)
            if found is False:
                self._count(map_kind, "uncertain")
                return "uncertain"
            twenty_id = found or twenty_id
        elif current and current["state"] == "synced" and current["digest"] == dig:
            self._count(map_kind, "unchanged")
            return "unchanged"
        result = await self._write(map_kind, plural, singular, source_id, twenty_id, body, dig)
        if result == "synced":
            await self._link_target(kind, map_kind, item)
        return result

    async def _reconcile(self, plural, field, value):
        """Twenty id if the record exists, None if it does not, False if unknown."""
        literal = json.dumps(value) if isinstance(value, str) else value
        try:
            rows = await self.client.find(plural, f"{field}[eq]:{literal}")
        except TwentyError:
            return False
        if len(rows) > 1:
            logger.warning("twenty duplicate %s for %s=%s", plural, field, value)
            return False
        return rows[0]["id"] if rows else None

    async def _write(self, map_kind, plural, singular, source_id, twenty_id, body, dig,
                     system="amocrm"):
        await self.maps.put(map_kind, source_id, state="pending", system=system)
        try:
            if twenty_id:
                record = await self.client.update(plural, singular, twenty_id, body)
            else:
                record = await self.client.create(plural, singular, body)
        except TwentyUncertain as exc:
            await self.maps.fail(map_kind, source_id, str(exc), uncertain=True, system=system)
            self._count(map_kind, "uncertain")
            return "uncertain"
        except TwentyError as exc:
            state = await self.maps.fail(map_kind, source_id, str(exc), system=system)
            self._count(map_kind, state)
            return state
        await self.maps.put(map_kind, source_id, state="synced", twenty_id=record["id"],
                            dig=dig, system=system)
        self._count(map_kind, "updated" if twenty_id else "created")
        return "synced"

    async def _link_target(self, kind, map_kind, item):
        """Attach task/note to its opportunity or person exactly once."""
        if map_kind not in TARGETS or item.get("entity_type") not in ("leads", "contacts"):
            return
        target_kind = "opportunity" if item["entity_type"] == "leads" else "person"
        target = await self.maps.get(target_kind, item.get("entity_id"))
        own = await self.maps.get(map_kind, item["id"])
        if not target or not target.get("twenty_id") or not own:
            self._count(map_kind, "target_missing")
            return
        plural, singular, fk = TARGETS[map_kind]
        link_kind = singular
        link = await self.maps.get(link_kind, item["id"])
        if link and link["state"] == "synced":
            return
        field = "targetOpportunityId" if target_kind == "opportunity" else "targetPersonId"
        body = {fk: own["twenty_id"], field: target["twenty_id"]}
        if link and link["state"] == "uncertain":
            found = await self._reconcile(plural, fk, own["twenty_id"])
            if found is False:
                return
            if found:
                await self.maps.put(link_kind, item["id"], state="synced", twenty_id=found,
                                    dig=digest(body))
                return
        await self._write(link_kind, plural, singular, item["id"], None, body, digest(body))

    async def run(self) -> dict:
        self.report = {}
        await self.maps.recover_interrupted()
        complete = {}
        for kind in ("contacts", "leads", "tasks", "notes"):
            complete[kind] = await self.project_kind(kind)
        state = "ready" if all(complete.values()) else "partial"
        if await self.maps.problems(limit=1):
            state = "attention"
        return {"state": state, "complete": complete, "counts": self.report}
