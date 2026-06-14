from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from src.settings import settings


def get_local_timezone() -> ZoneInfo:
    timezone_name = getattr(settings, "APP_TIMEZONE", "Asia/Tashkent")
    try:
        return ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        return ZoneInfo("Asia/Tashkent")


def get_local_now() -> datetime:
    return datetime.now(get_local_timezone())


def is_quiet_hours(
    now: datetime | None = None, start_hour: int = 23, end_hour: int = 7
) -> bool:
    """23:00–07:00 Tashkent vaqti bo'yicha quiet hours."""
    current = now or get_local_now()
    h = current.hour
    if start_hour == end_hour:
        return True
    if start_hour > end_hour:
        # Yarim tun oshib ketadigan oraliq: 23:00–07:00
        return h >= start_hour or h < end_hour
    return start_hour <= h < end_hour


def is_sunday(now: datetime | None = None) -> bool:
    """Toshkent vaqti bo'yicha Yakshanba kuni (weekday==6)."""
    return (now or get_local_now()).weekday() == 6


def is_friday_tashkent(now: datetime | None = None) -> bool:
    """Toshkent vaqti bo'yicha Juma kuni (weekday==4)."""
    return (now or get_local_now()).weekday() == 4
