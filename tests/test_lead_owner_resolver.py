import asyncio

from src.services.core.crm.lead_owner_resolver import (
    canonical_name,
    format_verdict,
    owners_from_tags,
    resolve_owner,
    who_owns,
)
from src.services.core.dispatcher.handlers_lead_owner import extract_query


def _lead(tags=(), lead_id=42, name="Ali aka"):
    return {"id": lead_id, "name": name, "_embedded": {"tags": [{"name": t} for t in tags]}}


def _call(name, ts, dur=60):
    return {"manager_name": name, "created_at": ts, "duration_seconds": dur}


def test_canonical_name_aliases():
    assert canonical_name("Rayxon Abdullayeva") == "Rayxona"
    assert canonical_name("mumtoz") == "Mumtozmaxal"
    assert canonical_name("") == ""


def test_owners_from_tags_prefix_and_plain():
    assert owners_from_tags(["menejer:Rayxona", "Shahnoza", "taqsimot:inhouse"]) == ["Rayxona", "Shahnoza"]
    assert owners_from_tags(["meta-lead", "inhouse"]) == []


def test_tag_wins_and_agrees_with_first_call():
    v = resolve_owner(_lead(["menejer:Shahnoza"]), [_call("Shahnoza", "2026-11-20T10:00")])
    assert v.owner == "Shahnoza" and v.basis == "teg" and not v.disputed


def test_first_real_call_when_no_tag_short_calls_ignored():
    calls = [_call("Rayxona", "2026-11-20T09:00", dur=5), _call("Mumtozmaxal", "2026-11-20T10:00"),
             _call("Rayxona", "2026-11-20T11:00")]
    v = resolve_owner(_lead(), calls)
    assert v.owner == "Mumtozmaxal" and v.basis == "birinchi qoʼngʼiroq"
    assert v.call_counts == {"Mumtozmaxal": 1, "Rayxona": 1}


def test_dispute_when_tag_differs_from_first_caller():
    v = resolve_owner(_lead(["Rayxona"]), [_call("Shahnoza", "2026-11-20T10:00")])
    assert v.owner == "Rayxona" and v.disputed
    assert "Nizo" in format_verdict(v)


def test_dispute_when_two_tags():
    assert resolve_owner(_lead(["Rayxona", "menejer:Shahnoza"]), []).disputed


def test_unknown_owner():
    v = resolve_owner(_lead(), [_call("Sotuvchi", "2026-11-20T10:00")])
    assert v.owner is None and "aniqlanmadi" in format_verdict(v)


def test_format_escapes_html():
    v = resolve_owner(_lead(name="<b>x</b>"), [])
    assert "&lt;b&gt;x" in format_verdict(v)


def test_extract_query():
    assert extract_query("/kimning_lidi 998901234567") == "998901234567"
    assert extract_query("/lid_egasi@OishaBot Ali aka") == "Ali aka"
    assert extract_query("998901234567 kimning lidi?") == "998901234567"
    assert extract_query("salom") == ""


class _Amo:
    def __init__(self):
        self.searched = None

    async def get_lead(self, lead_id):
        return _lead(["menejer:Rayxona"], lead_id=lead_id)

    async def search_leads(self, q, limit=5):
        self.searched = q
        return []


class _Repo:
    async def get_lead_calls(self, lead_id):
        return [_call("Rayxona", "2026-11-20T10:00")]


class _Db:
    intelligence = _Repo()


def test_who_owns_by_link_and_not_found():
    amo = _Amo()
    out = asyncio.run(who_owns(amo, _Db(), "https://x.amocrm.ru/leads/detail/777", "x"))
    assert "Rayxona" in out and "777" in out
    out = asyncio.run(who_owns(amo, None, "Vali"))
    assert "topilmadi" in out and amo.searched == "Vali"
