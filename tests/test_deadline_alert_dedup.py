"""check_airtable_deadlines dedup regressiya testlari.

Bug: dedup faqat yuborilgandan keyin yozilardi — parallel scheduler loop'lar
va restart bir xil "URGENT PROJECT DEADLINE" xabarini spam qilardi.
"""
import datetime
import sys
import types
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import src.services.core.proactive_worker as pw


class FakeDB:
    """Bitta jarayonlar aro umumiy bo'lgan scheduled_jobs jadvali."""

    claims: set = set()

    async def claim_job_run(self, job_name, date_str):
        key = (job_name, date_str)
        if key in FakeDB.claims:
            return False
        FakeDB.claims.add(key)
        return True

    async def release_job_run(self, job_name, date_str):
        FakeDB.claims.discard((job_name, date_str))


@pytest.fixture(autouse=True)
def _clean_state():
    pw._deadline_sent_keys.clear()
    FakeDB.claims.clear()
    yield
    pw._deadline_sent_keys.clear()
    FakeDB.claims.clear()


def _airtable_stub(deadlines):
    sync = MagicMock()
    sync.get_upcoming_deadlines.return_value = deadlines
    module = types.ModuleType("src.services.core.airtable_sync")
    module.AirtableSync = MagicMock(return_value=sync)
    module.AirtableSync._get_field = staticmethod(lambda fields, name: fields.get(name))
    return module


def _run_checks(times, send_mock, deadlines):
    module = _airtable_stub(deadlines)
    with patch.dict(sys.modules, {"src.services.core.airtable_sync": module}), \
            patch.object(pw, "Database", FakeDB), \
            patch.object(pw, "Bot", MagicMock()), \
            patch.object(pw, "send_group_message_with_fallback", send_mock), \
            patch.dict("os.environ", {"BOT_TOKEN": "t"}), \
            patch("src.config.PROJECTS_GROUP_ID", -100, create=True):
        import asyncio

        for now in times:
            with patch.object(pw, "get_local_now", return_value=now):
                asyncio.run(pw.check_airtable_deadlines())


DEADLINES = [{"fields": {"project_name": "Sadiyya cakes - Naming Vip",
                         "stage": "Brief (Kelishuv)", "deadline": "2026-08-28"}}]


def test_repeated_loops_send_only_once_per_slot():
    """5 daqiqalik loop 10:00–10:10 oralig'ida bir necha marta ishlasa ham 1 xabar."""
    send = AsyncMock()
    times = [datetime.datetime(2026, 8, 27, 10, m) for m in (0, 2, 5, 7, 10)]
    _run_checks(times, send, DEADLINES)
    assert send.await_count == 1


def test_restart_does_not_resend():
    """Process restart (in-memory set yo'qoladi) — DB claim baribir to'sadi."""
    send = AsyncMock()
    _run_checks([datetime.datetime(2026, 8, 27, 10, 0)], send, DEADLINES)
    pw._deadline_sent_keys.clear()  # restart simulyatsiyasi
    _run_checks([datetime.datetime(2026, 8, 27, 10, 3)], send, DEADLINES)
    assert send.await_count == 1


def test_two_daily_slots_still_fire():
    send = AsyncMock()
    times = [datetime.datetime(2026, 8, 27, 10, 0), datetime.datetime(2026, 8, 27, 15, 0)]
    _run_checks(times, send, DEADLINES)
    assert send.await_count == 2


def test_failed_send_releases_claim_for_retry():
    send = AsyncMock(side_effect=[RuntimeError("telegram down"), None])
    times = [datetime.datetime(2026, 8, 27, 10, 0), datetime.datetime(2026, 8, 27, 10, 5)]
    _run_checks(times, send, DEADLINES)
    assert send.await_count == 2
    assert ("airtable_deadline_alert_10", "2026-08-27") in FakeDB.claims


def test_outside_window_is_silent():
    send = AsyncMock()
    _run_checks([datetime.datetime(2026, 8, 27, 12, 0)], send, DEADLINES)
    send.assert_not_awaited()
