"""Tests for chat-context phone enrichment into amoCRM contact cards."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.services.core.crm.amocrm.chats import AmoCRMChatsMixin
from src.services.core.crm.tg_amo_bridge.automerge import TelegramDealAutoMerger


class _FakeChatsClient(AmoCRMChatsMixin):
    def __init__(self, details: dict | None = None, patch_status: int = 200):
        self.base_url = "https://example.amocrm.ru"
        self.access_token = "tok"
        self._contact_details_cache = {101: (9999999999.0, details)} if details else {}
        self._details = details
        self._patch_status = patch_status
        self.patched: list[tuple[str, dict]] = []

    async def get_contact_details_async(self, contact_id: int, *, cache_ttl_seconds: int = 300):
        return self._details

    async def _authed_request(self, request_fn, url: str, **kwargs):
        self.patched.append((url, kwargs.get("json", {})))
        resp = MagicMock()
        resp.status_code = self._patch_status
        return resp


@pytest.mark.asyncio
async def test_add_phone_to_contact_async_appends_and_preserves_existing():
    client = _FakeChatsClient(
        details={
            "id": 101,
            "custom_fields_values": [
                {"field_code": "PHONE", "values": [{"value": "+998901112233", "enum_code": "WORK"}]}
            ],
        }
    )
    ok = await client.add_phone_to_contact_async(101, "998508815028")
    assert ok is True
    assert len(client.patched) == 1
    url, payload = client.patched[0]
    assert url.endswith("/api/v4/contacts/101")
    vals = payload["custom_fields_values"][0]["values"]
    assert vals == [
        {"value": "+998901112233", "enum_code": "WORK"},
        {"value": "+998508815028", "enum_code": "MOB"},
    ]
    assert 101 not in client._contact_details_cache


@pytest.mark.asyncio
async def test_add_phone_to_contact_async_is_idempotent_when_phone_exists():
    client = _FakeChatsClient(
        details={
            "id": 101,
            "custom_fields_values": [
                {"field_code": "PHONE", "values": [{"value": "+998508815028", "enum_code": "MOB"}]}
            ],
        }
    )
    ok = await client.add_phone_to_contact_async(101, "+998 50 881 50 28")
    assert ok is True
    assert client.patched == []


@pytest.mark.asyncio
async def test_automerge_enriches_existing_contact_when_phone_shared_in_chat():
    crm = MagicMock()
    crm.find_contacts_by_phone_async = AsyncMock(return_value=[])
    crm.get_contact_chats = AsyncMock(
        return_value=[{"contact_id": 555, "entity_type": "lead", "entity_id": 777}]
    )
    crm.get_contact_details_async = AsyncMock(
        return_value={"id": 555, "name": "I.S", "custom_fields_values": []}
    )
    crm.add_phone_to_contact_async = AsyncMock(return_value=True)
    crm.add_lead_note_async = AsyncMock(return_value=True)

    store = MagicMock()
    store.get_chat_link = AsyncMock(
        return_value={"tg_user_id": 9001, "amo_chat_id": "chat-uuid-1", "phone": None}
    )
    store.upsert_chat_link = AsyncMock()

    merger = TelegramDealAutoMerger(crm=crm, amojo=None, store=store)
    outcome = await merger.ensure_chat_linked_before_send(
        peer_id=9001,
        client_name="I.S",
        sender_phone=None,
        message_text="+998508815028 Shu nomerdan gaplashgandik",
        username="isomiddinovnaasss",
    )

    assert outcome.status == "phone_enriched"
    assert outcome.phone == "998508815028"
    assert outcome.target_contact_id == 555
    assert outcome.target_lead_id == 777
    crm.add_phone_to_contact_async.assert_awaited_once_with(555, "+998508815028")
    crm.add_lead_note_async.assert_awaited_once()
    store.upsert_chat_link.assert_awaited_once()


@pytest.mark.asyncio
async def test_automerge_enriches_contact_by_username_when_no_chat_id():
    crm = MagicMock()
    crm.find_contacts_by_phone_async = AsyncMock(return_value=[])
    crm.find_contacts_by_query_async = AsyncMock(
        return_value=[
            {
                "id": 888,
                "name": "I.S @isomiddinovnaasss",
                "custom_fields_values": [],
                "_embedded": {"leads": [{"id": 999}]},
            }
        ]
    )
    crm.get_contact_details_async = AsyncMock(
        return_value={"id": 888, "name": "I.S @isomiddinovnaasss", "custom_fields_values": []}
    )
    crm.add_phone_to_contact_async = AsyncMock(return_value=True)
    crm.add_lead_note_async = AsyncMock(return_value=True)

    store = MagicMock()
    store.get_chat_link = AsyncMock(return_value=None)
    store.upsert_chat_link = AsyncMock()

    merger = TelegramDealAutoMerger(crm=crm, amojo=None, store=store)
    outcome = await merger.ensure_chat_linked_before_send(
        peer_id=9002,
        client_name="I.S",
        sender_phone=None,
        message_text="Mening raqamim +998508815028",
        username="isomiddinovnaasss",
    )

    assert outcome.status == "phone_enriched"
    assert outcome.target_contact_id == 888
    assert outcome.target_lead_id == 999
    crm.add_phone_to_contact_async.assert_awaited_once_with(888, "+998508815028")
