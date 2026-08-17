"""Murabbiylik hisobotlari jadval bo'yicha ishga tushishi."""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.schedulers.background_monitor import BackgroundMonitor


@pytest.fixture()
def monitor():
    mon = BackgroundMonitor(
        msg_controller=SimpleNamespace(db=SimpleNamespace()),
        client=SimpleNamespace(send_message=AsyncMock()),
        settings=SimpleNamespace(TOPIC_REPORTS_ID=None),
    )
    mon._notify_admin = AsyncMock()
    mon._send_to_group_or_admin = AsyncMock()
    return mon


@pytest.mark.asyncio
async def test_daily_report_is_sent(monitor, monkeypatch):
    async def fake_report(self, day_iso):
        return f"HISOBOT {day_iso}"

    monkeypatch.setattr(
        "src.services.core.sales_quality_coach.SalesQualityCoach.generate_daily_report",
        fake_report,
    )

    await monitor._job_call_quality_daily(datetime(2026, 7, 21, 20, 0))

    monitor._send_to_group_or_admin.assert_awaited_once()
    assert "HISOBOT 2026-07-21" in monitor._send_to_group_or_admin.call_args[0][0]


@pytest.mark.asyncio
async def test_daily_report_sent_once_per_day(monitor, monkeypatch):
    """Monitor har 5 daqiqada aylanadi — hisobot takrorlanmasligi kerak."""

    async def fake_report(self, day_iso):
        return "HISOBOT"

    monkeypatch.setattr(
        "src.services.core.sales_quality_coach.SalesQualityCoach.generate_daily_report",
        fake_report,
    )
    now = datetime(2026, 7, 21, 20, 0)

    await monitor._job_call_quality_daily(now)
    await monitor._job_call_quality_daily(now)

    assert monitor._send_to_group_or_admin.await_count == 1


@pytest.mark.asyncio
async def test_no_data_means_no_message(monitor, monkeypatch):
    """Baholangan qo'ng'iroq bo'lmasa — bo'sh xabar yubormaymiz."""

    async def empty(self, day_iso):
        return None

    monkeypatch.setattr(
        "src.services.core.sales_quality_coach.SalesQualityCoach.generate_daily_report",
        empty,
    )

    await monitor._job_call_quality_daily(datetime(2026, 7, 21, 20, 0))

    monitor._send_to_group_or_admin.assert_not_awaited()


@pytest.mark.asyncio
async def test_coach_error_does_not_kill_monitor(monitor, monkeypatch):
    async def boom(self, day_iso):
        raise RuntimeError("db down")

    monkeypatch.setattr(
        "src.services.core.sales_quality_coach.SalesQualityCoach.generate_daily_report",
        boom,
    )

    # Istisno tashqariga chiqmaydi — monitor sikli to'xtamaydi.
    await monitor._job_call_quality_daily(datetime(2026, 7, 21, 20, 0))

    monitor._send_to_group_or_admin.assert_not_awaited()


@pytest.mark.asyncio
async def test_weekly_sends_script_and_suggestions(monitor, monkeypatch):
    async def fake_script(self):
        return "IDEAL SKRIPT"

    async def fake_suggestions(self):
        return "TAKLIFLAR"

    monkeypatch.setattr(
        "src.services.core.sales_quality_coach.SalesQualityCoach.generate_ideal_script",
        fake_script,
    )
    monkeypatch.setattr(
        "src.services.core.sales_quality_coach.SalesQualityCoach.suggest_playbook_improvements",
        fake_suggestions,
    )

    await monitor._job_call_quality_weekly(datetime(2026, 7, 20, 10, 0))

    sent = " ".join(call[0][0] for call in monitor._notify_admin.call_args_list)
    assert "IDEAL SKRIPT" in sent
    assert "TAKLIF" in sent
    # Playbook o'zgarmasligi ochiq aytiladi
    assert "Tasdiqlashingiz uchun" in sent


@pytest.mark.asyncio
async def test_weekly_skips_when_db_missing(monkeypatch):
    mon = BackgroundMonitor(
        msg_controller=SimpleNamespace(db=None),
        client=SimpleNamespace(send_message=AsyncMock()),
    )
    mon._notify_admin = AsyncMock()

    await mon._job_call_quality_weekly(datetime(2026, 7, 20, 10, 0))

    mon._notify_admin.assert_not_awaited()


def test_scheduler_loop_registers_both_jobs():
    """`run()` sikliga ulanganini tekshiramiz — aks holda hech qachon ishlamaydi."""
    import inspect

    from src.schedulers import background_monitor

    src = inspect.getsource(background_monitor.BackgroundMonitor.run)

    assert "_job_call_quality_daily" in src
    assert "_job_call_quality_weekly" in src
    assert "now.hour == 20" in src  # kunlik 20:00
    assert "now.weekday() == 0" in src  # haftalik dushanba


@pytest.mark.asyncio
async def test_send_to_group_uses_bot_client_when_available():
    bot_client = SimpleNamespace(send_message=AsyncMock())
    user_client = SimpleNamespace(send_message=AsyncMock())
    mon = BackgroundMonitor(
        msg_controller=SimpleNamespace(db=SimpleNamespace()),
        client=user_client,
        bot_client=bot_client,
        TN5_GROUP_ID=-100999,
        settings=SimpleNamespace(OWNER_ID=150074828, TOPIC_REPORTS_ID=7),
    )

    await mon._send_to_group_or_admin("Test message", reply_to=7)

    bot_client.send_message.assert_awaited_once_with(
        -100999, "Test message", message_thread_id=7
    )
    user_client.send_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_notify_admin_uses_bot_client_when_available():
    bot_client = SimpleNamespace(send_message=AsyncMock())
    user_client = SimpleNamespace(send_message=AsyncMock())
    mon = BackgroundMonitor(
        msg_controller=SimpleNamespace(db=SimpleNamespace()),
        client=user_client,
        bot_client=bot_client,
        settings=SimpleNamespace(OWNER_ID=150074828),
    )

    await mon._notify_admin("Admin alert")

    bot_client.send_message.assert_awaited_once_with(
        150074828, "Admin alert"
    )
    user_client.send_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_crm_daily_report_dispatches_via_bot_client(monkeypatch):
    bot_client = SimpleNamespace(send_message=AsyncMock())
    user_client = SimpleNamespace(send_message=AsyncMock())
    mon = BackgroundMonitor(
        msg_controller=SimpleNamespace(db=SimpleNamespace(), crm=SimpleNamespace(amocrm=SimpleNamespace())),
        client=user_client,
        bot_client=bot_client,
        TN5_GROUP_ID=-100888,
        settings=SimpleNamespace(OWNER_ID=150074828, TOPIC_REPORTS_ID=12),
    )

    class FakeStats:
        date_label = "Aug 17, 2026"
        total_leads = 5
        contacted = 3
        qualified = 2
        won = 1
        revenue = 500
        incoming_calls = 0
        avg_response_sec = 0
        top_manager = None
        pipeline_value = 1000

    class FakeReporter:
        def __init__(self, amocrm=None):
            pass
        async def fetch_stats(self):
            return FakeStats()
        def _load_prev_stats(self):
            return None
        def format_report(self, stats, prev):
            return f"AmoCRM Kunlik Hisobot | 📅 {stats.date_label}\nSent via Oisha-OS"

    monkeypatch.setattr("src.services.core.crm.crm_daily_report.CRMDailyReporter", FakeReporter)

    await mon._job_crm_daily_report(datetime(2026, 8, 17, 19, 30))

    bot_client.send_message.assert_awaited_once()
    sent_args = bot_client.send_message.call_args
    assert sent_args[0][0] == -100888
    assert "AmoCRM Kunlik Hisobot" in sent_args[0][1]
    assert sent_args[1]["message_thread_id"] == 12
    user_client.send_message.assert_not_awaited()
