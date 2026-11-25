"""Oddiy CRM web sahifasi va API — synthetic amoCRM fake bilan."""
from __future__ import annotations

import json

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

SELLER_AMO_ID = 900


class FakeResponse:
    def __init__(self, status_code, payload=None):
        self.status_code = status_code
        self._payload = payload or {}

    def json(self):
        return self._payload


class FakeAmo:
    base_url = "https://example.amocrm.ru"
    access_token = "t"

    def __init__(self):
        self.created = []
        self.notes = []
        self.status_updates = []
        self.lead_queries = []
        self.note_result = {"ok": True}
        self.leads_status = 200
        self.leads = {
            5: {"id": 5, "pipeline_id": SALES_PIPELINE_ID, "responsible_user_id": SELLER_AMO_ID},
            6: {"id": 6, "pipeline_id": SALES_PIPELINE_ID, "responsible_user_id": 1},
            7: {"id": 7, "pipeline_id": 1, "responsible_user_id": SELLER_AMO_ID},
        }

    async def _request_with_auth(self, method, url, params=None, timeout=None):
        self.lead_queries.append(params)
        if self.leads_status != 200:
            return FakeResponse(self.leads_status)
        if params["filter[statuses][0][status_id]"] == SALES_NEW_STATUS_ID:
            return FakeResponse(
                200,
                {"_embedded": {"leads": [{"id": 1, "name": "Ali"}, {"name": "no id"}]}},
            )
        return FakeResponse(204)

    async def get_lead(self, lead_id):
        return self.leads.get(lead_id)

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
    monkeypatch.setenv("OISHA_CRM_SELLER_MAP_JSON", json.dumps({"42": SELLER_AMO_ID}))
    return fake


def _client(monkeypatch, role=Role.SELLER, subject="42"):
    principal = None if role is None else Principal(subject, role, "session")
    monkeypatch.setattr(security, "authorize_connection", lambda conn: principal)
    app = FastAPI()
    app.include_router(simple_crm.router)
    return TestClient(app)


def test_page_redirects_without_cookie(monkeypatch):
    r = _client(monkeypatch).get("/api/simple-crm/", follow_redirects=False)
    assert r.status_code in (302, 307)
    assert "/api/auth/telegram/login" in r.headers["location"]


def test_page_served_with_cookie(monkeypatch):
    c = _client(monkeypatch)
    c.cookies.set("oisha_token", "x")
    r = c.get("/api/simple-crm/")
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


def test_board_groups_by_stage_for_owner(monkeypatch, amo):
    d = _client(monkeypatch, Role.OWNER).get("/api/simple-crm/board").json()
    assert d["columns"][0]["leads"] == [{"id": 1, "name": "Ali"}]
    assert d["columns"][1]["leads"] == []
    assert {c["key"] for c in d["columns"]}.isdisjoint({"won", "lost"})
    assert all("filter[responsible_user_id]" not in q for q in amo.lead_queries)


def test_board_scoped_to_seller(monkeypatch, amo):
    assert _client(monkeypatch).get("/api/simple-crm/board").status_code == 200
    assert all(q["filter[responsible_user_id]"] == SELLER_AMO_ID for q in amo.lead_queries)


def test_unmapped_seller_fails_closed(monkeypatch, amo):
    r = _client(monkeypatch, subject="999").get("/api/simple-crm/board")
    assert r.status_code == 403
    assert amo.lead_queries == []


def test_board_reports_amocrm_failure(monkeypatch, amo):
    amo.leads_status = 401
    assert _client(monkeypatch).get("/api/simple-crm/board").status_code == 502


def test_create_lead_goes_to_sales_new(monkeypatch, amo):
    r = _client(monkeypatch).post(
        "/api/simple-crm/leads",
        json={"name": " Ali ", "phone": "+998 90 123-45-67", "note": "logo kerak"},
    )
    assert r.json() == {"ok": True, "lead_id": 77, "note_saved": True}
    assert amo.created[0]["pipeline_id"] == SALES_PIPELINE_ID
    assert amo.created[0]["status_id"] == SALES_NEW_STATUS_ID
    assert amo.created[0]["name"] == "Ali"
    assert amo.created[0]["phone"] == "+998901234567"
    assert "logo kerak" in amo.notes[0][1]


def test_create_lead_strips_spreadsheet_dot_zero_and_preserves_foreign(monkeypatch, amo):
    r1 = _client(monkeypatch).post(
        "/api/simple-crm/leads",
        json={"name": "Ali", "phone": "998901234567.0"},
    )
    assert r1.status_code == 200
    assert amo.created[0]["phone"] == "+998901234567"

    r2 = _client(monkeypatch).post(
        "/api/simple-crm/leads",
        json={"name": "Ivan", "phone": "861 234 56 78"},
    )
    assert r2.status_code == 200
    assert amo.created[1]["phone"] == "8612345678"


def test_create_lead_reports_lost_note(monkeypatch, amo):
    amo.note_result = False
    r = _client(monkeypatch).post(
        "/api/simple-crm/leads", json={"name": "Ali", "phone": "+998901234567"}
    )
    assert r.json()["note_saved"] is False


@pytest.mark.parametrize(
    "payload",
    [{"name": "A", "phone": "abcdefgh"}, {"name": "A", "phone": "1 2 3 4"}, {"name": "  ", "phone": "+998901234567"}],
)
def test_create_lead_rejects_bad_input(monkeypatch, amo, payload):
    r = _client(monkeypatch).post("/api/simple-crm/leads", json=payload)
    assert r.status_code == 422
    assert amo.created == []


def test_call_logs_note(monkeypatch, amo):
    r = _client(monkeypatch).post("/api/simple-crm/leads/5/call", json={"result": "no_answer"})
    assert r.status_code == 200
    assert amo.notes == [(5, "[Oddiy CRM, seller 42] Qo'ng'iroq: Javob bermadi.")]


def test_call_failure_is_reported(monkeypatch, amo):
    amo.note_result = False
    r = _client(monkeypatch).post("/api/simple-crm/leads/5/call", json={"result": "talked"})
    assert r.status_code == 502


def test_unknown_call_result_rejected(monkeypatch, amo):
    r = _client(monkeypatch).post("/api/simple-crm/leads/5/call", json={"result": "x"})
    assert r.status_code == 422


@pytest.mark.parametrize("lead_id", [6, 7, 404])
def test_seller_cannot_touch_foreign_or_other_pipeline_lead(monkeypatch, amo, lead_id):
    c = _client(monkeypatch)
    assert c.post(f"/api/simple-crm/leads/{lead_id}/call", json={"result": "talked"}).status_code == 404
    assert c.post(f"/api/simple-crm/leads/{lead_id}/stage", json={"stage": "won"}).status_code == 404
    assert amo.notes == [] and amo.status_updates == []


def test_owner_can_touch_any_sales_lead(monkeypatch, amo):
    r = _client(monkeypatch, Role.OWNER).post("/api/simple-crm/leads/6/stage", json={"stage": "won"})
    assert r.status_code == 200


def test_stage_change(monkeypatch, amo):
    r = _client(monkeypatch).post("/api/simple-crm/leads/5/stage", json={"stage": "won"})
    assert r.json() == {"ok": True, "note_saved": True}
    assert amo.status_updates == [(5, STATUS_WON, SALES_PIPELINE_ID)]
    assert "Sotildi" in amo.notes[0][1]


def test_unknown_stage_rejected(monkeypatch, amo):
    r = _client(monkeypatch).post("/api/simple-crm/leads/5/stage", json={"stage": "zzz"})
    assert r.status_code == 422
    assert amo.status_updates == []
