"""Saytdagi "Sizga qo'ng'iroq qilamiz" vidjeti — servis va endpoint testlari."""
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.routes import callback_widget
from src.api.security import is_protected_path
from src.services.core.leads import callback_request as cb
from src.time_utils import get_local_timezone

TZ = get_local_timezone()
DAY = datetime(2026, 10, 6, 14, 30, tzinfo=TZ)
NIGHT = datetime(2026, 10, 6, 23, 40, tzinfo=TZ)


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    cb.reset_dedup()
    monkeypatch.delenv(cb.SLA_ENV, raising=False)
    callback_widget.limiter.reset()
    yield
    cb.reset_dedup()


def _amocrm(lead_id=321):
    amo = MagicMock()
    amo.ensure_lead = AsyncMock(return_value=lead_id)
    amo.create_task = AsyncMock(return_value={"ok": True})
    return amo


# --- telefon ---

@pytest.mark.parametrize("raw,expected", [
    ("+998 90 123 45 67", "+998901234567"),
    ("901234567", "+998901234567"),
    ("998901234567", "+998901234567"),
    ("+7 916 123 45 67", "+79161234567"),
])
def test_normalize_phone(raw, expected):
    assert cb.normalize_phone(raw) == expected


@pytest.mark.parametrize("raw", ["", "123", "+998 90 123", "abc", "+99890123456789"])
def test_normalize_phone_rejects(raw):
    with pytest.raises(cb.InvalidPhoneError):
        cb.normalize_phone(raw)


def test_phone_dedup_window():
    assert cb.is_duplicate_phone("+998901234567", now=1000.0) is False
    assert cb.is_duplicate_phone("+998901234567", now=1100.0) is True
    assert cb.is_duplicate_phone("+998901234567", now=1000.0 + 11 * 60) is False


# --- manba ---

def test_source_label_variants():
    assert cb.source_label({"utm_source": "instagram", "utm_medium": "cpc", "utm_campaign": "kuz"}) == "instagram / cpc / kuz"
    assert cb.source_label({"gclid": "x"}) == "google (gclid)"
    assert cb.source_label({"fbclid": "x"}) == "meta (fbclid)"
    assert cb.source_label({"referrer": "https://t.me/"}) == "referrer: https://t.me/"
    assert cb.source_label({}) == "to'g'ridan-to'g'ri"


def test_note_contains_utm_and_pages():
    note = cb.build_note("Ali", "+998901234567", {
        "utm_source": "instagram", "utm_campaign": "kuz", "fbclid": "abc",
        "page_url": "https://jonbranding.uz/narx", "landing_url": "https://jonbranding.uz/?utm_source=instagram",
    })
    for part in ("Ali", "+998901234567", "utm_source: instagram", "utm_campaign: kuz", "fbclid: abc",
                 "Sahifa: https://jonbranding.uz/narx", "Kirish sahifasi:"):
        assert part in note


def test_alert_escapes_html():
    text = cb.build_alert("<script>", "+998901234567", {"utm_source": "<b>"}, 5, 5)
    assert "<script>" not in text and "&lt;script&gt;" in text and "&lt;b&gt;" in text


# --- oqim ---

@pytest.mark.asyncio
async def test_flow_creates_lead_alert_and_task():
    amo = _amocrm()
    with patch.object(cb, "_send_alert", AsyncMock(return_value=True)) as alert:
        res = await cb.handle_callback_request("Ali", "+998901234567", {"utm_source": "instagram"}, amocrm=amo, now=DAY)
    assert res == {"lead_id": 321, "alert": True, "task": True}
    assert "utm_source: instagram" in amo.ensure_lead.call_args.kwargs["note"]
    assert "instagram" in alert.call_args.args[0]
    assert amo.create_task.call_args.kwargs["complete_till"] == int(DAY.timestamp()) + 5 * 60


@pytest.mark.asyncio
async def test_quiet_hours_skip_telegram_task_next_morning():
    amo = _amocrm()
    with patch.object(cb, "_send_alert", AsyncMock()) as alert:
        res = await cb.handle_callback_request("", "+998901234567", {}, amocrm=amo, now=NIGHT)
    alert.assert_not_called()
    assert res["reason"] == "quiet_hours" and res["task"] is True
    expected = datetime(2026, 10, 7, 9, 0, tzinfo=TZ)
    assert amo.create_task.call_args.kwargs["complete_till"] == int(expected.timestamp())


@pytest.mark.asyncio
async def test_lead_failure_still_alerts_without_task():
    amo = _amocrm(lead_id=None)
    amo.ensure_lead = AsyncMock(side_effect=RuntimeError("amocrm down"))
    with patch.object(cb, "_send_alert", AsyncMock(return_value=True)) as alert:
        res = await cb.handle_callback_request("Ali", "+998901234567", {}, amocrm=amo, now=DAY)
    assert res["lead_id"] is None and res["alert"] is True and res["task"] is False
    alert.assert_called_once()
    amo.create_task.assert_not_called()


# --- endpoint ---

def _client():
    app = FastAPI()
    app.state.limiter = callback_widget.limiter
    app.include_router(callback_widget.router)
    return TestClient(app)


def test_endpoint_is_public():
    assert is_protected_path("/api/callback-request") is False


def test_disabled_by_default(monkeypatch):
    monkeypatch.delenv(cb.ENABLED_ENV, raising=False)
    assert _client().post("/api/callback-request", json={"phone": "+998901234567"}).status_code == 404


def test_endpoint_accepts_and_queues(monkeypatch):
    monkeypatch.setenv(cb.ENABLED_ENV, "1")
    handler = AsyncMock(return_value={})
    with patch.object(cb, "handle_callback_request", handler):
        resp = _client().post("/api/callback-request", json={
            "phone": "90 123 45 67", "name": " Ali ", "utm_source": "instagram", "page_url": "https://x.uz",
        })
    assert resp.status_code == 202
    name, phone, tracking = handler.call_args.args
    assert (name, phone) == ("Ali", "+998901234567")
    assert tracking == {"utm_source": "instagram", "page_url": "https://x.uz"}


def test_endpoint_rejects_bad_phone(monkeypatch):
    monkeypatch.setenv(cb.ENABLED_ENV, "1")
    assert _client().post("/api/callback-request", json={"phone": "1234567"}).status_code == 422


def test_honeypot_silently_ignored(monkeypatch):
    monkeypatch.setenv(cb.ENABLED_ENV, "1")
    handler = AsyncMock()
    with patch.object(cb, "handle_callback_request", handler):
        resp = _client().post("/api/callback-request", json={"phone": "+998901234567", "website": "spam.com"})
    assert resp.status_code == 202
    handler.assert_not_called()


def test_same_phone_twice_handled_once(monkeypatch):
    monkeypatch.setenv(cb.ENABLED_ENV, "1")
    handler = AsyncMock(return_value={})
    client = _client()
    with patch.object(cb, "handle_callback_request", handler):
        client.post("/api/callback-request", json={"phone": "+998901234567"})
        client.post("/api/callback-request", json={"phone": "+998 90 123 45 67"})
    assert handler.call_count == 1


def test_rate_limit(monkeypatch):
    monkeypatch.setenv(cb.ENABLED_ENV, "1")
    client = _client()
    with patch.object(cb, "handle_callback_request", AsyncMock(return_value={})):
        codes = [
            client.post("/api/callback-request", json={"phone": f"+99890123450{i}"}).status_code
            for i in range(7)
        ]
    assert codes[:5] == [202] * 5
    assert 429 in codes[5:]


def test_oversized_fields_rejected(monkeypatch):
    monkeypatch.setenv(cb.ENABLED_ENV, "1")
    resp = _client().post("/api/callback-request", json={"phone": "+998901234567", "utm_source": "x" * 500})
    assert resp.status_code == 422


@pytest.mark.parametrize("path", ["/api/callback-widget.js", "/callback-widget.js"])
def test_widget_js_served(path):
    resp = _client().get(path)
    assert resp.status_code == 200
    assert "javascript" in resp.headers["content-type"]
    assert "OishaCallback" in resp.text
    assert is_protected_path(path) is False
