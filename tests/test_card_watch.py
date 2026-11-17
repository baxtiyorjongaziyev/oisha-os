"""Card watch: detection, Airtable matching, reminder cycle (synthetic test data)."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from src.services.core.card_watch import config
from src.services.core.card_watch.detector import CardSend, extract_amount, find_card
from src.services.core.card_watch.matcher import income_rows, is_paid
from src.services.core.card_watch.scanner import scan_client, scan_manager
from src.services.core.card_watch.service import load_state, run_cycle, send_daily_reports

CARDS = ["5614681918811393", "5614681919485106"]
NOW = datetime(2026, 11, 17, 10, 0, tzinfo=timezone.utc)


def _send(days_ago=3, amount=1_900_000.0, client="TestBrend", chat_id=-100123, mid=7, key="rayxona"):
    return CardSend(key, chat_id, f"{client} | Jon Branding", client, mid,
                    NOW - timedelta(days=days_ago), amount, CARDS[0])


def _income(day, amount, name="KIRIM-TG", turi="Kirim"):
    return {"fields": {"Turi": turi, "Sana": day, "Summa": amount, "Tranzaksiya": name}}


def test_find_card_tolerates_spaces():
    assert find_card("Karta: 5614 6819 1881 1393 Gaziyev", CARDS) == CARDS[0]
    assert find_card("5614-6819-1948-5106", CARDS) == CARDS[1]
    assert find_card("8600 1234 5678 9012", CARDS) is None


@pytest.mark.parametrize("text,expected", [
    ("Summa: 7 640 000 soʻm\n5614681918811393", 7_640_000),
    ("1.9 mln to'lov 5614 6819 1881 1393", 1_900_000),
    ("500 ming oldindan", 500_000),
    ("faqat karta 5614681918811393", None),
])
def test_extract_amount(text, expected):
    assert extract_amount(text) == expected


def test_paid_by_amount_and_name():
    incomes = income_rows([_income("2026-11-15", 1_900_000)])
    assert is_paid(_send(), incomes)
    named = income_rows([_income("2026-11-16", 1, name="TestBrend avans")])
    assert is_paid(_send(amount=None), named)


def test_not_paid_when_income_before_send_or_chiqim():
    incomes = income_rows([
        _income("2026-11-01", 1_900_000),
        _income("2026-11-15", 1_900_000, turi="Chiqim"),
    ])
    assert not is_paid(_send(), incomes)


def test_run_cycle_reminds_once(tmp_path, monkeypatch):
    monkeypatch.setenv("CARD_WATCH_GRACE_DAYS", "2")
    sent = []

    async def sender(text, topic):
        sent.append((text, topic))
        return True

    state = str(tmp_path / "s.json")
    sends = [_send(), _send(days_ago=1, mid=8)]  # second is still within grace
    r1 = asyncio.run(run_cycle(sends, [], sender, now=NOW, state_path=state))
    r2 = asyncio.run(run_cycle(sends, [], sender, now=NOW, state_path=state))
    assert r1["reminded"] == 1 and r2["reminded"] == 0
    assert sent[0][1] == 2976 and "TestBrend" in sent[0][0]


def test_run_cycle_prefers_manager_over_owner(tmp_path):
    sent = []

    async def sender(text, topic):
        sent.append(topic)
        return True

    sends = [_send(key="owner"), _send(key="shahnoza")]
    asyncio.run(run_cycle(sends, [], sender, now=NOW, state_path=str(tmp_path / "s.json")))
    assert sent == [122]


class _Msg(SimpleNamespace):
    async def get_sender(self):
        return SimpleNamespace(username="MumtozmaxalJonbranding")


class _FakeClient:
    def __init__(self, dialogs, messages):
        self._d, self._m = dialogs, messages

    async def iter_dialogs(self, limit=None):
        for d in self._d:
            yield d

    async def iter_messages(self, chat_id, limit=None):
        for m in self._m.get(chat_id, []):
            yield m


def test_scan_client_manager_and_owner_modes():
    t = NOW - timedelta(days=1)
    group = SimpleNamespace(id=-1001, name="Brend | Jon Branding", is_user=False, is_group=True, date=t)
    other = SimpleNamespace(id=-1002, name="Random chat", is_user=False, is_group=True, date=t)
    dm = SimpleNamespace(id=55, name="Ali", is_user=True, is_group=False, date=t, entity=None)
    msgs = {
        -1001: [_Msg(id=1, date=t, out=False, message="5614681918811393 2 mln")],
        -1002: [_Msg(id=2, date=t, out=True, message="5614681918811393")],
        55: [_Msg(id=3, date=t, out=True, message="karta 5614681919485106"),
             _Msg(id=4, date=t, out=False, message="5614681919485106")],
    }
    client = _FakeClient([group, other, dm], msgs)
    since = NOW - timedelta(days=5)
    mgr = asyncio.run(scan_client(client, "rayxona", CARDS, since))
    assert [(s.chat_id, s.message_id) for s in mgr] == [(55, 3)]
    owner = asyncio.run(scan_client(client, "owner", CARDS, since, owner_mode=True,
                                    username_map={"mumtozmaxaljonbranding": "mumtozmaxal"}))
    assert [(s.manager_key, s.client_name, s.amount) for s in owner] == [("mumtozmaxal", "Brend", 2_000_000)]


def test_manager_session_must_differ_from_prod(monkeypatch):
    monkeypatch.setenv("USERBOT_SESSION_STRING", "prod-secret")
    monkeypatch.setenv("CARD_WATCH_SESSION_RAYXONA", "prod-secret")
    mgr = next(m for m in config.load_managers() if m.key == "rayxona")
    assert "prod-secret" not in repr(mgr)
    assert asyncio.run(scan_manager(mgr, 1, "h", CARDS, 7)) == []


def test_config_defaults_and_overrides(monkeypatch):
    monkeypatch.delenv("CARD_WATCH_CARDS", raising=False)
    assert config.load_cards() == CARDS
    monkeypatch.setenv("CARD_WATCH_CARDS", "1111 2222 3333 4444")
    assert config.load_cards() == ["1111222233334444"]
    topics = {m.key: m.topic_id for m in config.load_managers()}
    assert topics == {"shahnoza": 122, "rayxona": 2976, "mumtozmaxal": 120, "hasanboy": 17141}


def test_daily_report_per_manager(tmp_path):
    state = str(tmp_path / "s.json")
    out = []

    async def sender(text, topic):
        out.append((topic, text))
        return True

    incomes = [_income("2026-11-16", 1_900_000)]
    sends = [_send(mid=1), _send(mid=2, amount=5_000_000, key="shahnoza")]
    asyncio.run(run_cycle(sends, incomes, sender, now=NOW, state_path=state))
    st = load_state(state)
    assert {e["manager"] for k, e in st.items() if not k.startswith("_")} == {"rayxona", "shahnoza"}
    out.clear()
    assert asyncio.run(send_daily_reports(sender, "2026-11-17", state)) == 2
    assert asyncio.run(send_daily_reports(sender, "2026-11-17", state)) == 0
    reports = dict(out)
    assert "Toʻlagan: 1" in reports[2976] and "Kutilmoqda: 1" in reports[122]


def test_unknown_sender_goes_to_owner_topic(tmp_path):
    topics = []

    async def sender(text, topic):
        topics.append(topic)
        return True

    asyncio.run(run_cycle([_send(key="owner")], [], sender, now=NOW, state_path=str(tmp_path / "s.json")))
    assert topics == [118]
