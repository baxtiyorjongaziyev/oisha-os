from datetime import datetime
from zoneinfo import ZoneInfo

from src.time_utils import is_quiet_hours


def _dt(hour: int) -> datetime:
    return datetime(2026, 5, 27, hour, 0, tzinfo=ZoneInfo("Asia/Tashkent"))


def test_default_quiet_hours_cover_late_night_to_morning():
    assert is_quiet_hours(_dt(23)) is True
    assert is_quiet_hours(_dt(0)) is True
    assert is_quiet_hours(_dt(6)) is True
    assert is_quiet_hours(_dt(7)) is False
    assert is_quiet_hours(_dt(22)) is False


def test_quiet_hours_support_non_wrapping_window():
    assert is_quiet_hours(_dt(10), start_hour=9, end_hour=18) is True
    assert is_quiet_hours(_dt(18), start_hour=9, end_hour=18) is False
