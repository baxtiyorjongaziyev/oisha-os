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
    cls_src = inspect.getsource(background_monitor.BackgroundMonitor)

    assert "_job_call_quality_daily" in src
    assert "_job_call_quality_weekly" in src
    assert "_job_hisobchi_daily_roast" not in cls_src
    assert not hasattr(background_monitor.BackgroundMonitor, "_job_hisobchi_daily_roast")
    assert "now.hour == 20" in src  # kunlik 20:00
    assert "now.weekday() == 0" in src  # haftalik dushanba


@pytest.mark.asyncio
async def test_scheduler_loop_sends_no_roast_at_2030(monitor, monkeypatch):
    """20:30 siklida hech qanday roast xabari yuborilmasligini runtime da tekshiramiz."""
    import asyncio

    monkeypatch.setattr(
        "src.time_utils.get_local_now", lambda: datetime(2026, 11, 27, 20, 30)
    )
    monkeypatch.setattr("src.time_utils.is_quiet_hours", lambda _now: False)
    monitor._job_check_stagnation_and_deadlines = AsyncMock()
    monitor._job_check_amocrm_due_tasks = AsyncMock()
    monitor._job_lead_os_cycle = AsyncMock()
    monitor._job_heartbeat = AsyncMock()

    async def _stop_after_one_tick(_seconds):
        raise asyncio.CancelledError

    monkeypatch.setattr(
        "src.schedulers.bg_monitor.monitor.asyncio.sleep", _stop_after_one_tick
    )

    with pytest.raises(asyncio.CancelledError):
        await monitor.run()

    monitor._send_to_group_or_admin.assert_not_awaited()
    monitor._notify_admin.assert_not_awaited()


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
async def test_growth_tips_go_to_training_topic(monkeypatch):
    mon = BackgroundMonitor(
        msg_controller=SimpleNamespace(db=SimpleNamespace()),
        client=SimpleNamespace(send_message=AsyncMock()),
        settings=SimpleNamespace(TOPIC_REPORTS_ID=7, TOPIC_TRAINING_ID=99),
    )
    mon._notify_admin = AsyncMock()
    mon._send_to_group_or_admin = AsyncMock()

    async def fake_report(self, day_iso):
        return "HISOBOT"

    async def fake_tips(self, day_iso):
        return "TAVSIYA"

    base = "src.services.core.sales_quality_coach.SalesQualityCoach."
    monkeypatch.setattr(base + "generate_daily_report", fake_report)
    monkeypatch.setattr(base + "generate_manager_growth_tips", fake_tips)

    await mon._job_call_quality_daily(datetime(2026, 7, 21, 20, 0))

    calls = {c[0][0]: c[1] for c in mon._send_to_group_or_admin.call_args_list}
    assert calls["HISOBOT"]["reply_to"] == 7
    assert calls["TAVSIYA"]["reply_to"] == 99
