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
    def __init__(self): self.sent = []
    async def send_message(self, chat_id, text, parse_mode=None):
        self.sent.append((chat_id, text)); return True


@pytest.fixture(autouse=True)
def _patch_service(monkeypatch):
    class FakeService:
        def __init__(self, *a, **k): pass
        async def run(self, slot): return [(1, "hi"), (2, "yo")]
    monkeypatch.setattr(sched, "_build_service", lambda bot_runtime, now_fn: FakeService())

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
