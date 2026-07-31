from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from src.services.core.telegram_salescoach_runtime import (
    AmoCRMConversationMatcher,
    AmoCRMTaskAdapter,
    TelethonConversationLoader,
)


class AsyncMessages:
    def __init__(self, values):
        self.values = list(values)

    def __aiter__(self):
        self.iterator = iter(self.values)
        return self

    async def __anext__(self):
        try:
            return next(self.iterator)
        except StopIteration as exc:
            raise StopAsyncIteration from exc


@pytest.mark.asyncio
async def test_telethon_loader_preserves_message_ids_and_roles():
    client = SimpleNamespace(
        iter_messages=lambda user_id, limit: AsyncMessages(
            [
                SimpleNamespace(
                    id=12,
                    out=True,
                    raw_text="Menejer javobi",
                    date=datetime(2026, 7, 31, 10, 2, tzinfo=timezone.utc),
                ),
                SimpleNamespace(
                    id=11,
                    out=False,
                    raw_text="Mijoz savoli",
                    date=datetime(2026, 7, 31, 10, 1, tzinfo=timezone.utc),
                ),
                SimpleNamespace(
                    id=10,
                    out=False,
                    raw_text="   ",
                    date=datetime(2026, 7, 31, 10, 0, tzinfo=timezone.utc),
                ),
            ]
        )
    )

    messages = await TelethonConversationLoader(client, limit=50)(555)

    assert [message.id for message in messages] == [11, 12]
    assert [message.role for message in messages] == ["customer", "manager"]


@pytest.mark.asyncio
async def test_crm_matcher_uses_verified_phone_and_active_lead():
    db = SimpleNamespace(
        get_user_info=AsyncMock(
            return_value={"phone": "+998901234567", "username": "client"}
        )
    )
    amocrm = SimpleNamespace(
        get_contact_by_phone=Mock(return_value={"id": 84}),
        get_active_leads_for_contact=Mock(
            return_value=[
                {
                    "id": 42,
                    "responsible_user_id": 777,
                    "status_id": 86076798,
                    "updated_at": 200,
                }
            ]
        ),
    )

    match = await AmoCRMConversationMatcher(db=db, amocrm=amocrm).match(555)

    assert match is not None
    assert match.lead_id == 42
    assert match.contact_id == 84
    assert match.responsible_user_id == 777
    assert match.confidence == 0.95


@pytest.mark.asyncio
async def test_crm_matcher_never_matches_without_verified_phone():
    db = SimpleNamespace(
        get_user_info=AsyncMock(return_value={"phone": "", "username": "client"})
    )
    amocrm = SimpleNamespace(
        get_contact_by_phone=Mock(),
        get_active_leads_for_contact=Mock(),
    )

    match = await AmoCRMConversationMatcher(db=db, amocrm=amocrm).match(555)

    assert match is None
    amocrm.get_contact_by_phone.assert_not_called()


@pytest.mark.asyncio
async def test_task_adapter_translates_existing_amocrm_methods():
    amocrm = SimpleNamespace(
        get_lead=AsyncMock(return_value={"id": 42, "responsible_user_id": 777}),
        get_lead_open_tasks=AsyncMock(return_value=[]),
        add_lead_note=Mock(return_value={"id": 8001}),
        get_lead_notes=AsyncMock(return_value=[]),
        create_task=AsyncMock(return_value={"id": 9001}),
        get_tasks=AsyncMock(
            return_value=[
                {
                    "id": 9001,
                    "entity_id": 42,
                    "responsible_user_id": 777,
                    "text": "Follow-up qiling",
                    "complete_till": 123456,
                }
            ]
        ),
    )
    adapter = AmoCRMTaskAdapter(amocrm)

    task = await adapter.create_task(
        {
            "entity_id": 42,
            "text": "Follow-up qiling",
            "complete_till": 123456,
            "responsible_user_id": 777,
            "params": {"type": "follow_up"},
        }
    )
    fetched = await adapter.get_task(9001)
    note = await adapter.create_note(42, "[OISHA_SALESCOACH]")

    assert task == {"id": 9001}
    assert fetched["id"] == 9001
    assert note == {"id": 8001}
    amocrm.create_task.assert_awaited_once_with(
        element_id=42,
        text="Follow-up qiling",
        complete_till=123456,
        responsible_user_id=777,
    )
