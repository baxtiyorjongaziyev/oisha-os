# tests/test_rop_weekly.py
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from src.services.core.rop.config import DEFAULTS
from src.services.core.rop.weekly import progress, no_result_streak_days, monday_start, WeeklyProgress
from src.services.core.crm.amocrm_pipeline_config import STATUS_WON

TZ = ZoneInfo("Asia/Tashkent")
CFG = dict(DEFAULTS)

def test_progress_counts_and_pcts():
    leads = [
        {"status_id": STATUS_WON, "price": 12_000_000},
        {"status_id": STATUS_WON, "price": 13_000_000},
        {"status_id": 143, "price": 9_000_000},  # lost — ignored
    ]
    p = progress(leads, CFG)
    assert isinstance(p, WeeklyProgress)
    assert p.won_count == 2
    assert p.won_revenue == 25_000_000
    assert p.sales_target == 10
    assert round(p.sales_pct, 1) == 20.0
    assert round(p.revenue_pct, 1) == 25.0

def test_monday_start_is_monday_midnight():
    wed = datetime(2026, 9, 9, 15, 30, tzinfo=TZ)   # Wednesday
    ms = monday_start(wed)
    assert ms.weekday() == 0 and ms.hour == 0 and ms.minute == 0
    assert (wed - ms).days == 2

def test_no_result_streak_skips_sunday_and_stops_on_hit():
    now = datetime(2026, 9, 10, 18, 0, tzinfo=TZ)   # Thursday
    # Wed and Tue empty, Mon 09-07 has a win -> streak 2
    mon_win = int(datetime(2026, 9, 7, 11, 0, tzinfo=TZ).timestamp())  # Monday
    assert no_result_streak_days([mon_win], now) == 2

def test_no_result_streak_capped_at_7():
    now = datetime(2026, 9, 10, 18, 0, tzinfo=TZ)
    assert no_result_streak_days([], now) == 7
