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
    now: datetime | None = None, start_hour: int = 0, end_hour: int = 6
) -> bool:
    current = now or get_local_now()
    return start_hour <= current.hour < end_hour
