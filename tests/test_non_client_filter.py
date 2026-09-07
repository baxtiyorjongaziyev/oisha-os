"""
Unit tests for non-client detection and suppression filter.
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.services.core.crm.non_client_filter import (
    clear_non_client_cache,
    is_lead_marked_as_non_client,
    is_sender_marked_as_non_client,
    is_text_marked_as_non_client,
)


@pytest.fixture(autouse=True)
def _clear_cache():
    clear_non_client_cache()
    yield
    clear_non_client_cache()


def test_is_text_marked_as_non_client_positives():
    cases = [
        "Mijoz emas",
        "Sardor (mijoz emas)",
        "Bu odam klient emas",
        "klientmas",
        "mijozmas",
        "клиент эмас",
        "мижоз эмас",
        "Не клиент",
        "Нецелевой лид",
        "не целевой",
        "not a client",
        "Not client",
        "non-client lead",
        "Adashgan nomer",
        "adashib tushgan",
        "adashib tushgan lid",
        "wrong number",
        "Spam reklama",
        "спам",
        "xizmat kerak emas",
        "keremas ekan",
        "qiziqmadi",
        "qiziqish yo'q",
        "rad etdi",
        "rad qildi",
        "отказ клиента",
        "нет потребности",
        "shaxsiy kontakt",
        "oila a'zosi",
        "hamkor kompaniya",
        "bizning xodim",
        "ustoz Baxtiyor aka",
    ]
    for text in cases:
        matched, reason = is_text_marked_as_non_client(text)
        assert matched is True, f"Expected matched=True for: {text!r}"
        assert bool(reason) is True


def test_is_text_marked_as_non_client_false_positives():
    cases = [
        "Haqiqiy mijoz bilan uchrashuv",
        "Yangi mijoz kirdi",
        "Mijoz talabi bo'yicha brending",
        "Klient bilan gaplashildi",
        "Kompaniya direktori",
        "Branding xizmati",
        "Salom, narxlar qanday?",
        "Hammasi yaxshi",
        "",
        None,
    ]
    for text in cases:
        matched, reason = is_text_marked_as_non_client(text)
        assert matched is False, f"Expected matched=False for: {text!r}"


@pytest.mark.asyncio
async def test_is_lead_marked_by_deal_name():
    sync = MagicMock()
    lead_data = {"id": 101, "name": "Akmal (Mijoz emas)"}
    matched, reason = await is_lead_marked_as_non_client(sync, 101, lead_data=lead_data)
    assert matched is True
    assert "sdelka_nomi" in reason


@pytest.mark.asyncio
async def test_is_lead_marked_by_tag():
    sync = MagicMock()
    lead_data = {
        "id": 102,
        "name": "Dilshod",
        "_embedded": {"tags": [{"id": 1, "name": "mijoz emas"}]},
    }
    matched, reason = await is_lead_marked_as_non_client(sync, 102, lead_data=lead_data)
    assert matched is True
    assert "tag" in reason


@pytest.mark.asyncio
async def test_is_lead_marked_by_contact_name():
    sync = MagicMock()
    lead_data = {
        "id": 103,
        "name": "Loyiha",
        "_embedded": {"contacts": [{"id": 501, "name": "Rustam (not client)"}]},
    }
    matched, reason = await is_lead_marked_as_non_client(sync, 103, lead_data=lead_data)
    assert matched is True
    assert "mijoz_nomi" in reason


@pytest.mark.asyncio
async def test_is_lead_marked_by_note_primechaniya():
    sync = MagicMock()
    sync.get_lead_notes = AsyncMock(return_value=[
        {"id": 1, "params": {"text": "Qo'ng'iroq qilindi: xizmat kerak emas deb rad etdi"}}
    ])
    sync.get_lead_tasks = AsyncMock(return_value=[])
    lead_data = {"id": 104, "name": "Loyiha Branding"}

    matched, reason = await is_lead_marked_as_non_client(sync, 104, lead_data=lead_data)
    assert matched is True
    assert "primechaniya" in reason


@pytest.mark.asyncio
async def test_is_lead_marked_by_task_result():
    sync = MagicMock()
    sync.get_lead_notes = AsyncMock(return_value=[])
    sync.get_lead_tasks = AsyncMock(return_value=[
        {
            "id": 88,
            "text": "Qo'ng'iroq qilish",
            "result": {"text": "Gaplashildi, mijoz emas ekan, adashgan"},
        }
    ])
    lead_data = {"id": 105, "name": "Loyiha X"}

    matched, reason = await is_lead_marked_as_non_client(sync, 105, lead_data=lead_data)
    assert matched is True
    assert "zadachaga_javob" in reason


@pytest.mark.asyncio
async def test_valid_lead_not_marked():
    sync = MagicMock()
    sync.get_lead_notes = AsyncMock(return_value=[
        {"id": 1, "params": {"text": "Mijoz yangi brending uchun 5000$ byudjet aytdi"}}
    ])
    sync.get_lead_tasks = AsyncMock(return_value=[
        {"id": 88, "text": "Taqdimot yuborish", "result": {"text": "Taqdimot ko'rildi"}}
    ])
    lead_data = {
        "id": 106,
        "name": "Chopar Pizza Branding",
        "_embedded": {"contacts": [{"id": 502, "name": "Farxod aka"}]},
    }

    matched, reason = await is_lead_marked_as_non_client(sync, 106, lead_data=lead_data)
    assert matched is False
    assert reason == ""


@pytest.mark.asyncio
async def test_create_task_blocked_for_non_client():
    from src.services.core.crm.amocrm.sync import AmoCRMSync

    sync = AmoCRMSync(token_file="data/test_amocrm_token.json")
    sync.get_lead = AsyncMock(return_value={"id": 999, "status_id": 100, "name": "Adashgan nomer (Spam)"})
    sync.get_lead_notes = AsyncMock(return_value=[])
    sync.get_lead_tasks = AsyncMock(return_value=[])

    res = await sync.create_task(element_id=999, text="Follow-up call", complete_till=1800000000)
    assert res is False
    assert sync.last_error == "lead_marked_as_non_client"


@pytest.mark.asyncio
async def test_is_sender_marked_by_name_or_contact():
    sync = MagicMock()
    sync.get_contact_by_phone = AsyncMock(return_value={"id": 77, "name": "Javohir (mijoz emas)"})
    sync.get_notes = AsyncMock(return_value=[])

    # Direct name test
    matched, reason = await is_sender_marked_as_non_client(sync, name="Javohir (mijoz emas)")
    assert matched is True

    # Phone contact lookup test
    clear_non_client_cache()
    matched, reason = await is_sender_marked_as_non_client(sync, phone="+998901234567")
    assert matched is True
    assert "amocrm_contact" in reason
