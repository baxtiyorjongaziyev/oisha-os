import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from src.schedulers import daily_priority_checkin as sched
from src.services.core.daily_priority import composer, engine, gatherer
from src.services.core.daily_priority import state as st

TZ = timezone(timedelta(hours=5))
NOW = datetime(2026, 11, 17, 9, 30, tzinfo=TZ)  # seshanba

TEAM = [
    {"key": "rayxona", "name": "Rayxona", "user_id": 1, "role": "sales"},
    {"key": "mumtozmaxal", "name": "Mumtozmaxal", "user_id": 2, "role": "sales"},
    {"key": "dilbar", "name": "Dilbar", "user_id": 3, "role": "finance"},
]


class FakeBot:
    def __init__(self):
        self.sent = []

    async def send_message(self, chat_id, text, **_):
        self.sent.append((chat_id, text))


async def no_ai(*_args, **_kwargs):
    raise RuntimeError("AI yoʻq")


def _lead(lead_id, price, status_id, days_idle=0):
    return {
        "id": lead_id, "name": f"Mijoz {lead_id}", "price": price, "status_id": status_id,
        "updated_at": int(NOW.timestamp()) - days_idle * 86400,
    }


async def fake_fetch(pipeline_id, status_id):
    data = {
        88871066: [_lead(10, 5_000_000, 88871066, 3), _lead(11, 9_000_000, 88871066, 1),
                   _lead(12, 1_000_000, 88871066)],
        87609546: [_lead(13, 7_000_000, 87609546)],
        87609550: [_lead(20, 4_000_000, 87609550)],
        86306514: [_lead(21, 6_000_000, 86306514, 10)],
    }
    return data.get(status_id, [])


@pytest.fixture(autouse=True)
def _isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("DAILY_PRIORITY_STATE_FILE", str(tmp_path / "state.json"))
    monkeypatch.setattr("src.services.core.daily_priority.engine.get_team", lambda: TEAM)
    monkeypatch.setattr("src.services.core.daily_priority.team.get_team", lambda: TEAM)


def test_gather_splits_sales_pool_without_duplicates_and_ranks_by_money():
    result = asyncio.run(gatherer.gather_tasks(TEAM, fetch=fake_fetch, now_ts=NOW.timestamp()))
    rayxona = [t["lead_id"] for t in result["rayxona"]]
    mumtoz = [t["lead_id"] for t in result["mumtozmaxal"]]
    assert rayxona[0] == 11 and mumtoz[0] == 13  # eng qimmat ikkitasi birinchi
    assert not set(rayxona) & set(mumtoz)
    assert [t["lead_id"] for t in result["dilbar"]] == [21, 20]


@pytest.mark.parametrize("text,expected", [
    ("Ha, shu", st.STATUS_ACCEPTED),
    ("xop", st.STATUS_ACCEPTED),
    ("Toʻladi, avans oldim", st.STATUS_DONE),
    ("to\x27ladi", st.STATUS_DONE),  # ASCII apostrof bilan yozilgan javob
    ("yo\x27q", st.STATUS_DECLINED),
    ("Yoʻq, bugun Akmal aka bilan uchrashuvim bor", st.STATUS_CHANGED),
    ("Bugun Sardor akaga KP yuboraman", st.STATUS_CHANGED),
])
def test_classify_reply(text, expected):
    assert composer.classify_reply(text) == expected


def test_full_day_flow():
    bot = FakeBot()
    sent = asyncio.run(engine.run_morning(bot, NOW, fetch=fake_fetch, generate=no_ai))
    assert sent == 3
    assert "Mijoz 11" in bot.sent[0][1]  # Rayxonaga aniq bitim taklif qilindi
    # Takror ishga tushsa hech kimga ikkinchi marta ketmaydi.
    assert asyncio.run(engine.run_morning(bot, NOW, fetch=fake_fetch, generate=no_ai)) == 0

    # Rayxona rozi, Dilbar oʻz ishini aytdi, Mumtozmaxal jim.
    reply = asyncio.run(engine.handle_reply(1, "ha", NOW, generate=no_ai))
    assert reply and "Rayxona" in reply
    asyncio.run(engine.handle_reply(3, "Bugun Sharq loyihasidan qarzni undiraman", NOW, generate=no_ai))
    assert asyncio.run(engine.handle_reply(999, "salom", NOW, generate=no_ai)) is None

    later = NOW.replace(hour=11)
    assert asyncio.run(engine.run_nudge(bot, later, generate=no_ai)) == 1  # faqat Mumtozmaxal
    assert asyncio.run(engine.run_nudge(bot, later, generate=no_ai)) == 0

    afternoon = NOW.replace(hour=15, minute=0)
    assert asyncio.run(engine.run_followup(bot, afternoon, generate=no_ai)) == 2  # Rayxona + Dilbar
    asyncio.run(engine.handle_reply(1, "Bajarildi, avans oldim", afternoon, generate=no_ai))

    data = st.load()
    day = NOW.strftime("%Y-%m-%d")
    assert data[day]["rayxona"]["status"] == st.STATUS_DONE
    assert data[day]["dilbar"]["task"].startswith("Bugun Sharq")

    evening = NOW.replace(hour=18, minute=30)
    assert asyncio.run(engine.run_owner_summary(bot, evening, owner_id=42)) is True
    summary = bot.sent[-1][1]
    assert bot.sent[-1][0] == 42
    assert "Bajarildi: 1/3" in summary and "Javob bermaganlar: Mumtozmaxal" in summary
    assert asyncio.run(engine.run_owner_summary(bot, evening, owner_id=42)) is False


def test_morning_mentions_yesterday_commitment():
    bot = FakeBot()
    asyncio.run(engine.run_morning(bot, NOW, fetch=fake_fetch, generate=no_ai))
    captured = {}

    async def spy(prompt, **_):
        captured["prompt"] = prompt
        raise RuntimeError

    tomorrow = NOW + timedelta(days=1)
    asyncio.run(engine.run_morning(FakeBot(), tomorrow, fetch=fake_fetch, generate=spy))
    assert "Kecha" in captured["prompt"]


def test_schedule_slots():
    assert sched.slot_for(NOW) == "morning"
    assert sched.slot_for(NOW.replace(hour=18, minute=30)) == "summary"
    assert sched.slot_for(NOW.replace(minute=31)) is None
    sunday = NOW + timedelta(days=5)
    assert sunday.weekday() == 6 and sched.slot_for(sunday) is None
