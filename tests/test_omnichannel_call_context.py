"""
Unit tests for OmnichannelContext and OmnichannelContextFetcher.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from src.services.call_analytics.omnichannel_context import (
    OmnichannelContext,
    OmnichannelContextFetcher,
)


@pytest.mark.asyncio
async def test_omnichannel_context_formatting():
    ctx = OmnichannelContext(
        lead_id=12345,
        lead_name="Kamila Pardalari",
        price=15000000,
        status_name="Muzokara",
        pipeline_name="Hunter",
        responsible_user="Baxtiyorjon",
        tags=["VIP", "Tekstil"],
        custom_fields={"Xizmat turi": "Brending", "Sfera": "Parda & Tekstil"},
        contact_name="Kamila",
        contact_phone="+998901234567",
        telegram_username="kamila_parda",
        telegram_messages=[
            "[2026-08-28 14:00] Mijoz: Salom, brending narxi qancha?",
            "[2026-08-28 14:05] Menejer: Assalomu alaykum! 3 xil tarifimiz bor.",
        ],
    )

    crm_prompt = ctx.format_crm_prompt_block()
    assert "Kamila Pardalari" in crm_prompt
    assert "15,000,000" in crm_prompt
    assert "Brending" in crm_prompt
    assert "@kamila_parda" in crm_prompt

    tg_prompt = ctx.format_telegram_prompt_block()
    assert "Mijoz: Salom, brending narxi qancha?" in tg_prompt

    note_block = ctx.format_crm_note_block()
    assert "15,000,000" in note_block
    assert "@kamila_parda" in note_block


@pytest.mark.asyncio
async def test_omnichannel_fetcher_integration():
    mock_amocrm = MagicMock()
    mock_amocrm.get_lead_details = AsyncMock(
        return_value={
            "id": 999,
            "name": "Ledir Brand",
            "price": 25000000,
            "status_name": "Kelishildi",
            "pipeline_name": "Closer",
            "tags": [{"name": "Yangi"}, "Optom"],
            "custom_fields_values": [
                {"field_name": "Xizmat turi", "values": [{"value": "Packaging & Logo"}]},
            ],
            "_embedded": {
                "contacts": [{"id": 555}],
            },
        }
    )
    mock_amocrm.get_contact_details = AsyncMock(
        return_value={
            "id": 555,
            "name": "Shoxrux",
            "custom_fields_values": [
                {"field_code": "PHONE", "values": [{"value": "+998931112233"}]},
                {"field_code": "TELEGRAM", "values": [{"value": "@shoxrux_ledir"}]},
            ],
        }
    )

    fetcher = OmnichannelContextFetcher(amocrm=mock_amocrm, tg_client=None, db=None)
    ctx = await fetcher.fetch_lead_omnichannel_context(lead_id=999)

    assert ctx.lead_id == 999
    assert ctx.lead_name == "Ledir Brand"
    assert ctx.price == 25000000
    assert ctx.contact_name == "Shoxrux"
    assert ctx.contact_phone == "+998931112233"
    assert ctx.telegram_username == "shoxrux_ledir"
    assert ctx.custom_fields.get("Xizmat turi") == "Packaging & Logo"
