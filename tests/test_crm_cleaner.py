"""Smoke tests for telegram_phone_enricher and deal_ai_analyzer.

Real AmoCRM yoki Telegramga tegmaydi — mock obyektlar ishlatadi.
"""
from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.services.core.telegram_phone_enricher import (
    TelegramPhoneEnricher,
    extract_usernames,
    normalize_phone,
    extract_existing_phones,
)
from src.services.core.deal_ai_analyzer import (
    DealAIAnalyzer,
    CATEGORY_TAGS,
)


# -------- normalizers --------

def test_normalize_phone_adds_country_code():
    assert normalize_phone("90 123 45 67") == "998901234567"
    assert normalize_phone("+998 (90) 123-45-67") == "998901234567"
    assert normalize_phone("not a phone") == ""


def test_extract_usernames_skips_emails():
    text = "Mijoz @baxtiyorjon_g va email: test@gmail.com, telegram: t.me/orbit_studio"
    found = extract_usernames(text)
    assert "baxtiyorjon_g" in found
    assert "orbit_studio" in found
    assert "gmail" not in found


def test_extract_existing_phones():
    contact = {
        "custom_fields_values": [
            {
                "field_code": "PHONE",
                "values": [{"value": "+998 90 123 45 67"}],
            }
        ]
    }
    phones = extract_existing_phones(contact)
    assert any(p.endswith("901234567") for p in phones)


# -------- enricher pipeline (mocked) --------

@pytest.mark.asyncio
async def test_enricher_dry_run_resolves_phone():
    amocrm = MagicMock()
    amocrm.base_url = "https://x.amocrm.ru"
    amocrm._load_token = MagicMock()
    amocrm._get_headers = MagicMock(return_value={})
    amocrm.refresh_token = MagicMock(return_value=False)
    amocrm.add_contact_note = MagicMock(return_value={"ok": True})
    amocrm.add_contact_tag = MagicMock(return_value=True)
    amocrm._get_notes = MagicMock(return_value=[])

    enricher = TelegramPhoneEnricher(amocrm=amocrm, tg_client=MagicMock())
    enricher.rate_limit_sec = 0
    enricher._fetch_contacts = AsyncMock(
        return_value=[
            {"id": 101, "name": "Mijoz @baxtiyorjon_g", "custom_fields_values": []},
            {"id": 102, "name": "No tg here", "custom_fields_values": []},
        ]
    )
    enricher._resolve_username = AsyncMock(return_value=("998901234567", 555))

    report = await enricher.run(limit=10, dry_run=True)
    assert report.dry_run is True
    assert report.checked == 2
    assert report.no_phone == 2
    # 101 should be found, 102 should be not_found
    statuses = [r.status for r in report.results]
    assert "dry_run" in statuses
    assert "not_found" in statuses
    assert amocrm.add_contact_note.call_count == 0  # dry-run = no writes


@pytest.mark.asyncio
async def test_enricher_apply_writes_phone():
    amocrm = MagicMock()
    amocrm.base_url = "https://x.amocrm.ru"
    amocrm._load_token = MagicMock()
    amocrm._get_headers = MagicMock(return_value={})
    amocrm.refresh_token = MagicMock(return_value=False)
    amocrm.add_contact_note = MagicMock(return_value={"ok": True})
    amocrm.add_contact_tag = MagicMock(return_value=True)
    amocrm._get_notes = MagicMock(return_value=[])

    enricher = TelegramPhoneEnricher(amocrm=amocrm, tg_client=MagicMock())
    enricher.rate_limit_sec = 0
    enricher._fetch_contacts = AsyncMock(
        return_value=[
            {"id": 101, "name": "Mijoz @baxtiyorjon_g", "custom_fields_values": []},
        ]
    )
    enricher._resolve_username = AsyncMock(return_value=("998901234567", 555))
    enricher._patch_contact_phone = MagicMock(return_value=True)

    report = await enricher.run(limit=10, dry_run=False)
    assert report.applied == 1
    enricher._patch_contact_phone.assert_called_once_with(101, "998901234567")
    amocrm.add_contact_note.assert_called_once()


# -------- AI analyzer --------

@pytest.mark.asyncio
async def test_deal_ai_analyzer_classifies_via_mock_ai():
    amocrm = MagicMock()
    amocrm.get_leads_detailed = AsyncMock(
        return_value=[
            {
                "id": 9001,
                "name": "Test sdelka @baxtiyorjon_g",
                "status_id": 1,
                "pipeline_id": 1,
                "_embedded": {"contacts": []},
            }
        ]
    )
    amocrm.get_lead_notes = AsyncMock(return_value=[])
    amocrm.get_contact_details = MagicMock(return_value=None)
    amocrm.add_lead_tag = AsyncMock(return_value=True)
    amocrm.add_lead_note = MagicMock(return_value={"ok": True})

    tg_client = MagicMock()
    tg_client.get_entity = AsyncMock(return_value=None)

    async def mock_iter(*args, **kwargs):
        if False:
            yield  # pragma: no cover
    tg_client.iter_messages = mock_iter

    async def fake_ai(prompt: str) -> str:
        return json.dumps({
            "category": "JUNK",
            "confidence": 0.82,
            "reason": "Suhbat yo'q, raqam yo'q, sdelka bo'sh",
            "evidence": ["Ism bo'sh", "Telegramda javob yo'q"],
            "recommended_action": "Lost ga ko'chiring",
        })

    analyzer = DealAIAnalyzer(
        amocrm=amocrm, tg_client=tg_client, ai_call=fake_ai, message_window=5
    )
    analyzer.rate_limit_sec = 0

    report = await analyzer.run(limit=5, dry_run=True)
    assert report.checked == 1
    item = report.items[0]
    assert item.category == "JUNK"
    assert 0 < item.confidence < 1
    assert item.status == "dry_run"
    assert item.lead_id == 9001


@pytest.mark.asyncio
async def test_deal_ai_analyzer_apply_writes_tag_and_note():
    amocrm = MagicMock()
    amocrm.get_leads_detailed = AsyncMock(
        return_value=[
            {
                "id": 7000,
                "name": "Lead",
                "status_id": 1,
                "pipeline_id": 1,
                "_embedded": {"contacts": []},
            }
        ]
    )
    amocrm.get_lead_notes = AsyncMock(return_value=[])
    amocrm.get_contact_details = MagicMock(return_value=None)
    amocrm.add_lead_tag = AsyncMock(return_value=True)
    amocrm.add_lead_note = MagicMock(return_value={"ok": True})

    async def mock_iter(*args, **kwargs):
        if False:
            yield  # pragma: no cover
    tg_client = MagicMock()
    tg_client.get_entity = AsyncMock(return_value=None)
    tg_client.iter_messages = mock_iter

    async def fake_ai(prompt: str) -> str:
        return "```json\n" + json.dumps({
            "category": "REAL_CLIENT",
            "confidence": 0.91,
            "reason": "Aniq sotuv suhbati",
            "evidence": ["Narx so'radi"],
            "recommended_action": "Davom ettirish",
        }) + "\n```"

    analyzer = DealAIAnalyzer(
        amocrm=amocrm, tg_client=tg_client, ai_call=fake_ai, message_window=5
    )
    analyzer.rate_limit_sec = 0
    report = await analyzer.run(limit=5, dry_run=False)
    item = report.items[0]
    assert item.category == "REAL_CLIENT"
    assert item.tag_applied == CATEGORY_TAGS["REAL_CLIENT"]
    assert item.note_applied is True
    amocrm.add_lead_tag.assert_awaited_once()
    amocrm.add_lead_note.assert_called_once()


# -------- ai response parser edge cases --------

def test_parse_ai_handles_fenced_json():
    parsed = DealAIAnalyzer._parse_ai_response("```json\n{\"category\":\"SPAM\"}\n```")
    assert parsed == {"category": "SPAM"}


def test_parse_ai_handles_garbage():
    parsed = DealAIAnalyzer._parse_ai_response("not even json")
    assert parsed == {}
