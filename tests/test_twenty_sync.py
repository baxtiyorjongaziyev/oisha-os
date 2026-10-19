"""Synthetic acceptance tests for the amoCRM -> Twenty projection.

All data here is SYNTHETIC; no real customers, no network.
"""
import asyncio
import json
import sqlite3

import httpx
import pytest
from fastapi import HTTPException

from src.api.routes import twenty_calls
from src.services.core.crm.parallel.store import Store
from src.services.core.crm.twenty import builders
from src.services.core.crm.twenty.client import (
    TwentyClient, TwentyError, TwentyNotConfigured, TwentyUncertain,
)
from src.services.core.crm.twenty.mapping import MapStore
from src.services.core.crm.twenty.notes import pull_notes
from src.services.core.crm.twenty.projector import Projector
from src.services.core.crm.twenty.runner import reconcile


class SQLitePool:
    def __init__(self):
        self.conn = sqlite3.connect(":memory:", check_same_thread=False)
        self.conn.row_factory = sqlite3.Row

    async def execute(self, query, params=None):
        result = self.conn.execute(query, params or [])
        return [dict(r) for r in result.fetchall()] if result.description else []

    async def commit(self):
        self.conn.commit()


class FakeTwenty:
    """In-memory Twenty with failure injection."""
    def __init__(self):
        self.db: dict[str, dict[str, dict]] = {}
        self.seq = 0
        self.fail_next: list[Exception] = []
        self.apply_then_fail = False
        self.writes = 0

    def _maybe_fail(self):
        if self.fail_next:
            raise self.fail_next.pop(0)

    async def create(self, plural, singular, body):
        self._maybe_fail()
        self.seq += 1
        rid = f"t-{self.seq}"
        self.db.setdefault(plural, {})[rid] = dict(body, id=rid)
        self.writes += 1
        if self.apply_then_fail:
            self.apply_then_fail = False
            raise TwentyUncertain("twenty_write_timeout")
        return {"id": rid}

    async def update(self, plural, singular, rid, body):
        self._maybe_fail()
        self.db[plural][rid].update(body)
        self.writes += 1
        return {"id": rid}

    async def find(self, plural, flt, limit=2):
        self._maybe_fail()
        if flt.startswith("and("):
            return []
        field, _, value = flt.partition("[eq]:")
        value = json.loads(value)
        rows = self.db.get(plural, {}).values()
        if field == "phones.primaryPhoneNumber":
            return [r for r in rows if (r.get("phones") or {}).get("primaryPhoneNumber") == value]
        return [r for r in rows if r.get(field) == value]


def run(coro):
    return asyncio.run(coro)


async def setup(stage_map=None, member_map=None):
    pool = SQLitePool()
    mirror, maps = Store(pool), MapStore(pool)
    await mirror.init()
    await maps.init()
    await mirror.set_meta("account", {"id": 1, "currency": "UZS"})
    twenty = FakeTwenty()
    projector = Projector(mirror, maps, twenty,
                          stage_map=stage_map or {10: "NEW", 20: "MEETING"},
                          member_map=member_map or {7: "member-7"}, batch=2)
    return mirror, maps, twenty, projector


def contact(cid=1, name="SYNTHETIC Ali Valiyev", phone="+998 90 123 45 67"):
    return {"id": cid, "name": name, "responsible_user_id": 7, "custom_fields_values": [
        {"field_code": "PHONE", "values": [{"value": phone}]}]}


def lead(lid=101, status=10, owner=7, contact_id=1, **kw):
    return {"id": lid, "name": "SYNTHETIC deal", "status_id": status, "pipeline_id": 1,
            "responsible_user_id": owner, "updated_at": 1, "price": 5_000_000,
            "_embedded": {"contacts": [{"id": contact_id, "is_main": True}]}, **kw}


def task(tid=501, lead_id=101, done=False, text="SYNTHETIC qo'ng'iroq qilish"):
    return {"id": tid, "entity_type": "leads", "entity_id": lead_id, "text": text,
            "responsible_user_id": 7, "complete_till": 1_800_000_000, "is_completed": done}


async def seed(mirror, *items):
    for kind, item in items:
        await mirror.upsert(kind, item, 1)


# 1. Re-sync of the same source record never creates a duplicate.
def test_resync_creates_no_duplicates():
    async def go():
        mirror, maps, twenty, projector = await setup()
        await seed(mirror, ("contacts", contact()), ("leads", lead()), ("tasks", task()))
        first = await projector.run()
        writes = twenty.writes
        second = await projector.run()
        assert first["state"] == "ready" and second["state"] == "ready"
        assert len(twenty.db["people"]) == 1 and len(twenty.db["opportunities"]) == 1
        assert len(twenty.db["tasks"]) == 1 and len(twenty.db["taskTargets"]) == 1
        assert twenty.writes == writes  # unchanged digests => zero writes
        assert second["counts"]["opportunity"]["unchanged"] == 1
    run(go())


# 2. Contact, stage, seller and task updates propagate to the same records.
def test_updates_are_reflected():
    async def go():
        mirror, maps, twenty, projector = await setup(member_map={7: "m7", 8: "m8"})
        await seed(mirror, ("contacts", contact()), ("leads", lead()), ("tasks", task()))
        await projector.run()
        await seed(mirror, ("contacts", contact(name="SYNTHETIC Ali Karimov")),
                   ("leads", lead(status=20, owner=8)), ("tasks", task(done=True)))
        await projector.run()
        person = next(iter(twenty.db["people"].values()))
        opp = next(iter(twenty.db["opportunities"].values()))
        t = next(iter(twenty.db["tasks"].values()))
        assert person["name"]["lastName"] == "Ali Karimov"
        assert opp["stage"] == "MEETING" and opp["ownerId"] == "m8"
        assert opp["pointOfContactId"] == person["id"]
        assert opp["amount"] == {"amountMicros": 5_000_000_000_000, "currencyCode": "UZS"}
        assert t["status"] == "DONE" and len(twenty.db["tasks"]) == 1
    run(go())


def test_unmapped_stage_and_owner_are_reported_not_guessed():
    async def go():
        mirror, maps, twenty, projector = await setup()
        await seed(mirror, ("leads", lead(lid=1, status=999)), ("leads", lead(lid=2, owner=55)))
        report = await projector.run()
        assert report["counts"]["opportunity"]["unmapped_stage"] == 1
        assert report["counts"]["opportunity"]["unmapped_owner"] == 1
        opp = next(iter(twenty.db["opportunities"].values()))
        assert opp["ownerId"] is None
    run(go())


# 4. Errors never lose data or report success; uncertain writes are reconciled.
def test_definite_failure_is_retried_later_not_marked_synced():
    async def go():
        mirror, maps, twenty, projector = await setup()
        await seed(mirror, ("contacts", contact()))
        twenty.fail_next = [TwentyError("twenty_http_400")]
        report = await projector.run()
        assert report["state"] == "attention"
        assert (await maps.get("person", 1))["state"] == "failed"
        report = await projector.run()
        assert (await maps.get("person", 1))["state"] == "synced"
        assert len(twenty.db["people"]) == 1
    run(go())


def test_uncertain_write_is_reconciled_without_duplicate():
    async def go():
        mirror, maps, twenty, projector = await setup()
        await seed(mirror, ("contacts", contact()))
        twenty.apply_then_fail = True  # server applied the create, client saw timeout
        await projector.run()
        assert (await maps.get("person", 1))["state"] == "uncertain"
        await projector.run()
        row = await maps.get("person", 1)
        assert row["state"] == "synced" and len(twenty.db["people"]) == 1
        assert row["twenty_id"] == next(iter(twenty.db["people"]))
    run(go())


def test_uncertain_stays_uncertain_when_lookup_fails():
    async def go():
        mirror, maps, twenty, projector = await setup()
        await seed(mirror, ("contacts", contact()))
        twenty.apply_then_fail = True
        await projector.run()
        twenty.fail_next = [TwentyError("twenty_read_failed")]
        await projector.run()
        assert (await maps.get("person", 1))["state"] == "uncertain"
        assert len(twenty.db["people"]) == 1
    run(go())


def test_retry_limit_blocks_for_operator_review():
    async def go():
        mirror, maps, twenty, projector = await setup()
        await seed(mirror, ("contacts", contact()))
        for _ in range(5):
            twenty.fail_next = [TwentyError("twenty_http_400")]
            await projector.run()
        assert (await maps.get("person", 1))["state"] == "blocked"
        assert await projector.sync_one("contacts", contact()) == "blocked"
    run(go())


# 5. An interrupted migration resumes from the checkpoint.
def test_interrupted_pass_resumes_from_checkpoint():
    async def go():
        mirror, maps, twenty, projector = await setup()
        await seed(mirror, *[("contacts", contact(cid=i, phone=f"90123450{i}")) for i in range(1, 6)])
        assert await projector.project_kind("contacts", max_batches=1) is False
        assert await mirror.meta("twenty_cursor_contacts") == 2
        assert len(twenty.db["people"]) == 2
        await maps.put("person", 3, state="pending")  # simulated crash mid-write
        await maps.recover_interrupted()
        assert (await maps.get("person", 3))["state"] == "uncertain"
        assert await projector.project_kind("contacts") is True
        assert len(twenty.db["people"]) == 5
        assert await mirror.meta("twenty_cursor_contacts") == 0
    run(go())


def test_deletions_are_not_propagated():
    async def go():
        mirror, maps, twenty, projector = await setup()
        await seed(mirror, ("contacts", contact()), ("leads", lead()))
        await projector.run()
        await seed(mirror, ("leads", lead(is_deleted=True)))
        report = await projector.run()
        assert report["counts"]["opportunity"]["source_deleted_not_propagated"] == 1
        assert len(twenty.db["opportunities"]) == 1
    run(go())


# 7. Source and target counts are reconciled and gaps are explicit.
def test_reconcile_reports_gaps():
    async def go():
        mirror, maps, twenty, projector = await setup()
        await seed(mirror, ("contacts", contact(cid=1)), ("contacts", contact(cid=2)))
        twenty.fail_next = [TwentyError("twenty_http_400")]
        await projector.run()
        report = await reconcile(mirror, maps)
        assert report["contacts"]["source"] == 2
        assert report["contacts"]["target_synced"] == 1
        assert report["contacts"]["gap"] == 1
        assert report["problems"][0]["state"] == "failed"
    run(go())


# Defect 5: notes history is read across ALL pages, with checkpoint.
class NotesRemote:
    def __init__(self, pages, fail_on=None):
        self.pages, self.fail_on, self.calls = pages, fail_on, []

    async def request(self, method, path, params):
        self.calls.append(params["page"])
        if params["page"] == self.fail_on:
            self.fail_on = None
            raise RuntimeError("network")
        rows = self.pages[params["page"] - 1]
        more = params["page"] < len(self.pages)
        return {"_embedded": {"notes": rows}, "_links": {"next": {"href": "x"}} if more else {}}


def test_notes_pull_reads_all_pages_and_resumes():
    async def go():
        mirror, maps, twenty, projector = await setup()
        pages = [[{"id": i * 10 + j, "entity_id": 101, "note_type": "common",
                   "params": {"text": "SYNTHETIC"}} for j in range(3)] for i in range(3)]
        remote = NotesRemote(pages, fail_on=2)
        with pytest.raises(RuntimeError):
            await pull_notes(mirror, remote)
        assert await mirror.meta("progress_notes") is None or \
            (await mirror.meta("progress_notes"))["page"] == 2
        assert await pull_notes(mirror, remote) is True
        rows = await mirror.sql("SELECT COUNT(*) AS n FROM parallel_crm_entities WHERE kind='notes'")
        assert rows[0]["n"] == 9
        assert remote.calls == [1, 2, 2, 3]
    run(go())


def test_notes_and_targets_are_deduplicated():
    async def go():
        mirror, maps, twenty, projector = await setup()
        await seed(mirror, ("contacts", contact()), ("leads", lead()),
                   ("notes", {"id": 9, "entity_type": "leads", "entity_id": 101,
                              "note_type": "call_in", "params": {"text": "SYNTHETIC", "duration": 75}}))
        await projector.run()
        await projector.run()
        assert len(twenty.db["notes"]) == 1 and len(twenty.db["noteTargets"]) == 1
        note = next(iter(twenty.db["notes"].values()))
        assert note["title"] == "Kiruvchi qo'ng'iroq" and "1 daq 15 son" in note["bodyV2"]["markdown"]
    run(go())


# 3. + defects 1-3: call webhook.
def event(**kw):
    return twenty_calls.CallEvent(**{"call_id": "SYN-1", "phone": "+998901234567",
                                     "direction": "in", "duration": 61, **kw})


def test_call_webhook_retry_does_not_duplicate():
    async def go():
        _, maps, twenty, _ = await setup()
        twenty.db["people"] = {"p1": {"id": "p1", "phones": {"primaryPhoneNumber": "901234567"}}}
        first = await twenty_calls.record_call(event(), twenty, maps)
        second = await twenty_calls.record_call(event(), twenty, maps)
        assert first["status"] == "recorded" and first["linked"] is True
        assert second["status"] == "duplicate"
        assert len(twenty.db["notes"]) == 1
    run(go())


def test_call_webhook_failure_is_not_success_and_uncertain_reconciles():
    async def go():
        _, maps, twenty, _ = await setup()
        twenty.fail_next = [TwentyError("twenty_http_400")]
        with pytest.raises(TwentyError):
            await twenty_calls.record_call(event(), twenty, maps)
        assert (await maps.get("call", "SYN-1", "moizvonki"))["state"] == "failed"
        twenty.apply_then_fail = True
        with pytest.raises(TwentyUncertain):
            await twenty_calls.record_call(event(), twenty, maps)
        result = await twenty_calls.record_call(event(), twenty, maps)
        assert result["status"] == "recorded" and len(twenty.db["notes"]) == 1
        assert result["linked"] is False  # unknown caller: not guessed
    run(go())


def test_call_webhook_secret_fails_closed(monkeypatch):
    monkeypatch.delenv("TWENTY_CALLS_WEBHOOK_SECRET", raising=False)
    with pytest.raises(HTTPException) as exc:
        twenty_calls._check_secret("anything")
    assert exc.value.status_code == 503
    monkeypatch.setenv("TWENTY_CALLS_WEBHOOK_SECRET", "SYNTHETIC-secret")
    with pytest.raises(HTTPException) as exc:
        twenty_calls._check_secret("wrong")
    assert exc.value.status_code == 401
    twenty_calls._check_secret("SYNTHETIC-secret")


def test_client_requires_key_and_classifies_outcomes():
    with pytest.raises(TwentyNotConfigured):
        TwentyClient("https://x", "")
    seen = []

    def handler(request):
        seen.append(request.method)
        if request.method == "GET" and len(seen) == 1:
            return httpx.Response(503)
        if request.method == "GET":
            return httpx.Response(200, json={"data": {"people": []}})
        return httpx.Response(500)

    async def no_sleep(_):
        return None

    async def go():
        client = TwentyClient("https://x", "SYNTHETIC", transport=httpx.MockTransport(handler),
                              sleep=no_sleep)
        assert await client.find("people", "") == []          # read retried after 503
        with pytest.raises(TwentyUncertain):                   # write 500 => uncertain, no retry
            await client.create("people", "person", {})
        await client.aclose()
    run(go())
    assert seen == ["GET", "GET", "POST"]


def test_phone_normalization():
    assert builders.normalize_phone("+998 (90) 123-45-67") == "901234567"
    assert builders.normalize_phone("901234567") == "901234567"
    assert builders.normalize_phone("12345") is None
