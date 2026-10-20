"""Synthetic fixtures only; no customer data or live amoCRM calls."""
import asyncio
import copy
import sqlite3
from uuid import uuid4

import pytest

from src.services.core.crm.parallel.schema import RemoteLead, baseline, revision
from src.services.core.crm.parallel.store import Store
from src.services.core.crm.parallel.sync import Sync


@pytest.fixture(autouse=True)
def synthetic_daytime(monkeypatch):
    monkeypatch.setattr("src.services.core.crm.parallel.sync.is_quiet_hours", lambda: False)


class SQLitePool:
    """Test-only adapter matching DatabasePool's execute/commit contract."""
    def __init__(self, path=":memory:"):
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row

    async def execute(self, query, params=None):
        result = self.conn.execute(query, params or [])
        return [dict(row) for row in result.fetchall()] if result.description else []

    async def commit(self):
        self.conn.commit()


def lead(entity_id=101, **changes):
    return RemoteLead.model_validate({
        "id": entity_id, "name": "SYNTHETIC QA lead", "updated_at": 100,
        "pipeline_id": 1, "status_id": 10, "responsible_user_id": 7,
        **changes,
    }).model_dump()


class FakeRemote:
    def __init__(self):
        self.item = lead()
        self.patches = []
        self.pages = {}
        self.calls = []
        self.account_id = 42
        self.fail_after_patch = False
        self.failed_kind = None

    async def account(self):
        return {"id": self.account_id, "currency": "UZS", "subdomain": "synthetic-qa"}

    async def lead(self, lead_id):
        return copy.deepcopy(self.item)

    async def page(self, kind, page, start, end):
        self.calls.append((kind, page, start, end))
        if kind == self.failed_kind:
            raise RuntimeError("synthetic network failure")
        return self.pages.get((kind, page), ([], False))

    async def patch(self, lead_id, patch):
        self.patches.append((lead_id, copy.deepcopy(patch)))
        self.item.update(patch)
        self.item["updated_at"] += 1
        if self.fail_after_patch:
            raise TimeoutError("synthetic ambiguous outcome")

    async def notes(self, lead_id):
        return [{"id": 3, "text": "SYNTHETIC QA note"}]


@pytest.fixture
def store():
    pool = SQLitePool()
    result = Store(pool)
    asyncio.run(result.init())
    yield result
    pool.conn.close()


async def queue(store, remote, patch=None):
    await store.upsert("leads", remote.item, 100)
    return await store.enqueue(str(uuid4()), 101, "synthetic-owner",
                               baseline(remote.item), patch or {"name": "SYNTHETIC renamed"})


@pytest.mark.asyncio
async def test_import_paginates_and_upserts_without_duplicates(store):
    remote = FakeRemote()
    remote.pages = {("leads", 1): ([lead()], True),
                    ("leads", 2): ([lead(102)], False)}
    sync = Sync(store, remote, clock=lambda: 200)
    assert (await sync.run())["state"] == "ready"
    assert await store.meta("cursor_leads") == 200
    assert (await store.entities("leads"))[1] == 2
    await sync.run()
    assert (await store.entities("leads"))[1] == 2
    assert [c[1] for c in remote.calls if c[0] == "leads"] == [1, 2, 1, 2]


@pytest.mark.asyncio
async def test_bounded_pull_resumes_page_and_keeps_checkpoint(store):
    remote = FakeRemote()
    remote.pages = {("leads", 1): ([lead()], True),
                    ("leads", 2): ([lead(102)], False)}
    sync = Sync(store, remote, clock=lambda: 200)
    assert await sync.pull("leads", max_pages=1) is False
    assert await store.meta("cursor_leads") is None
    assert (await store.meta("progress_leads"))["page"] == 2
    assert await sync.pull("leads") is True
    assert await store.meta("cursor_leads") == 200
    assert remote.calls[-1][1:] == (2, 0, 200)


@pytest.mark.asyncio
async def test_failure_does_not_advance_entity_watermark(store):
    remote = FakeRemote()
    await store.set_meta("cursor_leads", 80)
    remote.failed_kind = "leads"
    assert (await Sync(store, remote).run())["state"] == "unavailable"
    assert await store.meta("cursor_leads") == 80
    assert await store.meta("checked_leads") is None


@pytest.mark.asyncio
async def test_write_verified_and_journal_survives_repeated_sync(store):
    remote = FakeRemote()
    op = await queue(store, remote)
    sync = Sync(store, remote, writeback=True)
    await sync.run()
    assert (await store.operation(op["id"]))["state"] == "applied"
    assert len(remote.patches) == 1
    await sync.run()
    assert len(remote.patches) == 1
    audit = await store.sql("SELECT state FROM parallel_crm_audit WHERE operation_id=? ORDER BY seq", [op["id"]])
    assert [r["state"] for r in audit] == ["queued", "sending", "applied"]


@pytest.mark.asyncio
async def test_conflicting_remote_change_is_never_overwritten(store):
    remote = FakeRemote()
    op = await queue(store, remote)
    remote.item["responsible_user_id"] = 8
    await Sync(store, remote, writeback=True).run()
    assert not remote.patches
    assert (await store.operation(op["id"]))["reason"] == "remote_changed"


@pytest.mark.asyncio
async def test_timeout_after_success_is_read_back_without_resending(store):
    remote = FakeRemote()
    op = await queue(store, remote)
    remote.fail_after_patch = True
    sync = Sync(store, remote, writeback=True)
    result = await sync.run()
    assert result["state"] == "partial"
    assert result["outbox_errors"] == 1
    assert any(call[0] == "leads" for call in remote.calls)
    assert (await store.operation(op["id"]))["state"] == "uncertain"
    remote.fail_after_patch = False
    await sync.run()
    assert (await store.operation(op["id"]))["state"] == "applied"
    assert len(remote.patches) == 1


@pytest.mark.asyncio
async def test_restart_marks_interrupted_edit_for_read_only_review(store):
    remote = FakeRemote()
    op = await queue(store, remote)
    await store.state(op["id"], "sending")
    await Sync(store, remote, writeback=True).run()
    assert (await store.operation(op["id"]))["state"] == "conflict"
    assert not remote.patches


@pytest.mark.asyncio
async def test_read_only_mode_never_dispatches(store):
    remote = FakeRemote()
    op = await queue(store, remote)
    await Sync(store, remote, writeback=False).run()
    assert not remote.patches
    assert (await store.operation(op["id"]))["state"] == "queued"


@pytest.mark.asyncio
async def test_another_worker_cannot_acquire_active_lease(store):
    assert await store.lease("worker-a")
    assert not await store.lease("worker-b")
    assert await store.lease("worker-a")
    assert (await Sync(store, FakeRemote(), writeback=True).run())["state"] == "busy"


@pytest.mark.asyncio
async def test_cancel_between_read_and_write_prevents_remote_patch(store):
    remote = FakeRemote()
    op = await queue(store, remote)
    original = remote.lead

    async def read_and_cancel(entity_id):
        current = await original(entity_id)
        await store.discard(op["id"])
        return current

    remote.lead = read_and_cancel
    await Sync(store, remote, writeback=True).run()
    assert not remote.patches
    assert (await store.operation(op["id"]))["state"] == "discarded"


@pytest.mark.asyncio
async def test_account_switch_blocks_outbound_and_inbound(store):
    remote = FakeRemote()
    await store.set_meta("account", {"id": 999})
    op = await queue(store, remote)
    result = await Sync(store, remote, writeback=True).run()
    assert result["state"] == "unavailable"
    assert not remote.patches and not remote.calls
    assert (await store.operation(op["id"]))["state"] == "queued"


@pytest.mark.asyncio
async def test_only_one_active_edit_per_lead(store):
    remote = FakeRemote()
    op = await queue(store, remote)
    with pytest.raises(sqlite3.IntegrityError):
        await queue(store, remote)
    await store.discard(op["id"])
    assert (await queue(store, remote))["state"] == "queued"


@pytest.mark.asyncio
async def test_search_escapes_wildcards_and_scopes_seller(store):
    await store.upsert("leads", lead(name="SYNTHETIC 100%"), 100)
    await store.upsert("leads", lead(102, name="SYNTHETIC other", responsible_user_id=8), 100)
    rows, count = await store.entities("leads", query="%")
    assert count == 1 and rows[0]["id"] == 101
    rows, count = await store.entities("leads", owner=8)
    assert count == 1 and rows[0]["id"] == 102


@pytest.mark.asyncio
async def test_contacts_and_tasks_are_mirrored_with_independent_checkpoints(store):
    remote = FakeRemote()
    remote.pages = {
        ("contacts", 1): ([{"id": 15, "name": "SYNTHETIC contact"}], False),
        ("tasks", 1): ([{"id": 17, "entity_id": 101, "entity_type": "leads",
                         "text": "SYNTHETIC call", "complete_till": 300}], False),
    }
    await Sync(store, remote, clock=lambda: 200).run()
    assert (await store.get("contacts", 15))["name"] == "SYNTHETIC contact"
    assert (await store.tasks_for(101))[0]["id"] == 17
    assert await store.meta("cursor_contacts") == 200
    assert await store.meta("cursor_tasks") == 200


@pytest.mark.asyncio
async def test_remote_http_error_is_not_empty_success():
    from types import SimpleNamespace
    from src.services.core.crm.parallel.remote import AmoRemote, RemoteUnavailable

    class Client:
        base_url = "https://synthetic-qa.amocrm.ru"
        async def _request_with_auth(self, *args, **kwargs):
            return SimpleNamespace(status_code=503)
    with pytest.raises(RemoteUnavailable):
        await AmoRemote(Client()).page("leads", 1, 0, 200)


def test_api_authorization_idempotency_and_csrf(store, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from src.api import security
    from src.api.rbac import Principal, Role
    from src.api.routes import parallel_crm as api

    current = [Principal("seller-a", Role.SELLER, "test")]
    monkeypatch.setattr(security, "authorize_connection", lambda request: current[0])
    monkeypatch.setenv("OISHA_CRM_SELLER_MAP_JSON", '{"seller-a":7}')
    monkeypatch.setenv("OISHA_CRM_PARALLEL_ENABLED", "1")
    monkeypatch.setenv("OISHA_CRM_PARALLEL_WRITEBACK", "1")

    async def get_store():
        return store
    monkeypatch.setattr(api.runtime, "get_store", get_store)
    monkeypatch.setattr(api.runtime, "wake", lambda: None)
    remote = FakeRemote()
    monkeypatch.setattr(api.runtime, "get_remote", lambda: remote)
    asyncio.run(store.upsert("leads", lead(), 100))
    asyncio.run(store.upsert("leads", lead(102, responsible_user_id=8), 100))
    app = FastAPI()
    app.include_router(api.router)
    client = TestClient(app)
    path = "/api/crm/parallel"
    assert [r["id"] for r in client.get(path+"/snapshot").json()["leads"]] == [101]
    assert client.get(path+"/leads/102").status_code == 404
    body = {"request_id": str(uuid4()), "revision": revision(lead()),
            "patch": {"name": "SYNTHETIC renamed"}}
    assert client.patch(path+"/leads/101", json=body).status_code == 403
    headers = {"Origin": "http://testserver", "X-Oisha-CRM": "1"}
    assert client.patch(path+"/leads/101", json=body, headers={**headers, "Origin": "https://evil.test"}).status_code == 403
    first = client.patch(path+"/leads/101", json=body, headers=headers)
    assert first.status_code == 202, first.text
    assert client.patch(path+"/leads/101", json=body, headers=headers).json() == first.json()
    assert client.patch(path+"/leads/102", json=body, headers=headers).status_code == 404
    assert client.post(path+"/sync", headers=headers).status_code == 403
    current[0] = Principal("unmapped", Role.SELLER, "test")
    assert client.get(path+"/snapshot").status_code == 403
    current[0] = Principal("targetolog", Role.TARGETOLOG, "test")
    assert client.patch(path+"/leads/101", json=body, headers=headers).status_code == 403
    current[0] = None
    assert client.get(path+"/snapshot").status_code == 401


@pytest.mark.parametrize("patch", [{}, {"name": None}, {"name": " "}, {"status_id": 0},
                                    {"price": 1}, {"responsible_user_id": 8}])
def test_patch_rejects_unsupported_or_invalid_changes(patch):
    from pydantic import ValidationError
    from src.services.core.crm.parallel.schema import LeadPatch
    with pytest.raises(ValidationError):
        LeadPatch.model_validate(patch)


@pytest.mark.asyncio
async def test_missing_lead_does_not_starve_other_writes_or_inbound_pull(store):
    from src.services.core.crm.parallel.remote import RemoteMissing
    remote = FakeRemote()
    op = await queue(store, remote)

    async def missing(entity_id):
        raise RemoteMissing("synthetic deleted lead")
    remote.lead = missing
    result = await Sync(store, remote, writeback=True).run()
    assert result["state"] == "ready"
    assert remote.calls
    assert (await store.operation(op["id"]))["state"] == "conflict"
    assert (await store.operation(op["id"]))["reason"] == "remote_deleted"
    assert not remote.patches


@pytest.mark.asyncio
async def test_update_during_page_scan_does_not_drop_unchanged_lead(store):
    from types import SimpleNamespace
    from src.services.core.crm.parallel.remote import AmoRemote
    items = [lead(i) for i in range(1, 502)]

    class Client:
        base_url = "https://synthetic-qa.amocrm.ru"
        async def _request_with_auth(self, fn, url, **kwargs):
            params = kwargs["params"]
            assert params.get("order[id]") == "asc"
            lower = params["filter[updated_at][from]"]
            upper = params.get("filter[updated_at][to]", float("inf"))
            eligible = [row for row in items if lower <= row["updated_at"] <= upper]
            page = params["page"]
            rows = copy.deepcopy(eligible[(page-1)*250:page*250])
            data = {"_embedded": {"leads": rows}, "_links": {}}
            if page*250 < len(eligible):
                data["_links"]["next"] = {"href": "synthetic"}
            if page == 1:
                # Would leave the old fixed-upper-bound result set and shift page 2.
                items[0]["updated_at"] = 201
            return SimpleNamespace(status_code=200, json=lambda: data)

    await Sync(store, AmoRemote(Client()), clock=lambda: 200).pull("leads")
    assert (await store.entities("leads", limit=1000))[1] == 501
    assert await store.get("leads", 251)
    assert await store.meta("cursor_leads") == 200


@pytest.mark.asyncio
async def test_daily_full_reconciliation_revisits_old_records(store):
    remote = FakeRemote()
    await store.set_meta("cursor_leads", 200)
    await store.set_meta("full_leads", 200)
    await Sync(store, remote, clock=lambda: 90000).pull("leads")
    assert remote.calls[0][2] == 0
    assert await store.meta("full_leads") == 90000


@pytest.mark.asyncio
async def test_open_tasks_are_not_hidden_by_completed_history(store):
    for entity_id in range(1, 102):
        await store.upsert("tasks", {
            "id": entity_id, "entity_id": 101, "entity_type": "leads",
            "text": "SYNTHETIC task", "is_completed": entity_id != 101,
            "complete_till": entity_id,
        }, 100)
    tasks = await store.tasks_for(101)
    assert len(tasks) == 100
    assert tasks[0]["id"] == 101
    assert tasks[0]["is_completed"] is False
    assert await store.task_count(101) == 101


@pytest.mark.asyncio
async def test_quiet_hours_defer_writes_but_allow_inbound_sync(store):
    remote = FakeRemote()
    op = await queue(store, remote)
    result = await Sync(store, remote, writeback=True, can_dispatch=lambda: False).run()
    assert result["state"] == "ready"
    assert remote.calls and not remote.patches
    actual = await store.operation(op["id"])
    assert actual["state"] == "queued"
    assert actual["reason"] == "quiet_hours_deferred"
