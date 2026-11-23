import asyncio
import sqlite3

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.routes import task_registry_routes as routes
from src.services.core.task_registry import TaskRegistry, TaskRegistryError


def _sqlite_executor():
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row

    async def execute(query, params=None):
        cur = conn.execute(query, params or [])
        conn.commit()
        return cur.fetchall()

    return execute


@pytest.fixture
def registry():
    return TaskRegistry(_sqlite_executor())


def run(coro):
    return asyncio.run(coro)


def test_create_is_idempotent(registry):
    a = run(registry.create(title="Uchrashuv", owner="oisha", created_by="mrjon", idempotency_key="k1"))
    b = run(registry.create(title="Uchrashuv", owner="oisha", created_by="mrjon", idempotency_key="k1"))
    assert a["id"] == b["id"]
    assert len(run(registry.list())) == 1


def test_unknown_owner_rejected(registry):
    with pytest.raises(TaskRegistryError):
        run(registry.create(title="x", owner="hermes", created_by="oisha"))


def test_only_owner_can_claim_and_only_once(registry):
    t = run(registry.create(title="x", owner="amina", created_by="oisha"))
    with pytest.raises(TaskRegistryError, match="not_owner"):
        run(registry.claim(t["id"], "oisha"))
    assert run(registry.claim(t["id"], "amina"))["status"] == "in_progress"
    with pytest.raises(TaskRegistryError, match="bad_state"):
        run(registry.claim(t["id"], "amina"))


def test_complete_requires_evidence(registry):
    t = run(registry.create(title="x", owner="oisha", created_by="oisha"))
    run(registry.claim(t["id"], "oisha"))
    with pytest.raises(TaskRegistryError, match="evidence_required"):
        run(registry.complete(t["id"], "oisha", {}))
    done = run(registry.complete(t["id"], "oisha", {"calendar_event_id": "abc"}))
    assert done["status"] == "done"
    assert done["evidence"] == {"calendar_event_id": "abc"}


def test_fail_records_error(registry):
    t = run(registry.create(title="x", owner="oisha", created_by="oisha"))
    run(registry.claim(t["id"], "oisha"))
    assert run(registry.fail(t["id"], "oisha", "calendar 403"))["error"] == "calendar 403"


def test_reassign_moves_owner(registry):
    t = run(registry.create(title="x", owner="mrjon", created_by="mrjon"))
    moved = run(registry.reassign(t["id"], "mrjon", "oisha"))
    assert moved["owner"] == "oisha"
    with pytest.raises(TaskRegistryError, match="not_owner"):
        run(registry.reassign(t["id"], "mrjon", "amina"))


def test_list_filters(registry):
    run(registry.create(title="a", owner="oisha", created_by="oisha"))
    run(registry.create(title="b", owner="amina", created_by="oisha"))
    assert [t["title"] for t in run(registry.list(owner="amina"))] == ["b"]


@pytest.fixture
def client(monkeypatch, registry):
    monkeypatch.setenv("TASK_REGISTRY_TOKENS", "oisha:tok-o,amina:tok-a")
    monkeypatch.setattr(routes, "get_registry", lambda: registry)
    app = FastAPI()
    app.include_router(routes.router)
    return TestClient(app)


def test_api_fail_closed_without_tokens(monkeypatch):
    monkeypatch.delenv("TASK_REGISTRY_TOKENS", raising=False)
    app = FastAPI()
    app.include_router(routes.router)
    assert TestClient(app).get("/api/tasks").status_code == 503


def test_api_rejects_bad_token(client):
    assert client.get("/api/tasks", headers={"Authorization": "Bearer nope"}).status_code == 401


def test_api_flow_identity_from_token(client):
    o = {"Authorization": "Bearer tok-o"}
    a = {"Authorization": "Bearer tok-a"}
    t = client.post("/api/tasks", json={"title": "Coach", "owner": "amina"}, headers=o).json()
    assert t["created_by"] == "oisha"
    assert client.post(f"/api/tasks/{t['id']}/claim", headers=o).status_code == 409
    assert client.post(f"/api/tasks/{t['id']}/claim", headers=a).json()["status"] == "in_progress"
    r = client.post(f"/api/tasks/{t['id']}/complete", json={"evidence": {"msg_id": 5}}, headers=a)
    assert r.json()["status"] == "done"
    assert client.get("/api/tasks/missing", headers=a).status_code == 404


def test_production_app_allows_task_registry_tokens_through_security_middleware(monkeypatch, registry):
    from src.api_server import app

    monkeypatch.setenv("TASK_REGISTRY_TOKENS", "oisha:tok-o,amina:tok-a")
    monkeypatch.setattr(routes, "get_registry", lambda: registry)
    prod_client = TestClient(app)
    assert prod_client.get("/api/tasks").status_code == 401
    assert prod_client.get("/api/tasks", headers={"Authorization": "Bearer wrong"}).status_code == 401
    res = prod_client.post(
        "/api/tasks",
        json={"title": "Handoff", "owner": "amina"},
        headers={"Authorization": "Bearer tok-o"},
    )
    assert res.status_code == 200
    assert res.json()["created_by"] == "oisha"
    list_res = prod_client.get("/api/tasks", headers={"Authorization": "Bearer tok-a"})
    assert list_res.status_code == 200
    assert len(list_res.json()) == 1
