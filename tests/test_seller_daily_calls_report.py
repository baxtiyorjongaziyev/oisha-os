import asyncio
from datetime import datetime

from src.schedulers import seller_daily_calls_report as mod

CALLS = [
    # kiruvchi (0), javob berildi
    {"user_account": "rayxona@jonbranding.uz", "direction": 0, "answered": 1, "duration": 117},
    # chiquvchi (1), javob berildi
    {"user_account": "Rayxona@jonbranding.uz", "direction": 1, "answered": 1, "duration": 1409},
    # chiquvchi, javobsiz
    {"user_account": "rayxona@jonbranding.uz", "direction": 1, "answered": 0, "duration": 30},
    # boshqa sotuvchi
    {"user_account": "shahnoza@jonbranding.uz", "direction": 1, "answered": 1, "duration": 60},
]


def test_aggregate_splits_directions():
    s = mod.aggregate(CALLS, ["rayxona@jonbranding.uz"])
    assert (s.all.total, s.all.answered, s.all.missed) == (3, 2, 1)
    assert (s.incoming.total, s.incoming.answered) == (1, 1)
    assert (s.outgoing.total, s.outgoing.answered, s.outgoing.missed) == (2, 1, 1)
    assert s.all.talk_sec == 117 + 1409  # javobsiz davomiylik hisoblanmaydi
    rows = mod.table_rows(s)
    assert rows[3] == ["Davomiylik", "00:25:26", "00:01:57", "00:23:29"]


class FakeClient:
    def __init__(self):
        self.sent = []

    async def send_rich_message(self, chat_id, rich, message_thread_id=None):
        self.sent.append((chat_id, message_thread_id, rich))
        return {"ok": True}


def test_sends_each_rep_to_own_topic(monkeypatch):
    monkeypatch.delenv("REMOTE_CHECKIN_TOPIC_ID", raising=False)
    monkeypatch.delenv("REMOTE_CHECKIN_GROUP_ID", raising=False)
    client = FakeClient()
    reps = [
        {"key": "rayxon", "name": "Rayxon", "emails": ["rayxona@jonbranding.uz"], "topic": 2976},
        {"key": "shahnoza", "name": "Shahnoza", "emails": ["shahnoza@jonbranding.uz"], "topic": 122},
    ]
    n = asyncio.run(
        mod.send_seller_daily_call_reports(
            datetime(2026, 11, 23, 19, 5), client=client, fetch_calls=lambda a, b: CALLS, reps=reps
        )
    )
    assert n == 2
    assert [t for _, t, _ in client.sent] == [2976, 122]


def test_no_credentials_skips(monkeypatch):
    client = FakeClient()
    n = asyncio.run(
        mod.send_seller_daily_call_reports(
            datetime(2026, 11, 23, 19, 5), client=client, fetch_calls=lambda a, b: None
        )
    )
    assert n == 0 and client.sent == []
