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


@pytest.mark.asyncio
async def test_admin_lookup_fallback_deletes_newly_imported_contact():
    from src.services.core.admin_bot.lookup import AdminLookupMixin

    class DummyBot(AdminLookupMixin):
        def __init__(self, user_client):
            self.user_client = user_client

    user = SimpleNamespace(id=101, username="u101", first_name="Ali", last_name="Vali")
    client = AsyncMock(
        side_effect=[
            SimpleNamespace(users=[user], imported=[SimpleNamespace(user_id=101)]),
            None,
        ]
    )
    client.get_entity = AsyncMock(side_effect=ValueError("not found"))

    res = await DummyBot(client)._perform_global_lookup_import_fallback("+998901112233")
    assert res == {"user_id": 101, "username": "u101", "first_name": "Ali", "last_name": "Vali"}
    assert _names(client) == ["ImportContactsRequest", "DeleteContactsRequest"]


@pytest.mark.asyncio
async def test_global_phone_lookup_deletes_newly_imported_contact(monkeypatch):
    from src.entrypoint import crm_push

    monkeypatch.setattr(crm_push.app_ctx, "msg_controller", None, raising=False)
    user = SimpleNamespace(id=202, username="u202", first_name="Hasan", last_name="")
    client = AsyncMock(
        side_effect=[
            SimpleNamespace(users=[user], imported=[SimpleNamespace(user_id=202)]),
            None,
        ]
    )
    client.get_entity = AsyncMock(side_effect=ValueError("not found"))

    res = await crm_push.global_phone_lookup("901112233", client=client)
    assert res == {"user_id": 202, "username": "u202", "first_name": "Hasan", "last_name": ""}
    assert _names(client) == ["ImportContactsRequest", "DeleteContactsRequest"]


@pytest.mark.asyncio
async def test_auditor_phone_lookup_deletes_newly_imported_contact():
    from src.services.core.crm.auditor.telegram_history import TelegramHistoryMixin

    class DummyAuditor(TelegramHistoryMixin):
        def __init__(self, tg_client):
            self.tg_client = tg_client

    user = SimpleNamespace(id=303, username="u303")
    client = AsyncMock(
        side_effect=[
            SimpleNamespace(users=[user], imported=[SimpleNamespace(user_id=303)]),
            None,
        ]
    )
    client.get_entity = AsyncMock(side_effect=ValueError("not found"))

    tg_id, uname = await DummyAuditor(client).get_or_lookup_telegram_user("+998901112233", None)
    assert tg_id == 303
    assert uname == "u303"
    assert _names(client) == ["ImportContactsRequest", "DeleteContactsRequest"]


@pytest.mark.asyncio
async def test_omnichannel_hub_send_deletes_temp_contact_even_on_send_error(monkeypatch):
    from src.context import app_ctx
    from src.services.core.crm.omnichannel_hub import OmnichannelHub

    user = SimpleNamespace(id=404, username="u404")
    client = AsyncMock(
        side_effect=[
            SimpleNamespace(users=[user], imported=[SimpleNamespace(user_id=404)]),
            None,
        ]
    )
    client.is_connected = lambda: True
    client.get_entity = AsyncMock(side_effect=ValueError("not found"))
    client.send_message = AsyncMock(side_effect=RuntimeError("send fail"))
    monkeypatch.setattr(app_ctx, "client", client, raising=False)
    monkeypatch.setattr(app_ctx, "bot_runtime", None, raising=False)

    hub = OmnichannelHub.__new__(OmnichannelHub)
    ok = await hub._send_telegram_direct_message("+998901112233", "Salom")
    assert ok is False
    assert _names(client) == ["ImportContactsRequest", "DeleteContactsRequest"]
