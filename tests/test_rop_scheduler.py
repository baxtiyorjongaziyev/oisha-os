# tests/test_rop_scheduler.py
from datetime import datetime
from zoneinfo import ZoneInfo
import pytest
import src.schedulers.rop_scheduler as sched

TZ = ZoneInfo("Asia/Tashkent")
THU_9 = datetime(2026, 9, 10, 9, 0, tzinfo=TZ)
SUN_9 = datetime(2026, 9, 13, 9, 0, tzinfo=TZ)
THU_2AM = datetime(2026, 9, 10, 2, 0, tzinfo=TZ)


class FakeBot:
    def __init__(self):
        self.sent = []
        self.threads = []

    async def send_message(self, chat_id, text, parse_mode=None, message_thread_id=None):
        self.sent.append((chat_id, text))
        self.threads.append((chat_id, message_thread_id))
        return True


@pytest.fixture(autouse=True)
def _patch_service(monkeypatch):
    class FakeService:
        def __init__(self, *a, **k): pass
        async def run(self, slot): return [(1, "hi"), (2, "yo")]
    monkeypatch.setattr(sched, "_build_service", lambda bot_runtime, now_fn: FakeService())
    monkeypatch.delenv("ROP_SALES_GROUP_ID", raising=False)


@pytest.mark.asyncio
async def test_disabled_by_default(monkeypatch):
    monkeypatch.delenv("ROP_ENABLED", raising=False)
    n = await sched.run_rop_slot("morning", FakeBot(), now_fn=lambda: THU_9)
    assert n == 0


@pytest.mark.asyncio
async def test_enabled_sends(monkeypatch):
    monkeypatch.setenv("ROP_ENABLED", "1")
    monkeypatch.delenv("DISABLE_UNSOLICITED_REPORTS", raising=False)
    bot = FakeBot()
    n = await sched.run_rop_slot("morning", bot, now_fn=lambda: THU_9)
    assert n == 2 and len(bot.sent) == 2


@pytest.mark.asyncio
async def test_enabled_mirrors_ceo_summary_to_sales_group_topic(monkeypatch):
    monkeypatch.setenv("ROP_ENABLED", "1")
    monkeypatch.setenv("ROP_CEO_CHAT_ID", "2")
    monkeypatch.setenv("ROP_SALES_GROUP_ID", "-1003854308552")
    monkeypatch.setenv("ROP_SALES_TOPIC_ID", "115")
    monkeypatch.delenv("DISABLE_UNSOLICITED_REPORTS", raising=False)
    bot = FakeBot()
    n = await sched.run_rop_slot("morning", bot, now_fn=lambda: THU_9)
    assert n == 3
    assert (-1003854308552, 115) in bot.threads


@pytest.mark.asyncio
async def test_sunday_skipped(monkeypatch):
    monkeypatch.setenv("ROP_ENABLED", "1")
    n = await sched.run_rop_slot("morning", FakeBot(), now_fn=lambda: SUN_9)
    assert n == 0


@pytest.mark.asyncio
async def test_quiet_hours_skipped(monkeypatch):
    monkeypatch.setenv("ROP_ENABLED", "1")
    n = await sched.run_rop_slot("morning", FakeBot(), now_fn=lambda: THU_2AM)
    assert n == 0


@pytest.mark.asyncio
async def test_unsolicited_mute_skipped(monkeypatch):
    monkeypatch.setenv("ROP_ENABLED", "1")
    monkeypatch.setenv("DISABLE_UNSOLICITED_REPORTS", "1")
    n = await sched.run_rop_slot("morning", FakeBot(), now_fn=lambda: THU_9)
    assert n == 0
