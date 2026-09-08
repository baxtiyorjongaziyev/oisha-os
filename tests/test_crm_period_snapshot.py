from datetime import date

from src.services.core.crm.daily_report.models import PeriodType, PeriodMetrics, ManagerRow
from src.services.core.crm.daily_report.reporter import CRMDailyReporter


def _reporter(tmp_path):
    class _Amo:
        base_url = "https://x.amocrm.ru"
    return CRMDailyReporter(amocrm=_Amo(), db_path=str(tmp_path / "r.db"))


def _m(ptype, start, end, **kw):
    return PeriodMetrics(period_type=ptype, period_start=start, period_end=end, **kw)


def test_save_and_load_roundtrip(tmp_path):
    r = _reporter(tmp_path)
    m = _m(PeriodType.WEEKLY, date(2026, 9, 1), date(2026, 9, 7),
           new_leads=12, won_count=5, won_amount=45_000_000,
           managers=[ManagerRow(user_id=1, name="Oydin", won_count=3)])
    r.save_snapshot(m)
    got = r.load_snapshot(PeriodType.WEEKLY, date(2026, 9, 1))
    assert got == m


def test_load_missing_returns_none(tmp_path):
    r = _reporter(tmp_path)
    assert r.load_snapshot(PeriodType.MONTHLY, date(2020, 1, 1)) is None


def test_save_is_idempotent_on_primary_key(tmp_path):
    r = _reporter(tmp_path)
    r.save_snapshot(_m(PeriodType.DAILY, date(2026, 9, 7), date(2026, 9, 7), new_leads=1))
    r.save_snapshot(_m(PeriodType.DAILY, date(2026, 9, 7), date(2026, 9, 7), new_leads=9))
    got = r.load_snapshot(PeriodType.DAILY, date(2026, 9, 7))
    assert got.new_leads == 9


def test_list_snapshots_desc_by_start(tmp_path):
    r = _reporter(tmp_path)
    for day in (5, 6, 7):
        r.save_snapshot(_m(PeriodType.DAILY, date(2026, 9, day), date(2026, 9, day), new_leads=day))
    rows = r.list_snapshots(PeriodType.DAILY, limit=2)
    assert [x.period_start.day for x in rows] == [7, 6]
