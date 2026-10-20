"""Oddiy CRM web sahifasi va API — synthetic amoCRM fake bilan."""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api import security
from src.api.rbac import Principal, Role
from src.api.routes import simple_crm
from src.api.routes.state import api_state
from src.services.core.crm.amocrm_pipeline_config import (
    SALES_NEW_STATUS_ID,
    SALES_PIPELINE_ID,
    STATUS_WON,
)


class FakeAmo:
    def __init__(self):
        self.created = []
        self.notes = []
        self.status_updates = []
        self.note_result = {"ok": True}

    async def get_leads(self, status_id=None, limit=None, **kwargs):
        if status_id == SALES_NEW_STATUS_ID:
            return [{"id": 1, "name": "Ali (+998901234567)"}, {"name": "no id"}]
        return []

    async def create_lead(self, **kwargs):
        self.created.append(kwargs)
        return 77

    def add_lead_note(self, lead_id, text):
        self.notes.append((lead_id, text))
        return self.note_result

    async def update_lead_status(self, lead_id, status_id, pipeline_id=None):
        self.status_updates.append((lead_id, status_id, pipeline_id))
        return True


@pytest.fixture
def amo(monkeypatch):
    fake = FakeAmo()
    monkeypatch.setattr(api_state, "amocrm_instance", fake, raising=False)
    return fake


def _client(monkeypatch, role=Role.SELLER):
    principal = None if role is None else Principal("42", role, "session")
    monkeypatch.setattr(security, "authorize_connection", lambda conn: principal)
    app = FastAPI()
    app.include_router(simple_crm.router)
    return TestClient(app)


def test_page_redirects_without_cookie(monkeypatch):
    r = _client(monkeypatch).get("/crm", follow_redirects=False)
    assert r.status_code in (302, 307)
    assert "/api/auth/telegram/login" in r.headers["location"]


def test_page_served_with_cookie(monkeypatch):
    c = _client(monkeypatch)
    c.cookies.set("oisha_token", "x")
    r = c.get("/crm")
    assert r.status_code == 200
    assert "Yangi mijoz" in r.text


def test_api_requires_auth(monkeypatch, amo):
    assert _client(monkeypatch, None).get("/api/simple-crm/board").status_code == 401


def test_viewer_cannot_write(monkeypatch, amo):
    r = _client(monkeypatch, Role.VIEWER).post(
        "/api/simple-crm/leads", json={"name": "A", "phone": "+998901234567"}
    )
    assert r.status_code == 403
    assert amo.created == []


def test_board_groups_by_stage(monkeypatch, amo):
    d = _client(monkeypatch).get("/api/simple-crm/board").json()
    first = d["columns"][0]
    assert first["key"] == "new"
    assert first["leads"] == [{"id": 1, "name": "Ali (+998901234567)"}]
    assert {c["key"] for c in d["columns"]}.isdisjoint({"won", "lost"})


def test_create_lead_goes_to_sales_new(monkeypatch, amo):
    r = _client(monkeypatch).post(
        "/api/simple-crm/leads",
        json={"name": " Ali ", "phone": "+998 90 123 45 67", "note": "logo kerak"},
    )
    assert r.json() == {"ok": True, "lead_id": 77}
    assert amo.created[0]["pipeline_id"] == SALES_PIPELINE_ID
    assert amo.created[0]["status_id"] == SALES_NEW_STATUS_ID
    assert amo.created[0]["name"] == "Ali"
    assert "logo kerak" in amo.notes[0][1]


def test_create_lead_rejects_bad_phone(monkeypatch, amo):
    r = _client(monkeypatch).post(
        "/api/simple-crm/leads", json={"name": "A", "phone": "abcdefgh"}
    )
    assert r.status_code == 422
    assert amo.created == []


def test_call_logs_note(monkeypatch, amo):
    r = _client(monkeypatch).post(
        "/api/simple-crm/leads/5/call", json={"result": "no_answer"}
    )
    assert r.status_code == 200
    assert amo.notes == [(5, "[Oddiy CRM, seller 42] Qo'ng'iroq: Javob bermadi.")]


def test_call_failure_is_reported(monkeypatch, amo):
    amo.note_result = False
    r = _client(monkeypatch).post("/api/simple-crm/leads/5/call", json={"result": "talked"})
    assert r.status_code == 502


def test_unknown_call_result_rejected(monkeypatch, amo):
    r = _client(monkeypatch).post("/api/simple-crm/leads/5/call", json={"result": "x"})
    assert r.status_code == 422


def test_stage_change(monkeypatch, amo):
    r = _client(monkeypatch).post("/api/simple-crm/leads/5/stage", json={"stage": "won"})
    assert r.status_code == 200
    assert amo.status_updates == [(5, STATUS_WON, SALES_PIPELINE_ID)]
    assert "Sotildi" in amo.notes[0][1]


def test_unknown_stage_rejected(monkeypatch, amo):
    r = _client(monkeypatch).post("/api/simple-crm/leads/5/stage", json={"stage": "zzz"})
    assert r.status_code == 422
    assert amo.status_updates == []
