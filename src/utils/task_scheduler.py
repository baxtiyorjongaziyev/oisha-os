"""AmoCRM task scheduler — working hours va task spreading.

Working hours: 10:00 - 17:00 (Asia/Tashkent, UTC+5)
Working days: Monday - Saturday (0-5)
"""

import logging
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

TASHKENT_OFFSET = timedelta(hours=5)
TASHKENT_TZ = timezone(TASHKENT_OFFSET)

WORK_START_HOUR = 10  # 10:00
WORK_END_HOUR = 17    # 17:00
WORKING_DAYS = set(range(6))  # 0=Monday ... 5=Saturday


def _now_tashkent() -> datetime:
    """Hozirgi vaqt Toshkent bo'yicha."""
    return datetime.now(TASHKENT_TZ)


def _next_working_day(dt: datetime) -> datetime:
    """Keyingi ish kuniga o'tkazish (Dushanba=0 ... Shanba=5)."""
    while dt.weekday() not in WORKING_DAYS:
        dt += timedelta(days=1)
    return dt


def _clamp_to_work_start(dt: datetime) -> datetime:
    """Agar vaqt ish boshlanishidan oldin bo'lsa — ish boshlanishiga o'tkazish."""
    if dt.hour < WORK_START_HOUR:
        dt = dt.replace(hour=WORK_START_HOUR, minute=0, second=0, microsecond=0)
    return dt


def next_work_slot(after: datetime | None = None, minutes_offset: int = 0) -> datetime:
    """Keyingi bo'sh ish vaqti slotini qaytaradi.

    Args:
        after: Qaysi vaqtdan keyin kerak (default: hozir)
        minutes_offset: Qo'shimcha daqiqa qo'shish (task spread uchun)

    Returns:
        Toshkent vaqtidagi keyingi ish sloti (timezone-aware)
    """
    if after is None:
        after = _now_tashkent()
    elif after.tzinfo is None:
        after = after.replace(tzinfo=TASHKENT_TZ)

    # Offset qo'shish
    slot = after + timedelta(minutes=minutes_offset)

    # Agar bugun ish kuni emas — keyingi ish kuniga
    slot = _next_working_day(slot)

    # Ish boshlanishidan oldin bo'lsa — ish boshlanishiga
    slot = _clamp_to_work_start(slot)

    # Agar ish tugashidan keyin bo'lsa — keyingi ish kuniga
    if slot.hour >= WORK_END_HOUR:
        slot = slot + timedelta(days=1)
        slot = _next_working_day(slot)
        slot = slot.replace(hour=WORK_START_HOUR, minute=0, second=0, microsecond=0)

    return slot


def spread_tasks(count: int, base_minutes: int = 30) -> list[datetime]:
    """Bir nechta vazifani ish vaqti ichida tarqatib qo'yadi.

    Args:
        count: Nechta vaqt kerak
        base_minutes: Har bir vazifa orasidagi interval (daqiqa)

    Returns:
        Vaqt ro'yxati (Toshkent vaqti, timezone-aware)
    """
    now = _now_tashkent()
    slots = []
    used_times = set()

    for i in range(count):
        # Har bir keyingi task uchun offset — tarqatish uchun
        offset_minutes = (i * base_minutes) % ((WORK_END_HOUR - WORK_START_HOUR) * 60)

        slot = next_work_slot(after=now, minutes_offset=offset_minutes)

        # Takroriy vaqtni oldini olish
        slot_key = slot.isoformat()
        attempt = 0
        while slot_key in used_times and attempt < 100:
            slot = slot + timedelta(minutes=15)
            if slot.hour >= WORK_END_HOUR:
                slot = next_work_slot(after=slot + timedelta(days=1))
            slot_key = slot.isoformat()
            attempt += 1

        used_times.add(slot_key)
        slots.append(slot)

    return slots


def task_deadline(
    due_in_hours: int = 24,
    after: datetime | None = None,
) -> int:
    """Vazifa uchun deadline (timestamp) hisoblaydi — ish vaqtini hisobga oladi.

    Args:
        due_in_hours: Necha soat ichida bajarilishi kerak
        after: Qaysi vaqtdan hisoblash (default: hozir)

    Returns:
        Unix timestamp (int)
    """
    slot = next_work_slot(after=after, minutes_offset=due_in_hours * 60)
    return int(slot.timestamp())


def is_working_hours() -> bool:
    """Hozir ish vaqtimi?"""
    now = _now_tashkent()
    return now.weekday() in WORKING_DAYS and WORK_START_HOUR <= now.hour < WORK_END_HOUR


def hours_until_work() -> float:
    """Ish boshlanishigacha necha soat qoldi."""
    now = _now_tashkent()
    if is_working_hours():
        return 0.0

    next_start = next_work_slot(after=now)
    delta = next_start - now
    return delta.total_seconds() / 3600
