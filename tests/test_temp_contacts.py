from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.services.core.telegram import temp_contacts
from src.services.core.telegram.temp_contacts import (
    delete_temp_contact,
    import_temp_contact,
)


def _names(client):
    return [call.args[0].__class__.__name__ for call in client.await_args_list]


@pytest.mark.asyncio
async def test_import_skips_known_contact_so_name_is_not_overwritten():
    client = AsyncMock()
    client.get_entity = AsyncMock(return_value=SimpleNamespace(id=9))
    user, newly_imported = await import_temp_contact(client, "998773220098")
    assert user.id == 9
    assert newly_imported is False
    client.assert_not_awaited()


@pytest.mark.asyncio
async def test_import_marks_existing_contact_as_not_new():
    client = AsyncMock(
        return_value=SimpleNamespace(users=[SimpleNamespace(id=5)], imported=[])
    )
    client.get_entity = AsyncMock(side_effect=ValueError("not found"))
    user, newly_imported = await import_temp_contact(client, "+998901234567")
    assert user.id == 5
    assert newly_imported is False


@pytest.mark.asyncio
async def test_import_new_contact():
    client = AsyncMock(
        return_value=SimpleNamespace(
            users=[SimpleNamespace(id=6)], imported=[SimpleNamespace(user_id=6)]
        )
    )
    client.get_entity = AsyncMock(side_effect=ValueError("not found"))
    user, newly_imported = await import_temp_contact(client, "998901234567")
    assert newly_imported is True
    request = client.await_args.args[0]
    assert request.contacts[0].first_name == temp_contacts.TEMP_CONTACT_NAME
    assert request.contacts[0].phone == "998901234567"


@pytest.mark.asyncio
async def test_delete_retries_then_succeeds():
    client = AsyncMock(side_effect=[RuntimeError("flood"), None])
    assert await delete_temp_contact(client, 77, delay=0) is True
    assert _names(client) == ["DeleteContactsRequest", "DeleteContactsRequest"]


@pytest.mark.asyncio
async def test_delete_gives_up_after_attempts():
    client = AsyncMock(side_effect=RuntimeError("down"))
    assert await delete_temp_contact(client, 77, attempts=2, delay=0) is False
    assert client.await_count == 2


@pytest.mark.asyncio
async def test_delete_noop_without_id():
    client = AsyncMock()
    assert await delete_temp_contact(client, None) is True
    client.assert_not_awaited()
