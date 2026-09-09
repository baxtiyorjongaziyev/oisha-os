# tests/test_crm_period_scheduler.py
from datetime import datetime

import pytest

from src.services.core.crm.daily_report.models import PeriodType, ReportResult, PeriodMetrics
from src.schedulers.main_loop import periodic_reports as pr


class _Task:
    pass


class _FakeReporter:
    def __init__(self):
        self.built = []

    async def build(self, ptype):
        self.built.append(ptype)
        m = PeriodMetrics(period_type=ptype,
                          period_start=datetime(2026, 9, 7).date(),
                          period_end=datetime(2026, 9, 7).date())
        return ReportResult(ptype, m.period_start, m.period_end, m, None, {}, "TEXT-BODY", True)


class _Bot:
    def __init__(self):
        self.sent = []

    async def send_message(self, chat, text, **kw):
        self.sent.append((chat, text, kw))


@pytest.mark.asyncio
async def test_send_period_report_dispatches_to_sales_group(monkeypatch):
    bot = _Bot()
    rep = _FakeReporter()
    monkeypatch.setattr(pr.m, "bot_runtime", bot, raising=False)
    monkeypatch.setattr(pr.settings, "CRM_SALES_REPORT_GROUP_ID", -1003854308552, raising=False)
    monkeypatch.setattr(pr.settings, "CRM_SALES_REPORT_TOPIC_ID", 115, raising=False)

    await pr._send_period_report(
        PeriodType.WEEKLY, datetime(2026, 9, 7, 9, 0), _Task(),
        reporter_factory=lambda: rep,
    )
    assert rep.built == [PeriodType.WEEKLY]
    assert bot.sent == [(-1003854308552, "TEXT-BODY", {"message_thread_id": 115})]


@pytest.mark.asyncio
async def test_send_period_report_skips_when_group_unset(monkeypatch):
    bot = _Bot()
    monkeypatch.setattr(pr.m, "bot_runtime", bot, raising=False)
    monkeypatch.setattr(pr.settings, "CRM_SALES_REPORT_GROUP_ID", None, raising=False)
    await pr._send_period_report(
        PeriodType.DAILY, datetime(2026, 9, 7, 19, 30), _Task(),
        reporter_factory=lambda: _FakeReporter(),
    )
    assert bot.sent == []


@pytest.mark.asyncio
async def test_send_period_report_is_idempotent_per_day(monkeypatch):
    bot = _Bot()
    rep = _FakeReporter()
    monkeypatch.setattr(pr.m, "bot_runtime", bot, raising=False)
    monkeypatch.setattr(pr.settings, "CRM_SALES_REPORT_GROUP_ID", -1, raising=False)
    monkeypatch.setattr(pr.settings, "CRM_SALES_REPORT_TOPIC_ID", None, raising=False)
    task = _Task()
    for _ in range(2):
        await pr._send_period_report(
            PeriodType.DAILY, datetime(2026, 9, 7, 19, 30), task,
            reporter_factory=lambda: rep,
        )
    assert rep.built == [PeriodType.DAILY]  # built once
    assert len(bot.sent) == 1
