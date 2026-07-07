from __future__ import annotations

from types import SimpleNamespace

import pytest

import src.services.core.rnp_research as rnp_research


class _Msg:
    def __init__(self, msg_id: int, text: str, date: str = "2026-06-30T09:00:00"):
        self.id = msg_id
        self.message = text
        self.text = text
        self.raw_text = text
        self.date = SimpleNamespace(isoformat=lambda: date)


class _Entity:
    def __init__(self, username: str):
        self.username = username


class _Client:
    def __init__(self):
        self.entities = []

    async def get_entity(self, channel):
        self.entities.append(channel)
        return _Entity(channel)

    async def iter_messages(self, entity, limit=20):
        samples = {
            "tursunovlar_uz": [
                _Msg(1, "Biznesda tizim va intizom eng muhim."), 
                _Msg(2, "Follow-up o'z vaqtida bo'lishi kerak."),
            ],
            "AlisherIsaev_blogi": [
                _Msg(3, "Sotuvni oshirish uchun CRM va tasklar muhim."),
            ],
            "Avazovalisher": [
                _Msg(4, "Brendni kichik signal emas, katta tizim sifatida o'ylang."),
            ],
            "ibrahimGulyamov": [
                _Msg(5, "Katta natija uchun kundalik nazorat kerak."),
            ],
        }
        for msg in samples.get(entity.username, []):
            yield msg


class _Cursor:
    def __init__(self, rows):
        self.rows = rows

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    async def fetchall(self):
        return self.rows


class _Conn:
    def __init__(self, rows):
        self.rows = rows

    def execute(self, query, params=None):
        return _Cursor(self.rows)


class _Db:
    def __init__(self, rows):
        self.rows = rows

    async def get_connection(self):
        return _Conn(self.rows)


class _ResearcherStub:
    def __init__(self, *args, **kwargs):
        self.calls = []

    async def process_task(self, user_id, prompt, context=None):
        self.calls.append((user_id, prompt, context))
        return "Biznesda tizim va follow-up eng ko'p takrorlanmoqda."


class _FrogStub:
    def __init__(self):
        self.calls = []

    async def identify_frog(self, tasks, context=None):
        self.calls.append((tasks, context))
        return SimpleNamespace(
            most_important_task_id=7,
            profit_estimate=1500,
            reason="Kanal signaliga mos eng yuqori foydali vazifa.",
            motivation_message="Bugun shu qurbaqani yeymiz!",
        )


@pytest.mark.asyncio
async def test_rnp_research_collects_channels_and_picks_frog(monkeypatch):
    monkeypatch.setattr(rnp_research, "ResearcherAgent", _ResearcherStub)
    frog_stub = _FrogStub()
    monkeypatch.setattr(rnp_research, "FrogAgent", lambda: frog_stub)

    result = await rnp_research.build_business_research(
        client=_Client(),
        user_id=99,
        db=_Db(
            [
                (7, "Top task", "Need action", 3, 1500),
                (8, "Smaller task", "Later", 1, 300),
            ]
        ),
        channels=[
            "https://t.me/tursunovlar_uz",
            "https://t.me/AlisherIsaev_blogi",
        ],
        limit=3,
    )

    assert len(result["channels"]) == 3
    assert result["frog"]["most_important_task_id"] == 7
    assert "follow-up" in result["summary"].lower()
    assert frog_stub.calls


def test_rnp_report_formats_summary_and_frog():
    report = rnp_research.format_rnp_report(
        {
            "summary": "Takroriy mavzu: tizim va follow-up.",
            "frog": {
                "most_important_task_id": 7,
                "profit_estimate": 1500,
                "reason": "Eng foydali ish.",
                "motivation_message": "Bugun shu qurbaqani yeymiz!",
            },
            "channels": [{"channel": "tursunovlar_uz"}],
        }
    )

    assert "RNP Research" in report
    assert "Qurbaqa" in report
    assert "1500" in report
