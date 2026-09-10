# tests/test_crm_period_formatter.py
from datetime import date

from src.services.core.crm.daily_report.models import PeriodType, PeriodMetrics, ManagerRow
from src.services.core.crm.daily_report.reporter import CRMDailyReporter


def _reporter(tmp_path):
    class _Amo:
        base_url = "https://jonbrandingagency.amocrm.ru"
    return CRMDailyReporter(amocrm=_Amo(), db_path=str(tmp_path / "r.db"))


def _metrics(ptype, start, end, **kw):
    m = PeriodMetrics(period_type=ptype, period_start=start, period_end=end, **kw)
    m.recompute_derived()
    return m


def test_daily_report_heading_and_label(tmp_path):
    r = _reporter(tmp_path)
    m = _metrics(PeriodType.DAILY, date(2026, 9, 7), date(2026, 9, 7), new_leads=12)
    text = r.format_period_report(PeriodType.DAILY, m, None)
    assert "AmoCRM KUNLIK HISOBOT | 07.09.2026" in text
    assert "Yangi bitimlar: 12" in text
    assert "Oisha-OS orqali yuborilgan" in text


def test_weekly_label_range(tmp_path):
    r = _reporter(tmp_path)
    m = _metrics(PeriodType.WEEKLY, date(2026, 9, 1), date(2026, 9, 7))
    text = r.format_period_report(PeriodType.WEEKLY, m, None)
    assert "AmoCRM HAFTALIK HISOBOT | 01.09 - 07.09.2026" in text


def test_monthly_label_uzbek_month(tmp_path):
    r = _reporter(tmp_path)
    m = _metrics(PeriodType.MONTHLY, date(2026, 9, 1), date(2026, 9, 30))
    text = r.format_period_report(PeriodType.MONTHLY, m, None)
    assert "AmoCRM OYLIK HISOBOT | Sentyabr 2026" in text


def test_deltas_render_with_arrows(tmp_path):
    r = _reporter(tmp_path)
    cur = _metrics(PeriodType.DAILY, date(2026, 9, 7), date(2026, 9, 7), new_leads=12, won_count=5)
    prev = _metrics(PeriodType.DAILY, date(2026, 9, 6), date(2026, 9, 6), new_leads=9, won_count=7)
    text = r.format_period_report(PeriodType.DAILY, cur, prev)
    assert "Yangi bitimlar: 12  ▲ +3" in text
    assert "Yutilgan: 5" in text and "▼ -2" in text


def test_empty_sections_still_render_zero(tmp_path):
    r = _reporter(tmp_path)
    m = _metrics(PeriodType.DAILY, date(2026, 9, 7), date(2026, 9, 7))
    text = r.format_period_report(PeriodType.DAILY, m, None)
    assert "Yaratilgan: 0" in text
    assert "Zadachasiz ochiq bitimlar: 0" in text


def test_manager_lines(tmp_path):
    r = _reporter(tmp_path)
    m = _metrics(
        PeriodType.WEEKLY, date(2026, 9, 1), date(2026, 9, 7),
        managers=[
            ManagerRow(user_id=1, name="Oydin", won_count=3, won_amount=27_000_000),
            ManagerRow(user_id=2, name="Jasur", won_count=2, won_amount=18_000_000, open_tasks=7, overdue_tasks=2),
        ],
    )
    text = r.format_period_report(PeriodType.WEEKLY, m, None)
    assert "Oydin" in text and "27 000 000 so'm" in text
    assert "ochiq zadacha: 7" in text and "muddati o'tgan: 2" in text


def test_legacy_two_arg_format_report_still_works(tmp_path):
    r = _reporter(tmp_path)
    from src.services.core.crm.daily_report.models import CRMStats
    s = CRMStats()
    s.date_label = "Sep 07, 2026"
    s.total_leads = 4
    out = r.format_report(s, None)
    assert "Sep 07, 2026" in out
