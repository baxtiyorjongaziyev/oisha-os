from datetime import date

from src.services.core.crm.daily_report.models import (
    PeriodType,
    period_range,
    previous_range,
    previous_anchor,
)


def test_daily_range_is_single_day():
    assert period_range(PeriodType.DAILY, date(2026, 9, 7)) == (date(2026, 9, 7), date(2026, 9, 7))


def test_weekly_range_is_monday_to_sunday():
    # 2026-09-07 is a Monday
    assert period_range(PeriodType.WEEKLY, date(2026, 9, 9)) == (date(2026, 9, 7), date(2026, 9, 13))


def test_monthly_range_covers_whole_month_incl_dec():
    assert period_range(PeriodType.MONTHLY, date(2026, 12, 15)) == (date(2026, 12, 1), date(2026, 12, 31))


def test_monthly_range_february_non_leap():
    assert period_range(PeriodType.MONTHLY, date(2026, 2, 10)) == (date(2026, 2, 1), date(2026, 2, 28))


def test_previous_daily_is_yesterday():
    assert previous_range(PeriodType.DAILY, date(2026, 9, 7)) == (date(2026, 9, 6), date(2026, 9, 6))


def test_previous_weekly_is_prior_monday_block():
    assert previous_range(PeriodType.WEEKLY, date(2026, 9, 9)) == (date(2026, 8, 31), date(2026, 9, 6))


def test_previous_monthly_wraps_year():
    assert previous_range(PeriodType.MONTHLY, date(2026, 1, 20)) == (date(2025, 12, 1), date(2025, 12, 31))


def test_previous_anchor_is_start_of_previous_period():
    assert previous_anchor(PeriodType.WEEKLY, date(2026, 9, 9)) == date(2026, 8, 31)


from src.services.core.crm.daily_report.models import (
    PeriodMetrics,
    ManagerRow,
    compute_deltas,
)


def _metrics(**kw):
    base = dict(
        period_type=PeriodType.WEEKLY,
        period_start=date(2026, 9, 7),
        period_end=date(2026, 9, 13),
    )
    base.update(kw)
    return PeriodMetrics(**base)


def test_recompute_derived_win_rate_and_avg_deal():
    m = _metrics(won_count=3, lost_count=1, won_amount=30_000_000)
    m.recompute_derived()
    assert m.win_rate == 75.0
    assert m.avg_won_deal == 10_000_000


def test_recompute_derived_handles_zero_denominators():
    m = _metrics(won_count=0, lost_count=0, won_amount=0)
    m.recompute_derived()
    assert m.win_rate == 0
    assert m.avg_won_deal == 0


def test_to_dict_from_dict_roundtrip():
    m = _metrics(new_leads=12, won_count=5, won_amount=45_000_000,
                 managers=[ManagerRow(user_id=1, name="Oydin", won_count=3, won_amount=27_000_000)])
    restored = PeriodMetrics.from_dict(m.to_dict())
    assert restored == m
    assert restored.managers[0].name == "Oydin"


def test_compat_properties():
    m = _metrics(new_leads=9, won_count=4, lost_count=2, won_amount=8_000_000)
    assert m.total_leads == 9
    assert m.won == 4
    assert m.lost == 2
    assert m.revenue == 8_000_000
    assert m.date_label == "Sep 13, 2026"


def test_compute_deltas_subtracts_numeric_fields():
    cur = _metrics(new_leads=12, won_count=5)
    prev = _metrics(new_leads=9, won_count=7)
    d = compute_deltas(cur, prev)
    assert d["new_leads"] == 3
    assert d["won_count"] == -2
    assert "managers" not in d
    assert "period_type" not in d


def test_compute_deltas_none_previous_is_empty():
    assert compute_deltas(_metrics(), None) == {}
