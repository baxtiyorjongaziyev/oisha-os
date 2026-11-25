"""Tests for canonical Uzbekistan (+998) phone normalization on amoCRM write paths."""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from src.scripts.import_bulk_contacts import format_phone as bulk_import_format_phone
from src.scripts.update_bulk_contacts import format_phone as bulk_update_format_phone
from src.services.core.crm.amocrm.phone_format import normalize_amocrm_phone
from src.services.core.crm.amocrm_chat import AmoCRMChatClient
from src.services.core.crm.amocrm_sync import AmoCRMSync
from src.services.core.crm.crm_integration import CRMIntegration
from src.services.core.crm.tg_amo_bridge.amojo_client import format_profile_phone
from src.services.core.crm.tg_amo_bridge.analyzer import (
    extract_phone_from_text,
    normalize_uz_phone as bridge_normalize_uz_phone,
)


class _Response:
    def __init__(self, status_code: int, payload: dict | None = None):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = json.dumps(self._payload)

    def json(self):
        return self._payload


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("+998973355900", "+998973355900"),
        ("998973355900", "+998973355900"),
        ("998 97 335-59-00", "+998973355900"),
        ("+998 91 602 22 60", "+998916022260"),
        ("+998(88)4742222", "+998884742222"),
        ("(+998) 90 123 45 67", "+998901234567"),
        ("901796388", "+998901796388"),
        ("97-777-11-98", "+998977771198"),
        ("33 770 93 94", "+998337709394"),
        ("871234567", "+998871234567"),
        ("920103030", "+998920103030"),
        ("0998973355900", "+998973355900"),
        ("8998973355900", "+998973355900"),
        ("00998973355900", "+998973355900"),
        ("998974077229.0", "+998974077229"),
        ("+998974077229.0", "+998974077229"),
        (998974077229.0, "+998974077229"),
        (901796388, "+998901796388"),
    ],
)
def test_normalize_uz_variants(raw, expected):
    assert normalize_amocrm_phone(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("+77086892557", "+77086892557"),
        ("+7 (708) 689-25-57", "+7 (708) 689-25-57"),
        ("+44 (0)20 7946 0958", "+44 (0)20 7946 0958"),
        ("+18184791600", "+18184791600"),
        ("+992927330086", "+992927330086"),
        ("+996555620504", "+996555620504"),
        ("+8615591801525", "+8615591801525"),
        ("77086892557", "77086892557"),
        ("861 234 56 78", "861 234 56 78"),
        ("0901234567", "0901234567"),
    ],
)
def test_preserves_foreign_numbers(raw, expected):
    assert normalize_amocrm_phone(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("", ""),
        (None, ""),
        ("   ", ""),
        ("Samarqand", "Samarqand"),
        ("egram blog: @user", "egram blog: @user"),
        ("97116", "97116"),
        ("+99897575949", "+99897575949"),
        ("9989943900433", "9989943900433"),
        ("93 991 22 22 / 97 8912222", "93 991 22 22 / 97 8912222"),
    ],
)
def test_leaves_invalid_or_ambiguous_strings_unchanged(raw, expected):
    assert normalize_amocrm_phone(raw) == expected


def test_bulk_script_formatters_strip_excel_float_suffix():
    assert bulk_import_format_phone("998974077229.0") == "+998974077229"
    assert bulk_update_format_phone("998974077229.0") == "+998974077229"
    assert bulk_import_format_phone("901796388") == "+998901796388"
    assert bulk_update_format_phone("+77086892557") == "+77086892557"


def test_amojo_format_profile_phone_handles_local_uz_and_foreign():
    assert format_profile_phone("901796388") == "+998901796388"
    assert format_profile_phone("998973355900") == "+998973355900"
    assert format_profile_phone("+998 97 335-59-00") == "+998973355900"
    assert format_profile_phone("77086892557") == "+77086892557"
    assert format_profile_phone("") is None


def test_create_contact_normalizes_uz_phone(monkeypatch):
    monkeypatch.setenv("AMOCRM_ACCESS_TOKEN", "test-long-lived-token")
    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["json"] = json
        return _Response(200, {"_embedded": {"contacts": [{"id": 12345}]}})

    monkeypatch.setattr("requests.post", fake_post)
    amo = AmoCRMSync("jonbranding", "cid", "csec", "https://example.test/cb")

    contact_id = amo.create_contact("Hasan Gaziyev", "998973355900")
    assert contact_id == 12345
    assert captured["json"][0]["custom_fields_values"][0]["values"][0]["value"] == "+998973355900"

    amo.create_contact("Ali", "90-123-45-67")
    assert captured["json"][0]["custom_fields_values"][0]["values"][0]["value"] == "+998901234567"


def test_update_contact_phone_normalizes_uz_phone(monkeypatch):
    monkeypatch.setenv("AMOCRM_ACCESS_TOKEN", "test-long-lived-token")
    patched = {}

    def fake_get(url, headers=None, params=None, timeout=None):
        return _Response(200, {"_embedded": {"contacts": [{"id": 777}]}})

    def fake_patch(url, headers=None, json=None, timeout=None):
        patched["url"] = url
        patched["json"] = json
        return _Response(200, {"id": 777})

    monkeypatch.setattr("requests.get", fake_get)
    monkeypatch.setattr("requests.patch", fake_patch)
    amo = AmoCRMSync("jonbranding", "cid", "csec", "https://example.test/cb")

    assert amo.update_contact_phone("Hasan", "973355900") is True
    assert patched["url"].endswith("/api/v4/contacts/777")
    assert patched["json"]["custom_fields_values"][0]["values"][0]["value"] == "+998973355900"


@pytest.mark.asyncio
async def test_create_lead_normalizes_phone_for_contact_and_title(monkeypatch):
    monkeypatch.setenv("AMOCRM_ACCESS_TOKEN", "test-long-lived-token")
    amo = AmoCRMSync("jonbranding", "cid", "csec", "https://example.test/cb")
    calls = {}

    monkeypatch.setattr(amo, "get_contact_by_phone", lambda p: calls.setdefault("lookup", p) and None)

    def fake_create_contact(name, phone):
        calls["contact_phone"] = phone
        return 555

    def fake_create_lead_for_contact(**kwargs):
        calls["lead_name"] = kwargs["lead_name"]
        return 999

    monkeypatch.setattr(amo, "create_contact", fake_create_contact)
    monkeypatch.setattr(amo, "create_lead_for_contact", fake_create_lead_for_contact)

    lead_id = await amo.create_lead("Bobur", "998 90 111 22 33")
    assert lead_id == 999
    assert calls["lookup"] == "+998901112233"
    assert calls["contact_phone"] == "+998901112233"
    assert calls["lead_name"] == "Bobur (+998901112233)"


def test_crm_integration_create_amocrm_lead_normalizes_phone(monkeypatch):
    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["json"] = json
        return _Response(200, [{"id": 1}])

    monkeypatch.setattr("requests.post", fake_post)
    CRMIntegration.create_amocrm_lead("Dilshod", "91-555-11-51", api_token="tok", domain="jonbranding")
    phone_val = captured["json"][0]["_embedded"]["contacts"][0]["custom_fields_values"][0]["values"][0]["value"]
    assert phone_val == "+998915551151"


@pytest.mark.asyncio
async def test_amocrm_chat_send_message_normalizes_phone(monkeypatch):
    sent = {}

    class _FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, content=None, headers=None):
            sent["payload"] = json.loads(content.decode("utf-8"))
            return SimpleNamespace(status_code=200, text="ok")

    monkeypatch.setattr("src.services.core.crm.amocrm_chat.httpx.AsyncClient", lambda **kw: _FakeClient())
    chat = AmoCRMChatClient("acc", "chan", "secret")
    ok = await chat.send_message_to_amocrm(1, 2, "Salom", "Hasan", phone="998973355900")
    assert ok is True
    assert sent["payload"]["message"]["sender"]["profile"]["phone"] == "+998973355900"


@pytest.mark.asyncio
async def test_ensure_lead_normalizes_dot_zero_before_lookup(monkeypatch):
    monkeypatch.setenv("AMOCRM_ACCESS_TOKEN", "test-long-lived-token")
    amo = AmoCRMSync("jonbranding", "cid", "csec", "https://example.test/cb")
    seen = []

    def fake_find_active(phone):
        seen.append(phone)
        return {"id": 888}

    monkeypatch.setattr(amo, "find_active_lead_by_phone", fake_find_active)
    lead_id = await amo.ensure_lead("Ali", "998974077229.0")
    assert lead_id == 888
    assert seen == ["+998974077229"]


def test_tg_amo_analyzer_recognizes_new_87_and_92_prefixes():
    assert bridge_normalize_uz_phone("871234567") == "998871234567"
    assert bridge_normalize_uz_phone("+998920103030") == "998920103030"
    assert extract_phone_from_text("Raqamim 87 123 45 67") == "998871234567"
    assert extract_phone_from_text("Tel: +998 92 010 30 30") == "998920103030"
