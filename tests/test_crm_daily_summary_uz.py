"""amoBot uslubidagi o'zbekcha kunlik hisobot."""
import asyncio
from datetime import date, datetime
from types import SimpleNamespace

from src.services.core.crm.daily_report import CRMDailyReporter, CRMWeeklyStats


def _stats():
    d = date(2026, 10, 26)
    return CRMWeeklyStats(
        period_start=d, period_end=d,
        active_leads=487, active_amount=181_490_600,
        won_leads=5, won_amount=5_000_000,
        lost_leads=48, lost_amount=24_000_000,
        new_leads=7, new_companies=0, new_contacts=7,
    )


def test_format_daily_summary_uz():
    reporter = CRMDailyReporter.__new__(CRMDailyReporter)
    reporter._crm = SimpleNamespace(base_url="https://jonbranding.amocrm.ru")
    text = reporter.format_daily_summary_uz(_stats())
    assert text.startswith("Bugungi hisobot (26.10.2026)")
    assert ">487</a>" in text
    assert "181 490 600 soʻm" in text
    assert "Sotilmagan bitimlar: <a" in text
    assert "filter_date_from=26.10.2026" in text
    assert "Davrda yaratilgan yangi kontaktlar" in text


def test_scheduler_sends_once(monkeypatch):
    from src.schedulers.main_loop import periodic_reports as pr

    sent = []

    class Bot:
        async def send_message(self, chat, text, **kw):
            sent.append((chat, text, kw))

    class Rep:
        async def fetch_weekly_stats(self, a, b):
            return _stats()

        def format_daily_summary_uz(self, s):
            return "TXT"

    monkeypatch.setattr(pr.m, "bot_runtime", Bot(), raising=False)
    monkeypatch.setattr(pr.settings, "CRM_SALES_REPORT_GROUP_ID", -100, raising=False)
    monkeypatch.setattr(pr.settings, "CRM_SALES_REPORT_TOPIC_ID", None, raising=False)
    task = SimpleNamespace()
    now = datetime(2026, 10, 26, 19, 0)
    for _ in range(2):
        asyncio.run(pr._send_daily_summary(now, task, reporter_factory=Rep))
    assert len(sent) == 1
    assert sent[0][2]["parse_mode"] == "html"
