from __future__ import annotations

import datetime
from zoneinfo import ZoneInfo


UZBEKISTAN_TZ = ZoneInfo("Asia/Tashkent")


def get_local_now() -> datetime.datetime:
    return datetime.datetime.now(UZBEKISTAN_TZ)


def is_quiet_hours(now: datetime.datetime | None = None) -> bool:
    current = now or get_local_now()
    return 0 <= current.hour < 6
