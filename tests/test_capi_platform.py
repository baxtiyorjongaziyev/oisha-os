"""Synthetic CAPI payloads, isolated SQLite and mocked Meta; no live delivery."""
import asyncio
import json
import sqlite3
import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from src.api.routes import capi_platform as routes
from src.services.core.marketing import capi_platform as platform
from src.services.core.marketing import capi_platform_store as store
from src.services.core.marketing.capi_platform_schema import Conversion


class Pool:
    def __init__(self):
        self.conn = sqlite3.connect(":memory:", check_same_thread=False)
        self.conn.row_factory = sqlite3.Row

    async def execute(self, query, params=None):
        return [dict(row) for row in self.conn.execute(query, params or []).fetchall()]

    async def commit(self):
        self.conn.commit()


@pytest.fixture
def isolated(monkeypatch):
    pool = Pool()
    monkeypatch.setattr(store, "_pool", lambda: pool)
    cfg = dict(enabled=True, dataset_id="synthetic-dataset", token="synthetic-token",
               test_code="TEST_SYNTHETIC", version="v21.0")
    monkeypatch.setattr(platform.meta_capi, "_config", lambda: dict(cfg))
    return pool, cfg


def payload(**changes):
    result = dict(source="website", event_name="Lead", event_id="synthetic-lead-1",
                  event_time=int(time.time()), event_source_url="https://example.test/contact",
                  client_user_agent="SyntheticTest/1", email="synthetic@example.test", consent=True)
    result.update(changes)
    return result


@pytest.mark.parametrize("changes", [
    {"consent": False}, {"event_time": 1}, {"event_time": int(time.time()) + 1000},
    {"event_source_url": "http://example.test"}, {"event_source_url": "https://example.test/?email=x"},
    {"client_user_agent": ""}, {"email": ""}, {"event_name": "Purchase"},
    {"event_name": "Purchase", "value": float("nan"), "currency": "UZS"},
    {"source": "crm", "leadgen_id": "123", "event_id": "wrong"},
])
def test_invalid_event_rejected(changes):
    with pytest.raises(ValidationError):
        Conversion(**payload(**changes))


def test_payload_hashes_and_website_semantics():
    event = Conversion(**payload()).meta_event()
    assert event["action_source"] == "website"
    assert event["event_id"] == "synthetic-lead-1"
    assert "synthetic@example.test" not in json.dumps(event)
    assert len(event["user_data"]["em"][0]) == 64


def test_queue_duplicate_and_acceptance(isolated, monkeypatch):
    calls = []
    def post(cfg, event):
        calls.append(event)
        return {"ok": True, "response": {"events_received": 1}}
    monkeypatch.setattr(platform.meta_capi, "_post_events", post)
    async def scenario():
        event = Conversion(**payload())
        assert (await platform.accept(event))["status"] == "queued"
        assert (await platform.accept(event))["status"] == "duplicate"
        assert len(await platform.dispatch_due()) == 1
        assert await platform.dispatch_due() == []
        rows = await store.events()
        assert rows[0]["status"] == "sent" and rows[0]["error"] == ""
        assert "payload" not in rows[0]
    asyncio.run(scenario())
    assert len(calls) == 1


def test_unconfirmed_response_and_retry_keeps_id(isolated, monkeypatch):
    pool, _ = isolated
    sent = []
    def post(cfg, event):
        sent.append(event)
        return {"ok": True, "response": {"events_received": 0 if len(sent) == 1 else 1}}
    monkeypatch.setattr(platform.meta_capi, "_post_events", post)
    async def scenario():
        await platform.accept(Conversion(**payload()))
        assert (await platform.dispatch_due())[0]["status"] == "failed"
        assert await platform.dispatch_due() == []
        await pool.execute("UPDATE capi_platform_events SET next_attempt_at='2000'")
        assert (await platform.dispatch_due())[0]["status"] == "sent"
        assert sent[0] == sent[1]
    asyncio.run(scenario())


def test_mode_dataset_isolation_and_disabled(isolated, monkeypatch):
    _, cfg = isolated
    monkeypatch.setattr(platform.meta_capi, "_post_events", lambda *_: pytest.fail("No delivery allowed"))
    async def scenario():
        await platform.accept(Conversion(**payload()))
        cfg["test_code"] = ""
        assert await platform.dispatch_due() == []
        cfg["test_code"] = "TEST_SYNTHETIC"
        cfg["dataset_id"] = "different-dataset"
        assert await platform.dispatch_due() == []
        cfg["dataset_id"] = "synthetic-dataset"
        cfg["enabled"] = False
        assert (await platform.dispatch_due())[0]["status"] == "disabled"
        assert (await store.events())[0]["attempts"] == 0
    asyncio.run(scenario())


def test_atomic_lease_stale_result_cannot_overwrite(isolated):
    pool, cfg = isolated
    async def scenario():
        await platform.accept(Conversion(**payload()))
        key = ("synthetic-lead-1", "Lead", cfg["dataset_id"], "test")
        first = await store.claim(*key)
        assert await store.claim(*key) is None
        await pool.execute("UPDATE capi_platform_events SET updated_at='2000'")
        second = await store.claim(*key)
        await store.finish(key, second[0], True, "", 2)
        await store.finish(key, first[0], False, "HTTP 500", 1)
        assert (await store.events())[0]["status"] == "sent"
    asyncio.run(scenario())


def test_expired_event_never_sent(isolated, monkeypatch):
    pool, _ = isolated
    monkeypatch.setattr(platform.meta_capi, "_post_events", lambda *_: pytest.fail("Expired"))
    async def scenario():
        await platform.accept(Conversion(**payload()))
        old = Conversion(**payload()).meta_event()
        old["event_time"] = 1
        await pool.execute("UPDATE capi_platform_events SET payload=?", [json.dumps(old)])
        assert (await platform.dispatch_due())[0]["status"] == "failed"
        assert (await store.events())[0]["status"] == "expired"
        assert await platform.dispatch_due() == []
    asyncio.run(scenario())


def client():
    from src.api.security import ApiAccessMiddleware
    app = FastAPI()
    app.add_middleware(ApiAccessMiddleware)
    app.include_router(routes.router)
    return TestClient(app)


def test_ingest_auth_validation_privacy_and_size(isolated, monkeypatch):
    monkeypatch.setenv("OISHA_CAPI_INGEST_SECRET", "synthetic-ingest")
    http = client()
    endpoint = "/api/marketing/capi/events"
    assert http.post(endpoint, json=payload()).status_code == 401
    headers = {"Authorization": "Bearer synthetic-ingest"}
    response = http.post(endpoint, json=payload(consent=False), headers=headers)
    assert response.status_code == 422
    assert "synthetic@example.test" not in response.text
    assert http.post(endpoint, content="x" * 17000, headers=headers).status_code == 413
    assert http.post(endpoint, json=payload(), headers=headers).json()["status"] == "queued"
    assert http.get("/api/marketing/capi/status").status_code == 401
    assert http.post("/api/marketing/capi/dispatch").status_code == 401


def test_same_origin_denies_cross_origin():
    from starlette.requests import Request
    from fastapi import HTTPException
    request = Request({"type": "http", "scheme": "https", "path": "/", "query_string": b"",
                       "headers": [(b"host", b"oisha.test"), (b"origin", b"https://evil.test")]})
    with pytest.raises(HTTPException) as exc:
        routes.same_origin(request)
    assert exc.value.status_code == 403


def test_operator_rbac_status_no_store_and_intake_token_is_scoped(isolated, monkeypatch):
    import jwt
    from src.services.core.marketing import meta_capi_store
    pool, _ = isolated
    monkeypatch.setattr(meta_capi_store, "_pool", lambda: pool)
    monkeypatch.setattr(meta_capi_store, "_table_ready", False)
    secret = "synthetic-session-secret-for-test-only-32bytes"
    monkeypatch.setenv("JWT_SECRET", secret)
    monkeypatch.setenv("OISHA_CAPI_INGEST_SECRET", "synthetic-ingest")
    http = client()
    assert http.get("/api/marketing/capi/console", headers={
        "Authorization": "Bearer synthetic-ingest"
    }).status_code == 401
    for role in ("viewer", "seller", "admin", "owner"):
        token = jwt.encode({"sub": "synthetic-user", "role": role, "exp": int(time.time()) + 60},
                           secret, algorithm="HS256")
        http.cookies.set("oisha_token", token)
        response = http.get("/api/marketing/capi/status")
        if role in ("viewer", "seller"):
            assert response.status_code == 403
        else:
            assert response.status_code == 200
            assert response.headers["cache-control"] == "no-store"
            assert "synthetic-token" not in response.text
        if role != "owner":
            assert http.post("/api/marketing/capi/dispatch").status_code == 403
    assert http.post("/api/marketing/capi/dispatch", headers={"Origin": "https://evil.test"}).status_code == 403
    assert http.post("/api/marketing/capi/dispatch", headers={"Origin": "http://testserver"}).status_code == 200
