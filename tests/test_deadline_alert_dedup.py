"""check_airtable_deadlines dedup regressiya testlari.

Bug: dedup faqat yuborilgandan keyin yozilardi — parallel scheduler loop'lar
va restart bir xil "URGENT PROJECT DEADLINE" xabarini spam qilardi.
"""
import datetime
import os
import shutil
import sys
import tempfile
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
def _clean_state(monkeypatch):
    pw._deadline_sent_keys.clear()
    FakeDB.claims.clear()
    # Disk claim'lar test uchun vaqtinchalik katalogda — repo'ga tegmaydi.
    claim_dir = tempfile.mkdtemp(prefix="deadline-claims-")
    monkeypatch.setattr(pw, "_DEADLINE_CLAIM_DIR", claim_dir)
    yield
    shutil.rmtree(claim_dir, ignore_errors=True)
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
    """Process restart (in-memory set yo'qoladi) — disk/DB claim baribir to'sadi."""
    send = AsyncMock()
    _run_checks([datetime.datetime(2026, 8, 27, 10, 0)], send, DEADLINES)
    pw._deadline_sent_keys.clear()  # restart simulyatsiyasi
    _run_checks([datetime.datetime(2026, 8, 27, 10, 3)], send, DEADLINES)
    assert send.await_count == 1


def test_only_once_per_day_across_both_slots():
    """Kuniga BITTA deadline hisoboti. 10:00 va 15:00 oynalari bitta kunlik
    kalitni bo'lishadi — ikkinchi oyna qayta yubormaydi. (Ilgari kuniga 2
    marta edi; ikki oynali kalit + 2 scheduler spam manbai edi.)"""
    send = AsyncMock()
    times = [datetime.datetime(2026, 8, 27, 10, 0), datetime.datetime(2026, 8, 27, 15, 0)]
    _run_checks(times, send, DEADLINES)
    assert send.await_count == 1


def test_failed_send_releases_claim_for_retry():
    send = AsyncMock(side_effect=[RuntimeError("telegram down"), None])
    times = [datetime.datetime(2026, 8, 27, 10, 0), datetime.datetime(2026, 8, 27, 10, 5)]
    _run_checks(times, send, DEADLINES)
    assert send.await_count == 2
    # Kunlik kalit — yuborish muvaffaqiyatidan keyin claim saqlanadi.
    assert ("airtable_deadline_alert_2026-08-27", "2026-08-27") in FakeDB.claims


def test_success_then_next_window_does_not_resend():
    """Regressiya: 27.08 dagi 12 martalik spam. Muvaffaqiyatli yuborishdan
    keyin claim RELEASE QILINMAYDI — keyingi 5-daqiqalik loop qayta yubormaydi."""
    send = AsyncMock()
    times = [datetime.datetime(2026, 8, 27, 17, m) for m in (2, 7, 12, 17, 22, 58)]
    # 17:xx oynadan tashqari — umuman yubormasligi kerak.
    _run_checks(times, send, DEADLINES)
    assert send.await_count == 0

    send2 = AsyncMock()
    times2 = [datetime.datetime(2026, 8, 27, 10, m) for m in (0, 5, 10)]
    _run_checks(times2, send2, DEADLINES)
    assert send2.await_count == 1


def test_restart_without_db_does_not_resend():
    """Turso yiqilgan holat: DB claim ishlamasa ham disk claim restartni to'sadi."""

    class BrokenDB:
        async def claim_job_run(self, *_):
            raise RuntimeError("turso unreachable")

        async def release_job_run(self, *_):
            raise RuntimeError("turso unreachable")

    send = AsyncMock()
    module = _airtable_stub(DEADLINES)
    import asyncio

    with patch.dict(sys.modules, {"src.services.core.airtable_sync": module}), \
            patch.object(pw, "Database", BrokenDB), \
            patch.object(pw, "Bot", MagicMock()), \
            patch.object(pw, "send_group_message_with_fallback", send), \
            patch.dict("os.environ", {"BOT_TOKEN": "t"}), \
            patch("src.config.PROJECTS_GROUP_ID", -100, create=True):
        for minute in (0, 3, 6):
            pw._deadline_sent_keys.clear()  # har safar "yangi process"
            with patch.object(pw, "get_local_now",
                              return_value=datetime.datetime(2026, 8, 27, 10, minute)):
                asyncio.run(pw.check_airtable_deadlines())

    assert send.await_count == 1


def test_stale_claim_files_are_pruned():
    old_file = os.path.join(pw._DEADLINE_CLAIM_DIR, "old_job.lock")
    os.makedirs(pw._DEADLINE_CLAIM_DIR, exist_ok=True)
    open(old_file, "w").close()
    os.utime(old_file, (0, 0))  # 1970 — juda eski
    assert pw._claim_on_disk("airtable_deadline_alert_2026-08-27_2026-08-27") is True
    assert not os.path.exists(old_file)


def test_outside_window_is_silent():
    send = AsyncMock()
    _run_checks([datetime.datetime(2026, 8, 27, 12, 0)], send, DEADLINES)
    send.assert_not_awaited()
