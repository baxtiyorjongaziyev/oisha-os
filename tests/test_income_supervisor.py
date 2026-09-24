import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from src.services.core.finance.income_supervisor import (
    extract_phone_numbers,
    extract_brand_or_client,
    resolve_seller_for_income,
    supervise_recent_incomes,
    AMOCRM_USER_TO_JAMOA,
)


def test_extract_phone_numbers():
    text = "Mijoz: Izzatbek Muxtorov\nTel: +998 94 382 15 55\nQo'shimcha: 90 508-43-38"
    phones = extract_phone_numbers(text)
    assert "943821555" in phones
    assert "905084338" in phones


def test_extract_brand_or_client():
    text = "Brand nomi: Shukrona\nMijoz: Izzatbek Muxtorov\nXizmat turi: Patentlash"
    queries = extract_brand_or_client(text)
    assert "Shukrona" in queries
    assert "Izzatbek Muxtorov" in queries


@pytest.mark.asyncio
async def test_resolve_seller_from_loyiha():
    mock_at = MagicMock()
    mock_at.get_project.return_value = {
        "id": "recProj1",
        "fields": {
            "Loyiha nomi": "Test Project",
            "Sotuvchi": ["rec8fmSHRpZi5Rx9N"],
        },
    }

    record = {
        "id": "recTrx1",
        "fields": {
            "Tranzaksiya": "Kirim - Test",
            "Loyiha": ["recProj1"],
            "Izoh": "Oddiy to'lov",
        },
    }

    res = await resolve_seller_for_income(record, airtable_sync=mock_at)
    assert res is not None
    assert res["seller_id"] == "rec8fmSHRpZi5Rx9N"
    assert res["source"] == "Loyiha kartasi"


@pytest.mark.asyncio
async def test_resolve_seller_from_amocrm_phone():
    mock_crm = AsyncMock()
    mock_crm.search_leads.return_value = [
        {"id": 12345, "name": "Asl kids deal", "responsible_user_id": 13021974}
    ]

    record = {
        "id": "recTrx2",
        "fields": {
            "Tranzaksiya": "Kirim - Asl kids",
            "Izoh": "Tel: +998 90 508 43 38\nAvans to'landi",
        },
    }

    res = await resolve_seller_for_income(record, amocrm_sync=mock_crm)
    assert res is not None
    assert res["seller_id"] == "rec8fmSHRpZi5Rx9N"
    assert "AmoCRM telefon" in res["source"]


@pytest.mark.asyncio
async def test_resolve_seller_from_izoh_name():
    record = {
        "id": "recTrx3",
        "fields": {
            "Tranzaksiya": "Kirim - Shaxsiy",
            "Izoh": "Ahrorbek orqali yangi mijozdan avans olindi",
        },
    }

    res = await resolve_seller_for_income(record)
    assert res is not None
    assert res["seller_id"] == "recp8ClrBsXi6G0Km"
    assert "Ahrorbek" in res["source"]


@pytest.mark.asyncio
async def test_supervise_recent_incomes_execution():
    mock_at = MagicMock()
    mock_at.get_transactions.return_value = [
        {
            "id": "recTrx10",
            "fields": {
                "Turi": "Kirim",
                "Tranzaksiya": "Kirim - Asl kids",
                "Summa UZS": 10000000,
                "Izoh": "Ahrorbek orqali",
            },
        },
        {
            "id": "recTrx20",
            "fields": {
                "Turi": "Kirim",
                "Tranzaksiya": "Kirim - Noma'lum",
                "Summa UZS": 500000,
                "Izoh": "Hech qanday ma'lumot yo'q",
            },
        },
    ]
    mock_at.update_project_fields.return_value = True
    mock_crm = AsyncMock()
    mock_crm.search_leads.return_value = []

    with patch("src.services.core.finance.income_supervisor._dispatch_supervisor_alert") as mock_alert, \
         patch("src.services.core.finance.income_supervisor._ALERTED_RECORD_IDS", set()):
        stats = await supervise_recent_incomes(
            airtable_sync=mock_at, amocrm_sync=mock_crm, notify_telegram=True
        )

        assert stats["checked"] == 2
        assert stats["resolved"] == 1
        assert stats["unresolved"] == 1
        mock_at.update_project_fields.assert_called_once_with(
            "recTrx10", {"Sotuvchi": ["recp8ClrBsXi6G0Km"]}
        )
        assert mock_alert.call_count == 2


@pytest.mark.asyncio
async def test_supervise_skips_pre_september_records():
    mock_at = MagicMock()
    mock_at.get_transactions.return_value = [
        {
            "id": "recOldTrx",
            "fields": {
                "Sana": "2026-08-31",
                "Turi": "Kirim",
                "Tranzaksiya": "Kirim - Eski",
                "Summa UZS": 1000000,
            },
        },
        {
            "id": "recSeptTrx",
            "fields": {
                "Sana": "2026-09-05",
                "Turi": "Kirim",
                "Tranzaksiya": "Kirim - Sentabr",
                "Summa UZS": 2000000,
                "Izoh": "Ahrorbek",
            },
        },
    ]
    mock_at.update_project_fields.return_value = True
    mock_crm = AsyncMock()

    with patch("src.services.core.finance.income_supervisor._dispatch_supervisor_alert"):
        stats = await supervise_recent_incomes(
            airtable_sync=mock_at, amocrm_sync=mock_crm, notify_telegram=False
        )

        assert stats["checked"] == 1
        assert stats["resolved"] == 1
        mock_at.update_project_fields.assert_called_once_with(
            "recSeptTrx", {"Sotuvchi": ["recp8ClrBsXi6G0Km"]}
        )


@pytest.mark.asyncio
async def test_supervise_persistent_dedup_anti_spam(tmp_path):
    mock_at = MagicMock()
    mock_at.get_transactions.return_value = [
        {
            "id": "recSpamTrx",
            "fields": {
                "Sana": "2026-09-24",
                "Turi": "Kirim",
                "Tranzaksiya": "Kirim - Noma'lum",
                "Summa UZS": 8000000,
                "Izoh": "Izohda sotuvchi yo'q",
            },
        }
    ]
    mock_crm = AsyncMock()
    mock_crm.search_leads.return_value = []

    test_alert_file = str(tmp_path / "test_alerted.json")
    with patch("src.services.core.finance.income_supervisor._ALERT_STORE_PATH", test_alert_file), \
         patch("src.services.core.finance.income_supervisor._ALERTED_RECORD_IDS", set()), \
         patch("src.services.core.finance.income_supervisor._dispatch_supervisor_alert") as mock_alert:
        
        # 1st run: alerts once
        stats1 = await supervise_recent_incomes(airtable_sync=mock_at, amocrm_sync=mock_crm, notify_telegram=True)
        assert stats1["unresolved"] == 1
        assert mock_alert.call_count == 1

        # 2nd run: MUST NOT alert again (anti-spam check)
        stats2 = await supervise_recent_incomes(airtable_sync=mock_at, amocrm_sync=mock_crm, notify_telegram=True)
        assert stats2["unresolved"] == 1
        assert mock_alert.call_count == 1  # Still 1, NOT 2!

