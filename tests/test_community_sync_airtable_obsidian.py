from types import SimpleNamespace as NS
from unittest.mock import MagicMock

from src.services.core.community_sync.adapters.airtable import AirtableAdapter
from src.services.core.community_sync.adapters.obsidian import ObsidianAdapter, _parse
from src.services.core.community_sync.merge import Change
from src.services.core.community_sync.models import Person


def ali(**kw):
    d = dict(key="tg:1", tg_id=1, first_name="Ali", last_name="Valiyev",
             phone="+998901112233", cohorts={"TN7"})
    d.update(kw)
    return Person(**d)


def _at(records):
    at = MagicMock()
    at._table_url.return_value = "https://api/t"
    calls = []

    def req(method, url, **kw):
        calls.append((method, url, kw))
        if method == "GET":
            return NS(status_code=200, json=lambda: {"records": records})
        return NS(status_code=200, json=lambda: {"id": "recNEW"})

    at._request.side_effect = req
    return at, calls


async def test_airtable_read_matches_phone():
    at, _ = _at([{"id": "rec1", "fields": {"Mijoz ismi": "Ali Valiyev TN7 Gr",
                                           "Telefon raqami": "+998 90 111 22 33"}}])
    people = {"tg:1": ali()}
    rows = await AirtableAdapter(at).read_all(people)
    assert rows == {"tg:1": {"first_name": "Ali", "last_name": "Valiyev", "phone": "+998901112233"}}
    assert people["tg:1"].ext["airtable"] == "rec1"


async def test_airtable_creates_with_canonical_name():
    at, calls = _at([])
    a = AirtableAdapter(at)
    people = {"tg:1": ali()}
    await a.read_all(people)
    res = await a.apply([Change("airtable", "tg:1", "phone", "+998901112233")], people)
    post = [c for c in calls if c[0] == "POST"][0]
    assert post[2]["json"]["fields"] == {"Mijoz ismi": "Ali Valiyev TN7 Gr",
                                         "Telefon raqami": "+998901112233"}
    assert res["ok"] == 1 and people["tg:1"].ext["airtable"] == "recNEW"


async def test_obsidian_writes_card_and_keeps_body(tmp_path):
    a = ObsidianAdapter(tmp_path)
    people = {"tg:1": ali(ext={"google": "people/c1"})}
    assert await a.read_all(people) == {}
    await a.apply([Change("obsidian", "tg:1", "first_name", "Ali")], people)
    card = next((tmp_path / "60-Wiki" / "mijozlar").glob("*.md"))
    card.write_text(card.read_text(encoding="utf-8") + "Qöl yozuv\n", encoding="utf-8")

    b = ObsidianAdapter(tmp_path)
    people = {"tg:1": ali(phone="+998901112244", ext={"google": "people/c1"})}
    rows = await b.read_all(people)
    assert rows["tg:1"]["first_name"] == "Ali"
    await b.apply([Change("obsidian", "tg:1", "phone", "+998901112244")], people)
    meta, body = _parse(card.read_text(encoding="utf-8"))
    assert meta["phone"] == "+998901112244" and meta["google_id"] == "people/c1"
    assert "Qöl yozuv" in body
