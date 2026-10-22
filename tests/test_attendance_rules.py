"""Rules engine: grace, kechikish, erta ketish, dam olish, bayram, tungi smena."""
from datetime import date, datetime, time, timezone, timedelta

from src.services.core.attendance import rules as r

TZ = timezone(timedelta(hours=5))  # Toshkent
SHIFT = r.Shift()
POL = r.Policy()
CAL = r.Calendar()
THU = date(2026, 10, 22)  # payshanba


def at(h, m, d=THU):
    return datetime(d.year, d.month, d.day, h, m, tzinfo=TZ)


def test_on_time_and_within_grace():
    assert r.classify_check_in(SHIFT, POL, CAL, at(9, 50)).status == r.ON_TIME
    assert r.classify_check_in(SHIFT, POL, CAL, at(10, 10)).status == r.ON_TIME


def test_late_after_grace_counts_from_shift_start():
    c = r.classify_check_in(SHIFT, POL, CAL, at(10, 25))
    assert c.status == r.LATE and c.minutes_late == 25


def test_early_leave():
    c = r.classify_check_out(SHIFT, POL, CAL, at(18, 30))
    assert c.status == r.EARLY_LEAVE and c.minutes_early == 30
    assert r.classify_check_out(SHIFT, POL, CAL, at(19, 5)).status == r.ON_TIME


def test_weekend_and_holiday():
    sun = date(2026, 10, 25)
    assert r.classify_day_without_check_in(SHIFT, CAL, sun) == r.DAY_OFF
    assert r.is_working_day(SHIFT, date(2026, 10, 24), CAL)  # shanba — ish kuni
    cal = r.Calendar(holidays=frozenset({THU}))
    assert r.classify_day_without_check_in(SHIFT, cal, THU) == r.DAY_OFF
    assert r.classify_check_in(SHIFT, POL, cal, at(10, 0)).status == r.PENDING_REVIEW


def test_absent_and_approved_leave():
    assert r.classify_day_without_check_in(SHIFT, CAL, THU) == r.ABSENT
    cal = r.Calendar(approved_leave=frozenset({THU}))
    assert r.classify_day_without_check_in(SHIFT, cal, THU) == r.APPROVED_LEAVE


def test_utc_input_converted_to_tashkent():
    utc = datetime(2026, 10, 22, 5, 5, tzinfo=timezone.utc)  # 10:05 Toshkent
    assert r.classify_check_in(SHIFT, POL, CAL, utc).status == r.ON_TIME


def test_night_shift_checkout_belongs_to_previous_day():
    night = r.Shift(start=time(22, 0), end=time(6, 0), weekdays=frozenset(range(1, 8)))
    out = at(5, 30, date(2026, 10, 23))
    c = r.classify_check_out(night, POL, CAL, out)
    assert c.work_date == THU and c.status == r.EARLY_LEAVE and c.minutes_early == 30
    c_in = r.classify_check_in(night, POL, CAL, at(22, 15))
    assert c_in.work_date == THU and c_in.status == r.LATE


def test_worked_minutes_and_overtime():
    worked, overtime = r.worked_minutes(SHIFT, at(10, 0), at(20, 0))
    assert worked == 600 and overtime == 60
    assert r.worked_minutes(SHIFT, at(10, 0), at(9, 0)) == (0, 0)


def test_individual_weekdays():
    mumtoz = r.Shift(weekdays=r.parse_weekdays("1,2,4,5,6,7"))  # chorshanba dam, yakshanba ishlaydi
    assert r.classify_day_without_check_in(mumtoz, CAL, date(2026, 10, 21)) == r.DAY_OFF
    assert r.classify_day_without_check_in(mumtoz, CAL, date(2026, 10, 25)) == r.ABSENT
    ahror = r.Shift(weekdays=r.parse_weekdays("1,2,3,4,5,6,7"))
    assert r.classify_check_in(ahror, POL, CAL, at(10, 0, date(2026, 10, 25))).status == r.ON_TIME


def test_optional_sunday_never_absent():
    hasanboy = r.Shift(weekdays=r.parse_weekdays("1,2,3,4,5,6"), optional_weekdays=frozenset({7}))
    sun = date(2026, 10, 25)
    assert r.classify_day_without_check_in(hasanboy, CAL, sun) == r.DAY_OFF
    assert r.classify_check_in(hasanboy, POL, CAL, at(10, 5, sun)).status == r.ON_TIME
    assert not r.is_required_day(hasanboy, sun, CAL)
