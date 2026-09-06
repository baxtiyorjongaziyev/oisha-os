import pytest
from unittest.mock import patch, MagicMock

from src.handlers.income_workflow import (
    resolve_income_category,
    resolve_income_account,
    count_income_records_for_project,
    create_income_airtable_record,
    INCOME_CAT_NAMING,
    INCOME_CAT_BRANDING,
    ACC_BANK_UZS,
    ACC_P2P_UZS,
    ACC_NAQD_UZS,
    ACC_NAQD_USD,
)


def test_resolve_income_category():
    assert resolve_income_category("500$ avans Naming uchun", "Brand Pro") == INCOME_CAT_NAMING
    assert resolve_income_category("1000$ avans", "Sadiyya cakes - Naming") == INCOME_CAT_NAMING
    assert resolve_income_category("1000$ avans", "Sadiyya cakes - Rebrending") == INCOME_CAT_BRANDING


def test_resolve_income_account():
    assert resolve_income_account("Naqd", "USD") == ACC_NAQD_USD
    assert resolve_income_account("Naqd", "UZS") == ACC_NAQD_UZS
    assert resolve_income_account("Bank hisobi", "UZS") == ACC_BANK_UZS
    assert resolve_income_account("P2P card", "UZS") == ACC_P2P_UZS
    assert resolve_income_account(None, "USD") == ACC_P2P_UZS


@pytest.mark.asyncio
async def test_count_income_records_for_project():
    mock_records = [
        {"_record_type": "income", "fields": {"Loyiha": ["recProject1"]}},
        {"_record_type": "income", "fields": {"Loyiha nomi": ["recProject1"]}},
        {"_record_type": "income", "fields": {"Loyiha": ["recProject2"]}},
        {"_record_type": "expense", "fields": {"Loyiha": ["recProject1"]}},
    ]

    with patch("src.services.core.airtable_sync.AirtableSync.get_finance_records", return_value=mock_records):
        count1 = await count_income_records_for_project("recProject1")
        count2 = await count_income_records_for_project("recProject2")
        count3 = await count_income_records_for_project("recProject3")

        assert count1 == 2
        assert count2 == 1
        assert count3 == 0


@pytest.mark.asyncio
async def test_create_income_airtable_record_tranzaksiyalar():
    workflow = {
        "project_id": "recProject123",
        "project_name": "Test Project",
        "amount_value": 500,
        "currency": "USD",
        "source_text": "Mijozdan 500$ naqd avans tushdi",
        "project_fields": {"Kurs": 12500},
        "seller_ids": ["recSeller456"],
    }

    mock_sync_instance = MagicMock()
    mock_sync_instance.create_record.return_value = {"id": "recNewTrx", "fields": {}}

    with patch("src.services.core.airtable_sync.AirtableSync") as MockSync:
        MockSync.return_value = mock_sync_instance
        result = await create_income_airtable_record(workflow)

        assert result == {"id": "recNewTrx", "fields": {}}
        MockSync.assert_called_once_with(table_name="Tranzaksiyalar")

        mock_sync_instance.create_record.assert_called_once()
        call_fields = mock_sync_instance.create_record.call_args[0][0]

        assert call_fields["Turi"] == "Kirim"
        assert call_fields["Summa"] == 500
        assert call_fields["Valyuta"] == "USD"
        assert call_fields["Kurs"] == 12500
        assert call_fields["Loyiha"] == ["recProject123"]
        assert call_fields["Holat"] == "Tasdiqlangan"
        assert call_fields["Kategoriya"] == [INCOME_CAT_BRANDING]
        assert call_fields["Hisob"] == [ACC_NAQD_USD]
        assert call_fields["Xodim"] == ["recSeller456"]
        assert "Tranzaksiya" in call_fields
        assert call_fields["Tranzaksiya"].startswith("KIRIM-TG-")
