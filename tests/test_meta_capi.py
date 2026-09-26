"""Meta CAPI (Conversion Leads): payload, hash, idempotency, mapping, callback ruxsati."""
from __future__ import annotations

import asyncio
import hashlib
import sqlite3
from types import SimpleNamespace

import pytest

from src.services.core.marketing import meta_capi, meta_capi_store, meta_capi_triggers


class _SqlitePool:
    """database_pool.db_pool o'rniga in-memory SQLite (RETURNING qo'llaydi)."""

    def __init__(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row

    async def execute(self, query, params=None):
        cur = self.conn.execute(query, params or [])
        rows = [dict(r) for r in cur.fetchall()]
        return rows

    async def commit(self):
        self.commits = getattr(self, "commits", 0) + 1
        self.conn.commit()


@pytest.fixture
def pool(monkeypatch):
    p = _SqlitePool()
    monkeypatch.setattr(meta_capi_store, "_pool", lambda: p)
    monkeypatch.setattr(meta_capi_store, "_table_ready", False)
    return p


@pytest.fixture
def enabled(monkeypatch):
    cfg = {"enabled": True, "dataset_id": "999", "token": "tok", "test_code": "", "version": "v21.0"}
    monkeypatch.setattr(meta_capi, "_config", lambda: dict(cfg))
    return cfg


def _run(coro):
    return asyncio.run(coro)


def test_build_event_shape_and_hash():
    ev = meta_capi.build_event("123", "Purchase", value=5_000_000, phone="+998 90 123-45-67",
                               email=" A@B.uz ", event_time=1700000000)
    assert ev["action_source"] == "system_generated"
    assert ev["event_time"] == 1700000000
    assert ev["user_data"]["lead_id"] == "123"
    assert ev["event_id"] == "crm-123-Purchase"
    assert ev["user_data"]["ph"] == [hashlib.sha256(b"998901234567").hexdigest()]
    assert ev["user_data"]["em"] == [hashlib.sha256(b"a@b.uz").hexdigest()]
    assert ev["custom_data"] == {"event_source": "crm", "lead_event_source": "Oisha-OS",
                                 "value": 5_000_000.0, "currency": "UZS"}


def test_build_event_qualified_has_no_value_or_pii():
    ev = meta_capi.build_event("123", "QualifiedLead")
    assert "value" not in ev["custom_data"]
    assert set(ev["user_data"]) == {"lead_id"}


def test_disabled_by_default_sends_nothing(monkeypatch, pool):
    monkeypatch.setattr(meta_capi, "_config", lambda: {"enabled": False, "dataset_id": "", "token": "",
                                                        "test_code": "", "version": "v21.0"})
    res = _run(meta_capi.send_crm_event("123", "Purchase"))
    assert res.status == "disabled" and not res.success


def test_idempotent_send(monkeypatch, pool, enabled):
    calls = []

    def fake_post(cfg, event):
        calls.append((cfg["dataset_id"], event["event_name"]))
        return {"ok": True, "response": {"events_received": 1}}

    monkeypatch.setattr(meta_capi, "_post_events", fake_post)
    first = _run(meta_capi.send_crm_event("555", "QualifiedLead", amo_lead_id=7))
    second = _run(meta_capi.send_crm_event("555", "QualifiedLead", amo_lead_id=7))
    assert first.status == "sent" and second.status == "duplicate"
    assert calls == [("999", "QualifiedLead")]
    assert pool.commits >= 2
    assert _run(meta_capi_store.get_event_status("555", "QualifiedLead")) == "sent"


def test_failed_send_can_retry(monkeypatch, pool, enabled):
    results = iter([{"ok": False, "error": "HTTP 500"}, {"ok": True, "response": {}}])
    monkeypatch.setattr(meta_capi, "_post_events", lambda cfg, ev: next(results))
    assert _run(meta_capi.send_crm_event("777", "Purchase")).status == "failed"
    assert _run(meta_capi_store.get_event_status("777", "Purchase")) == "failed"
    assert _run(meta_capi.send_crm_event("777", "Purchase")).status == "sent"


def test_post_events_no_retry_on_4xx(monkeypatch):
    calls = []

    def fake_post(url, json, timeout):
        calls.append((url, json))
        return SimpleNamespace(status_code=400, json=lambda: {})

    monkeypatch.setattr(meta_capi.requests, "post", fake_post)
    cfg = {"dataset_id": "999", "token": "tok", "test_code": "TEST1", "version": "v21.0"}
    out = meta_capi._post_events(cfg, {"event_name": "Purchase"})
    assert out == {"ok": False, "error": "HTTP 400"}
    assert len(calls) == 1
    assert calls[0][0] == "https://graph.facebook.com/v21.0/999/events"
    assert calls[0][1]["test_event_code"] == "TEST1"


def test_status_mapping(monkeypatch):
    monkeypatch.setenv("META_CAPI_QUALIFIED_STATUS_IDS", "111, 222")
    assert meta_capi_triggers.event_for_status(142) == "Purchase"
    assert meta_capi_triggers.event_for_status("222") == "QualifiedLead"
    assert meta_capi_triggers.event_for_status(143) is None
    assert meta_capi_triggers.event_for_status(None) is None


def test_on_amo_status_reverse_lookup(monkeypatch):
    sent = {}

    async def fake_send(leadgen_id, event_name, **kw):
        sent.update(leadgen_id=leadgen_id, event_name=event_name, **kw)
        return "ok"

    monkeypatch.setattr(meta_capi_triggers, "is_enabled", lambda: True)
    monkeypatch.setattr(meta_capi_triggers, "send_crm_event", fake_send)
    import src.services.core.instagram.leadgen_delivery as delivery
    monkeypatch.setattr(delivery, "get_leadgen_id_by_lead_id", lambda lid: "LG1" if lid == 42 else None)
    assert _run(meta_capi_triggers.on_amo_status(42, 142, price=100.0)) == "ok"
    assert sent["leadgen_id"] == "LG1" and sent["event_name"] == "Purchase" and sent["value"] == 100.0
    assert _run(meta_capi_triggers.on_amo_status(43, 142)) is None


def test_reverse_lookup_in_delivery_db(monkeypatch, tmp_path):
    import src.services.core.instagram.leadgen_delivery as delivery
    monkeypatch.setattr(delivery, "_DB_PATH", tmp_path / "d.db")
    delivery.save_crm_checkpoint("LG9", 900)
    assert delivery.get_leadgen_id_by_lead_id(900) == "LG9"
    assert delivery.get_leadgen_id_by_lead_id(901) is None


def test_buttons_and_parse(monkeypatch):
    monkeypatch.setattr(meta_capi_triggers, "is_enabled", lambda: False)
    assert meta_capi_triggers.capi_button_rows("123") == []
    monkeypatch.setattr(meta_capi_triggers, "is_enabled", lambda: True)
    row = meta_capi_triggers.capi_button_rows("123")[0]
    assert [b["callback_data"] for b in row] == ["capi:q:123", "capi:p:123"]
    assert all(len(b["callback_data"].encode()) <= 64 for b in row)
    assert meta_capi_triggers.parse_callback("capi:p:123") == ("Purchase", "123")
    assert meta_capi_triggers.parse_callback("capi:x:123") is None
    assert meta_capi_triggers.parse_callback("capi:q:12;drop") is None


class _Event:
    def __init__(self, sender_id):
        self.sender_id = sender_id
        self.answers = []
        self.message = SimpleNamespace(text="Lead", reply_markup=None)

    async def answer(self, text, alert=False):
        self.answers.append((text, alert))

    async def edit(self, text, buttons=None):
        self.message.text = text


def _settings(monkeypatch, owner=1, whitelist=(2,)):
    import src.settings as s
    monkeypatch.setattr(s.settings, "OWNER_ID", owner, raising=False)
    monkeypatch.setattr(s.settings, "WHITELIST_IDS", list(whitelist), raising=False)


def test_callback_rejects_non_whitelisted(monkeypatch):
    _settings(monkeypatch)
    called = []

    async def fake_send(*a, **kw):
        called.append(a)

    monkeypatch.setattr(meta_capi_triggers, "send_crm_event", fake_send)
    ev = _Event(sender_id=99)
    _run(meta_capi_triggers.handle_capi_callback(ev, "capi:q:123"))
    assert not called and ev.answers[0][1] is True


def test_callback_whitelisted_sends_and_edits(monkeypatch):
    _settings(monkeypatch)
    from src.services.core.tool_registry import ToolResult
    import src.services.core.instagram.leadgen_delivery as delivery
    monkeypatch.setattr(delivery, "get_crm_checkpoint", lambda lg: 555)
    seen = {}

    async def fake_send(leadgen_id, event_name, **kw):
        seen.update(leadgen_id=leadgen_id, event_name=event_name, **kw)
        return ToolResult("meta_capi", True, status="sent")

    monkeypatch.setattr(meta_capi_triggers, "send_crm_event", fake_send)

    async def price(lid):
        return 7_000_000.0

    monkeypatch.setattr(meta_capi_triggers, "_amo_lead_price", price)
    ev = _Event(sender_id=2)
    _run(meta_capi_triggers.handle_capi_callback(ev, "capi:p:123"))
    assert seen["event_name"] == "Purchase" and seen["amo_lead_id"] == 555
    assert seen["value"] == 7_000_000.0
    assert "Meta CAPI" in ev.message.text


def test_manual_purchase_without_price_is_refused(monkeypatch):
    _settings(monkeypatch)
    import src.services.core.instagram.leadgen_delivery as delivery
    monkeypatch.setattr(delivery, "get_crm_checkpoint", lambda lg: 555)
    called = []

    async def fake_send(*a, **kw):
        called.append(a)

    async def no_price(lid):
        return None

    monkeypatch.setattr(meta_capi_triggers, "send_crm_event", fake_send)
    monkeypatch.setattr(meta_capi_triggers, "_amo_lead_price", no_price)
    ev = _Event(sender_id=2)
    _run(meta_capi_triggers.handle_capi_callback(ev, "capi:p:123"))
    assert not called and "summa" in ev.answers[0][0]


def test_failed_purchase_keeps_attribution_row_open(monkeypatch):
    from src.services.core.marketing import attribution_sync
    from src.services.core.tool_registry import ToolResult
    import src.services.core.marketing.meta_capi_triggers as trig
    updates = []
    monkeypatch.setattr(attribution_sync, "pending_revenue_sync",
                        lambda d, l: [{"leadgen_id": "LG1", "lead_id": 42}])
    monkeypatch.setattr(attribution_sync, "update_revenue", lambda *a: updates.append(a))
    monkeypatch.setattr(attribution_sync, "_REQUEST_DELAY_SECONDS", 0)

    async def failed(*a, **kw):
        return ToolResult("meta_capi", False, status="failed")

    monkeypatch.setattr(trig, "on_amo_status", failed)

    class Amo:
        async def get_lead(self, lid):
            return {"price": 100, "status_id": 142}

    res = _run(attribution_sync.sync_attribution_revenue(Amo()))
    assert updates == [] and res.failed == 1
