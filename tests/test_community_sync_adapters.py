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
    g.create_person.assert_called_once_with("Ali", "Valiyev TN7 Gr", ["+998901112233"], [])
    g.add_to_group.assert_called_once_with("people/c9", "TEZ NATIJA 7")
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
        get_state=AsyncMock(return_value=None),
        set_state=AsyncMock(),
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


async def test_amocrm_create_and_skip_empty(monkeypatch):
    patch = MagicMock(return_value=NS(status_code=200))
    monkeypatch.setattr("src.services.core.community_sync.adapters.amocrm.requests.patch", patch)
    monkeypatch.setattr("src.services.core.community_sync.adapters.amocrm.requests.get",
                        MagicMock(return_value=NS(status_code=204)))
    amo = MagicMock(base_url="https://x")
    amo.create_contact.return_value = 55
    a = AmoAdapter(amo)
    people = {"tg:1": ali(), "tg:2": ali(key="tg:2", first_name="", last_name="", phone="")}
    await a.read_all(people)
    res = await a.apply([Change("amocrm", "tg:1", "phone", "+998901112233"),
                         Change("amocrm", "tg:2", "username", "x")], people)
    amo.create_contact.assert_called_once_with("Ali Valiyev TN7 Gr", "+998901112233")
    assert people["tg:1"].ext["amocrm"] == "55" and res["ok"] == 1


def _amo_contact(phones, tags=(), name="Ali Valiyev TN7 Gr"):
    return {"id": 7, "name": name,
            "custom_fields_values": [{"field_code": "PHONE", "values": [{"value": x} for x in phones]}],
            "_embedded": {"tags": [{"name": t} for t in tags]}}


async def test_amocrm_patch_appends_phone_and_keeps_tags(monkeypatch):
    patch = MagicMock(return_value=NS(status_code=200))
    monkeypatch.setattr("src.services.core.community_sync.adapters.amocrm.requests.patch", patch)
    monkeypatch.setattr("src.services.core.community_sync.adapters.amocrm.requests.get", MagicMock(
        return_value=NS(status_code=200, json=lambda: _amo_contact(["+998907778899"], tags=["VIP"]))))
    amo = MagicMock(base_url="https://x")
    a = AmoAdapter(amo)
    people = {"tg:1": ali(ext={"amocrm": "7"})}
    await a.read_all(people)
    await a.apply([Change("amocrm", "tg:1", "phone", "+998901112233")], people)
    body = patch.call_args.kwargs["json"]
    vals = [v["value"] for v in body["custom_fields_values"][0]["values"]]
    assert vals == ["+998907778899", "+998901112233"]
    assert [t["name"] for t in body["_embedded"]["tags"]] == ["VIP", "community", "TN7"]
    assert "name" not in body


async def test_amocrm_rejects_unverified_phone_match(monkeypatch):
    body = {"_embedded": {"contacts": [_amo_contact(["+998900000000"])]}}
    monkeypatch.setattr("src.services.core.community_sync.adapters.amocrm.requests.get",
                        MagicMock(return_value=NS(status_code=200, json=lambda: body)))
    amo = MagicMock(base_url="https://x")
    people = {"tg:1": ali()}
    assert await AmoAdapter(amo).read_all(people) == {} and "amocrm" not in people["tg:1"].ext


async def test_amocrm_read_failure_blocks_create(monkeypatch):
    monkeypatch.setattr("src.services.core.community_sync.adapters.amocrm.requests.get",
                        MagicMock(return_value=NS(status_code=500)))
    amo = MagicMock(base_url="https://x")
    a = AmoAdapter(amo)
    people = {"tg:1": ali()}
    await a.read_all(people)
    await a.apply([Change("amocrm", "tg:1", "phone", "+998901112233")], people)
    amo.create_contact.assert_not_called()


async def test_google_list_error_raises():
    import pytest
    g = MagicMock()
    g.list_all_contacts.side_effect = RuntimeError("quota")
    with pytest.raises(RuntimeError):
        await GoogleAdapter(g).read_all({"tg:1": ali()})


async def test_google_locked_name_reported_as_canonical():
    g = MagicMock()
    g.list_all_contacts.return_value = [{
        "resource_name": "people/c1", "display_name": "Ali V TN4 Gr",
        "given_name": "Ali", "family_name": "V TN4 Gr", "phones": ["+998901112233"],
    }]
    rows = await GoogleAdapter(g).read_all({"tg:1": ali(first_name="Alisher")})
    assert rows["tg:1"]["first_name"] == "Alisher"


async def test_amocrm_linked_lookup_error_blocks_patch(monkeypatch):
    patch = MagicMock()
    monkeypatch.setattr("src.services.core.community_sync.adapters.amocrm.requests.get",
                        MagicMock(return_value=NS(status_code=502)))
    monkeypatch.setattr("src.services.core.community_sync.adapters.amocrm.requests.patch", patch)
    a = AmoAdapter(MagicMock(base_url="https://x"))
    people = {"tg:1": ali(ext={"amocrm": "7"})}
    await a.read_all(people)
    await a.apply([Change("amocrm", "tg:1", "phone", "+998901112233")], people)
    patch.assert_not_called()


async def test_telegram_locked_name_not_enqueued():
    users = [NS(id=1, first_name="Ali", last_name="Valiyev TN4 Gr", phone=None)]
    client = AsyncMock(return_value=NS(users=users))
    store = MagicMock(enqueue_tg=AsyncMock())
    a = TelegramAdapter(client=client, store=store)
    people = {"tg:1": ali()}
    rows = await a.read_all(people)
    assert rows["tg:1"]["first_name"] == "Ali"
    await a.apply([Change("telegram", "tg:1", "phone", "+998901112233")], people)
    store.enqueue_tg.assert_not_awaited()


async def test_daily_limit_shared_across_runs():
    import sqlite3  # noqa: F401
    from src.services.core.community_sync.store import SyncStore
    from tests.test_community_sync_store import fake_exec
    store = SyncStore(execute=fake_exec())
    await store.ensure_schema()
    for i in range(3):
        await store.enqueue_tg(f"tg:{i}", f"u{i}", "")
    client = AsyncMock()
    client.get_input_entity = AsyncMock(return_value=NS())
    people = {f"tg:{i}": ali(key=f"tg:{i}", tg_id=i) for i in range(3)}
    now = datetime(2026, 11, 17, 10)
    first = await drip(store, client, people, 1, now)
    second = await drip(store, client, people, 1, now)
    assert (first["ok"], second["ok"]) == (1, 0)


def test_gcontacts_full_phone_compare():
    from src.services.core.gcontacts import _full_digits
    assert _full_digits("+12025550123") != _full_digits("+442025550123")
    assert _full_digits("90 111 22 33") == _full_digits("+998901112233")
