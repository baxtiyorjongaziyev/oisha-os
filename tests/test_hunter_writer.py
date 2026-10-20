"""Hunter yagona yozuvchisi — in-memory SQLite va soxta amoCRM bilan."""
from __future__ import annotations

import sqlite3

import pytest

from src.services.core.crm.amocrm_pipeline_config import SALES_NEW_STATUS_ID, SALES_PIPELINE_ID, STATUS_WON
from src.services.core.leads import hunter
from src.services.core.leads.hunter import Candidate, HunterWriter, normalize_phone


class MemPool:
    def __init__(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row

    async def execute(self, query, params=None):
        return [dict(r) for r in self.conn.execute(query, params or []).fetchall()]

    async def commit(self):
        self.conn.commit()


class FakeAmo:
    def __init__(self):
        self.ensured, self.standalone, self.notes = [], [], []
        self.next_id = 500
        self.fail = False
        self.tags = []
        self.lead_status = {}
        self.note_ok = True

    async def ensure_lead(self, **kw):
        self.ensured.append(kw)
        if self.fail:
            return None
        self.next_id += 1
        return self.next_id

    async def create_standalone_lead(self, **kw):
        self.standalone.append(kw)
        self.next_id += 1
        return self.next_id

    def add_lead_note(self, lead_id, text):
        self.notes.append((lead_id, text))
        return {"ok": True} if self.note_ok else False

    async def add_lead_tag(self, lead_id, tag):
        self.tags.append((lead_id, tag))
        return True

    async def get_lead(self, lead_id):
        if lead_id in self.lead_status and self.lead_status[lead_id] is None:
            return None
        return {"id": lead_id, "status_id": self.lead_status.get(lead_id, SALES_NEW_STATUS_ID)}


@pytest.fixture
def setup():
    amo, pool = FakeAmo(), MemPool()
    return amo, pool, HunterWriter(amo, pool)


def states(pool):
    return [r["state"] for r in pool.conn.execute("SELECT state FROM hunter_candidates ORDER BY id")]


@pytest.mark.parametrize(
    "raw,expected",
    [("90 123 45 67", "+998901234567"), ("+998 (90) 123-45-67", "+998901234567"),
     ("998901234567", "+998901234567"), ("1 2 3 4", None), ("Raqam yo'q", None), (None, None)],
)
def test_normalize_phone(raw, expected):
    assert normalize_phone(raw) == expected


async def test_new_lead_goes_to_sales_new(setup):
    amo, pool, w = setup
    r = await w.submit(Candidate(source="telegram_dm", name="Ali", phone="901234567", note="logo"))
    assert r.ok and r.state == "sent" and r.lead_id == 501
    assert amo.ensured[0]["pipeline_id"] == SALES_PIPELINE_ID
    assert amo.ensured[0]["status_id"] == SALES_NEW_STATUS_ID
    assert amo.ensured[0]["phone"] == "+998901234567"
    assert "telegram_dm" in amo.ensured[0]["note"] and "logo" in amo.ensured[0]["note"]
    assert states(pool) == ["sent"]
    assert amo.tags == [(501, "hunter:telegram_dm")]


async def test_same_phone_twice_adds_note_not_lead(setup):
    amo, pool, w = setup
    await w.submit(Candidate(source="telegram_dm", name="Ali", phone="+998901234567"))
    r = await w.submit(Candidate(source="meta", name="Ali V", phone="90 123 45 67"))
    assert r.state == "duplicate" and r.lead_id == 501
    assert len(amo.ensured) == 1
    assert amo.notes[0][0] == 501 and "meta" in amo.notes[0][1]


async def test_no_phone_uses_external_id(setup):
    amo, pool, w = setup
    r1 = await w.submit(Candidate(source="telegram_dm", name="Ali", phone="Raqam yo'q", external_id="tg:7"))
    r2 = await w.submit(Candidate(source="telegram_dm", name="Ali", external_id="tg:7"))
    assert r1.state == "sent" and r2.state == "duplicate"
    assert len(amo.standalone) == 1
    assert amo.standalone[0]["tags"] == ["hunter:telegram_dm"]


async def test_no_key_rejected(setup):
    amo, pool, w = setup
    r = await w.submit(Candidate(source="x", name="Ali"))
    assert not r.ok and r.error == "no_phone_or_external_id"
    assert amo.ensured == [] and amo.standalone == []


async def test_daily_limit_only_for_non_inbound(setup, monkeypatch):
    amo, pool, w = setup
    monkeypatch.setenv("HUNTER_DAILY_LIMIT", "2")
    for i in range(3):
        await w.submit(Candidate(source="channel", kind="signal", name=f"S{i}", phone=f"90000000{i}"))
    r = await w.submit(Candidate(source="telegram_dm", name="Inbound", phone="901111111"))
    assert states(pool) == ["sent", "sent", "limited", "sent"]
    assert r.ok


def test_default_limit_is_20(monkeypatch):
    monkeypatch.delenv("HUNTER_DAILY_LIMIT", raising=False)
    assert hunter.daily_limit() == 20


async def test_amocrm_failure_stays_pending(setup):
    amo, pool, w = setup
    amo.fail = True
    r = await w.submit(Candidate(source="telegram_dm", name="Ali", phone="901234567"))
    assert not r.ok and r.state == "pending"
    row = pool.conn.execute("SELECT state, attempts, error FROM hunter_candidates").fetchone()
    assert tuple(row) == ("pending", 1, "amocrm_rejected")
    amo.fail = False
    r2 = await w.submit(Candidate(source="telegram_dm", name="Ali", phone="901234567"))
    assert r2.state == "sent"  # band qilingan kalit bo'shatilgan


async def test_in_flight_key_blocks_second_writer(setup):
    amo, pool, w = setup
    await w.init()
    assert await w._reserve(["phone:+998901234567"])
    r = await w.submit(Candidate(source="meta", name="Ali", phone="901234567"))
    assert r.state == "busy"
    assert amo.ensured == []


async def test_phone_learned_later_matches_telegram_identity(setup):
    amo, pool, w = setup
    r1 = await w.submit(Candidate(source="telegram_dm", name="Ali", external_id="tg:7"))
    r2 = await w.submit(Candidate(source="telegram_dm", name="Ali", phone="901234567", external_id="tg:7"))
    r3 = await w.submit(Candidate(source="meta", name="Ali", phone="+998901234567"))
    assert (r1.state, r2.state, r3.state) == ("sent", "duplicate", "duplicate")
    assert r1.lead_id == r2.lead_id == r3.lead_id
    assert amo.ensured == []


async def test_closed_lead_gets_new_deal(setup):
    amo, pool, w = setup
    r1 = await w.submit(Candidate(source="telegram_dm", name="Ali", phone="901234567"))
    amo.lead_status[r1.lead_id] = STATUS_WON
    r2 = await w.submit(Candidate(source="telegram_dm", name="Ali", phone="901234567"))
    assert r2.state == "sent" and r2.lead_id != r1.lead_id


async def test_unreadable_lead_stays_pending(setup):
    amo, pool, w = setup
    r1 = await w.submit(Candidate(source="telegram_dm", name="Ali", phone="901234567"))
    amo.lead_status[r1.lead_id] = None
    r2 = await w.submit(Candidate(source="telegram_dm", name="Ali", phone="901234567"))
    assert (r2.ok, r2.state, r2.error) == (False, "pending", "lead_check_failed")
    assert len(amo.ensured) == 1


async def test_failed_duplicate_note_is_not_success(setup):
    amo, pool, w = setup
    await w.submit(Candidate(source="telegram_dm", name="Ali", phone="901234567"))
    amo.note_ok = False
    r = await w.submit(Candidate(source="meta", name="Ali", phone="901234567"))
    assert (r.ok, r.state, r.error) == (False, "pending", "note_failed")


async def test_group_sync_is_limited_signal(monkeypatch):
    from src.services.core.crm import crm_service

    amo, pool = FakeAmo(), MemPool()
    monkeypatch.setattr("src.database_pool.db_pool", pool)
    monkeypatch.setenv("HUNTER_DAILY_LIMIT", "0")
    svc = crm_service.CRMService.__new__(crm_service.CRMService)
    svc.amocrm = amo
    out = await svc.sync_lead(1, "G", "901234567", source="telegram_group_tn5", kind="signal")
    assert out["state"] == "limited" and amo.ensured == []


async def test_crm_service_routes_through_hunter(monkeypatch):
    from src.services.core.crm import crm_service

    amo, pool = FakeAmo(), MemPool()
    monkeypatch.setattr("src.database_pool.db_pool", pool)
    svc = crm_service.CRMService.__new__(crm_service.CRMService)
    svc.amocrm = amo
    out = await svc.sync_lead(42, "Ali", "+998901234567", note="sifatli", price=0, extra_fields={"x": 1})
    assert out == {"success": True, "lead_id": 501, "state": "sent"}
    assert amo.ensured[0]["status_id"] == SALES_NEW_STATUS_ID
