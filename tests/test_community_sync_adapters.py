from datetime import datetime
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, MagicMock

from src.services.core.community_sync.adapters.amocrm import AmoAdapter
from src.services.core.community_sync.adapters.google import GoogleAdapter
from src.services.core.community_sync.adapters.telegram import TelegramAdapter, drip
from src.services.core.community_sync.merge import Change
from src.services.core.community_sync.models import Person


def ali(**kw):
    d = dict(key="tg:1", tg_id=1, first_name="Ali", last_name="Valiyev",
             phone="+998901112233", cohorts={"TN7"})
    d.update(kw)
    return Person(**d)


async def test_google_read_maps_by_phone_and_strips_suffix():
    g = MagicMock()
    g.list_all_contacts.return_value = [{
        "resource_name": "people/c1", "display_name": "Ali Valiyev TN4 Gr",
        "given_name": "Ali", "family_name": "Valiyev TN4 Gr", "phones": ["+998 90 111 22 33"],
    }]
    people = {"tg:1": ali()}
    rows = await GoogleAdapter(g).read_all(people)
    assert rows == {"tg:1": {"first_name": "Ali", "last_name": "Valiyev", "phone": "+998901112233"}}
    assert people["tg:1"].ext["google"] == "people/c1"


async def test_google_create_uses_label_and_suffix():
    g = MagicMock()
    g.list_all_contacts.return_value = []
    g.create_person.return_value = "people/c9"
    a = GoogleAdapter(g)
    people = {"tg:1": ali()}
    await a.read_all(people)
    res = await a.apply([Change("google", "tg:1", "first_name", "Ali")], people)
    g.create_person.assert_called_once_with("Ali", "Valiyev TN7 Gr", ["+998901112233"], ["TEZ NATIJA 7"])
    assert res["ok"] == 1 and people["tg:1"].ext["google"] == "people/c9"


async def test_existing_other_suffix_kept_on_update():
    g = MagicMock()
    g.list_all_contacts.return_value = [{
        "resource_name": "people/c1", "display_name": "Ali Valiyev TN4 Gr",
        "given_name": "Ali", "family_name": "Valiyev TN4 Gr", "phones": [],
    }]
    g.update_person.return_value = True
    a = GoogleAdapter(g)
    people = {"tg:1": ali(phone="", ext={"google": "people/c1"}, cohorts={"TN7", "TN4"})}
    await a.read_all(people)
    await a.apply([Change("google", "tg:1", "cohorts", "TN4,TN7")], people)
    g.update_person.assert_called_once_with("people/c1", "Ali", "Valiyev TN4 Gr", [])
    g.add_to_group.assert_any_call("people/c1", "TEZ NATIJA 7")


async def test_telegram_apply_enqueues():
    store = MagicMock(enqueue_tg=AsyncMock())
    a = TelegramAdapter(client=MagicMock(), store=store)
    await a.apply([Change("telegram", "tg:1", "first_name", "Ali")], {"tg:1": ali(username="ali")})
    store.enqueue_tg.assert_awaited_once_with("tg:1", "ali", "+998901112233")


async def test_floodwait_defers():
    from telethon.errors import FloodWaitError

    store = MagicMock(
        due_tg=AsyncMock(return_value=[{"key": "tg:1", "username": "ali", "phone": ""},
                                       {"key": "tg:2", "username": "b", "phone": ""}]),
        mark_tg=AsyncMock(),
    )
    err = FloodWaitError(request=None, capture=3600)
    client = AsyncMock(side_effect=err)
    client.get_input_entity = AsyncMock(return_value=NS())
    now = datetime(2026, 11, 17, 10)
    res = await drip(store, client, {"tg:1": ali(), "tg:2": ali(key="tg:2")}, 120, now)
    store.mark_tg.assert_awaited_once()
    args = store.mark_tg.await_args.args
    assert args[0] == "tg:1" and args[1] == "deferred" and (args[2] - now).total_seconds() == 3600
    assert (res["ok"], res["deferred"]) == (0, 2)


async def test_amocrm_create_and_skip_empty():
    amo = MagicMock()
    amo.get_contact_by_phone.return_value = None
    amo.create_contact.return_value = 55
    a = AmoAdapter(amo)
    people = {"tg:1": ali(), "tg:2": ali(key="tg:2", first_name="", last_name="", phone="")}
    await a.read_all(people)
    res = await a.apply([Change("amocrm", "tg:1", "phone", "+998901112233"),
                         Change("amocrm", "tg:2", "username", "x")], people)
    amo.create_contact.assert_called_once_with("Ali Valiyev TN7 Gr", "+998901112233")
    assert people["tg:1"].ext["amocrm"] == "55" and res["ok"] == 1
