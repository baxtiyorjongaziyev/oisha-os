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
