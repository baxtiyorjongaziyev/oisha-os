from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

import src.schedulers.daily_insights_scheduler as sched
from src.services.core.crm.amocrm_pipeline_config import STATUS_WON
from src.services.core.rop.config import DEFAULTS
from src.services.core.rop.insights import (
    build_insights, collect, find_at_risk, render, working_days_left,
)
from src.services.core.rop.targets import SellerTarget

TZ = ZoneInfo("Asia/Tashkent")
WED_9 = datetime(2026, 9, 9, 9, 15, tzinfo=TZ)
DAY = 86400


def _seller(uid, name):
    return SellerTarget(uid, name, None, 1, 10, 20, 2, 0, 1, 0)


ROSTER = [_seller(1, "Rayxon"), _seller(2, "Aziz")]
CONFIG = dict(DEFAULTS)


def _lead(lid, uid, price, idle_days):
    return {"id": lid, "name": f"Lead{lid}", "responsible_user_id": uid,
            "price": price, "status_id": 0,
            "updated_at": int(WED_9.timestamp() - idle_days * DAY)}


def test_working_days_left():
    assert working_days_left(datetime(2026, 9, 7, tzinfo=TZ)) == 6  # Mon
    assert working_days_left(datetime(2026, 9, 12, tzinfo=TZ)) == 1  # Sat
    assert working_days_left(datetime(2026, 9, 13, tzinfo=TZ)) == 0  # Sun


def test_at_risk_needs_silence_plus_gap():
    leads = [
        _lead(1, 1, 5_000_000, 10),   # silent + no task -> risk
        _lead(2, 1, 9_000_000, 1),    # fresh -> ok
        _lead(3, 2, 1_000_000, 10),   # silent but has future task -> ok
    ]
    tasks = {3: [{"complete_till": WED_9.timestamp() + DAY}]}
    risk = find_at_risk(leads, tasks, {1: "Rayxon"}, CONFIG, WED_9)
    assert [r.name for r in risk] == ["Lead1"]
    assert risk[0].owner == "Rayxon"
    assert "keyingi vazifa yo'q" in risk[0].reasons


def test_leaderboard_and_render():
    won = [{"responsible_user_id": 2, "price": 7_000_000, "status_id": STATUS_WON}]
    ins = build_insights(ROSTER, [_lead(1, 1, 5_000_000, 10)], {}, won, won,
                         {1: [{}, {}]}, CONFIG, WED_9)
    assert ins.leaderboard[0].name == "Aziz"
    text = render(ins)
    assert "Kecha (08.09)" in text
    assert "1. Aziz — 1 ta sotuv, 7 000 000 so'm" in text
    assert "Lead1" in text and "4 ish kuni" in text


class FakeFetcher:
    async def fetch_active_sales_leads(self):
        return [_lead(1, 1, 5_000_000, 10)]
    async def fetch_open_tasks_for_leads(self, ids):
        return {}
    async def fetch_won_leads_since(self, since):
        today = int(WED_9.replace(hour=0, minute=0).timestamp())
        return [{"responsible_user_id": 1, "price": 1, "status_id": STATUS_WON,
                 "closed_at": today + 100}]  # closed today -> not "yesterday"
    async def fetch_today_completed_tasks(self, uids, now=None):
        return {}, {}


async def test_collect_excludes_today_wins_from_yesterday():
    ins = await collect(FakeFetcher(), ROSTER, CONFIG, WED_9)
    assert all(r.won == 0 for r in ins.leaderboard)
    assert ins.weekly.won_count == 1


class FakeRepo:
    async def all_config(self): return {}
    async def set_config(self, k, v): pass
    async def list_active_targets(self):
        return [{"responsible_user_id": 1, "seller_name": "Rayxon"}]


class FakeBot:
    def __init__(self): self.sent = []
    async def send_message(self, chat_id, text, parse_mode=None, **kwargs):
        self.sent.append((chat_id, text, kwargs))


async def test_scheduler_gated_and_sends(monkeypatch):
    bot = FakeBot()
    monkeypatch.setenv("ROP_CEO_CHAT_ID", "42")
    monkeypatch.delenv("DAILY_INSIGHTS_ENABLED", raising=False)
    assert not await sched.run_daily_insights(bot, now_fn=lambda: WED_9,
                                              fetcher=FakeFetcher(), repo=FakeRepo())
    monkeypatch.setenv("DAILY_INSIGHTS_ENABLED", "1")
    assert await sched.run_daily_insights(bot, now_fn=lambda: WED_9,
                                          fetcher=FakeFetcher(), repo=FakeRepo())
    assert bot.sent[0][0] == 42 and "kunlik 3 savol" in bot.sent[0][1]


async def test_scheduler_skips_sunday(monkeypatch):
    monkeypatch.setenv("ROP_CEO_CHAT_ID", "42")
    monkeypatch.setenv("DAILY_INSIGHTS_ENABLED", "1")
    sun = datetime(2026, 9, 13, 9, 15, tzinfo=TZ)
    assert not await sched.run_daily_insights(FakeBot(), now_fn=lambda: sun,
                                              fetcher=FakeFetcher(), repo=FakeRepo())


def test_target_destination_defaults(monkeypatch):
    monkeypatch.setenv("ROP_CEO_CHAT_ID", "-1003854308552")
    monkeypatch.delenv("ROP_CEO_TOPIC_ID", raising=False)
    assert sched._target_destination() == (-1003854308552, 115)

    monkeypatch.setenv("ROP_CEO_TOPIC_ID", "200")
    assert sched._target_destination() == (-1003854308552, 200)

    monkeypatch.setenv("ROP_CEO_CHAT_ID", "123456")
    monkeypatch.delenv("ROP_CEO_TOPIC_ID", raising=False)
    assert sched._target_destination() == (123456, None)


async def test_scheduler_sends_to_topic(monkeypatch):
    bot = FakeBot()
    monkeypatch.setenv("ROP_CEO_CHAT_ID", "-1003854308552")
    monkeypatch.setenv("DAILY_INSIGHTS_ENABLED", "1")
    assert await sched.run_daily_insights(bot, now_fn=lambda: WED_9,
                                          fetcher=FakeFetcher(), repo=FakeRepo())
    assert bot.sent[0][0] == -1003854308552
    assert bot.sent[0][2].get("message_thread_id") == 115

