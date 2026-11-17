from datetime import datetime
from zoneinfo import ZoneInfo

from src.services.core.attendance import lunch_watch as lw

TZ = ZoneInfo("Asia/Tashkent")


def _ts(h, m):
    return int(datetime(2026, 11, 17, h, m, tzinfo=TZ).timestamp())


END = lw.lunch_end_ts(datetime(2026, 11, 17, 15, 0, tzinfo=TZ))


def _row(eid, name, inside, since, seen):
    return {"employee_id": eid, "name": name, "inside": inside, "outside_since": since, "last_seen": seen}


def test_lunch_end_is_14_local():
    assert END == _ts(14, 0)


def test_nothing_before_grace():
    rows = [_row(1, "Rayxona", 0, _ts(13, 0), _ts(14, 5))]
    assert lw.late_returners(rows, _ts(14, 5), END, 10) == []


def test_flags_outside_since_lunch():
    rows = [
        _row(1, "Rayxona", 0, _ts(13, 0), _ts(14, 55)),
        _row(2, "Shahnoza", 1, None, _ts(14, 55)),        # qaytgan
        _row(3, "Mumtozmaxal", 0, _ts(14, 40), _ts(14, 55)),  # obeddan keyin chiqqan
    ]
    out = lw.late_returners(rows, _ts(15, 0), END, 10)
    assert [(x.name, x.minutes_over, x.stale) for x in out] == [("Rayxona", 60, False)]


def test_left_after_lunch_end_not_flagged():
    rows = [_row(1, "Rayxona", 0, _ts(14, 5), _ts(14, 20))]
    assert lw.late_returners(rows, _ts(14, 20), END, 10) == []


def test_yesterday_state_ignored():
    rows = [_row(1, "Rayxona", 0, _ts(13, 0) - 86400, _ts(13, 0) - 86400)]
    assert lw.late_returners(rows, _ts(15, 0), END, 10) == []


def test_name_html_escaped():
    out = lw.format_alert([lw.LateReturner(1, "Ali <dizayner>", 5, False)])
    assert "&lt;dizayner&gt;" in out


def test_stale_location_marked():
    rows = [_row(1, "Rayxona", 0, _ts(13, 0), _ts(13, 5))]
    out = lw.late_returners(rows, _ts(15, 0), END, 10)
    assert out[0].stale is True
    assert "lokatsiya eski" in lw.format_alert(out)
