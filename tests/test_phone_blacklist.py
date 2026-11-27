"""Tests for global amoCRM and call-analysis phone blacklist."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.services.core.crm.phone_blacklist import is_excluded_phone


@pytest.mark.parametrize(
    "phone",
    [
        "+998701641197",
        "+998977373717",
        "+998905632360",
        "+998977781004",
        "+998 50 200 72 76",
        "998502007276",
        "502007276",
        "+998905372258",
    ],
)
def test_default_blacklisted_phones_are_blocked(phone: str):
    assert is_excluded_phone(phone) is True


def test_non_blacklisted_phone_is_allowed():
    assert is_excluded_phone("+998901234567") is False
    assert is_excluded_phone("") is False


@pytest.mark.asyncio
async def test_amocrm_create_lead_skips_blacklisted_phone():
    from src.services.core.crm.amocrm.leads_create import AmoCRMLeadsCreateMixin

    class DummyClient(AmoCRMLeadsCreateMixin):
        get_contact_by_phone = MagicMock()
        create_contact = MagicMock()
        create_lead_for_contact = MagicMock()

    client = DummyClient()
    result = await client.create_lead(name="Test", phone="+998 50 200 72 76")
    assert result is None
    client.get_contact_by_phone.assert_not_called()
    client.create_contact.assert_not_called()
    client.create_lead_for_contact.assert_not_called()


@pytest.mark.asyncio
async def test_lead_orchestrator_skips_blacklisted_phone():
    from src.services.core.leads.lead_orchestrator import LeadOrchestrator

    amocrm = MagicMock()
    amocrm.get_contact_by_phone = AsyncMock()
    amocrm.create_lead = AsyncMock()
    orch = LeadOrchestrator(
        amocrm=amocrm,
        airtable=MagicMock(),
        auto_lead=MagicMock(),
        admin_bot=MagicMock(),
    )
    lead_id, is_repeat = await orch._sync_with_amocrm(
        name="Blocked",
        phone="+998977373717",
        user_id=123,
        username="blocked",
        source="telegram",
        lead_details={"intent": "WARM", "summary": "Test"},
    )
    assert lead_id is None
    assert is_repeat is False
    amocrm.get_contact_by_phone.assert_not_called()
    amocrm.create_lead.assert_not_called()
