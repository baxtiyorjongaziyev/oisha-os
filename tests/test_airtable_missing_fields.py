from datetime import date, datetime

from src.schedulers.airtable_missing_fields_scheduler import should_send
from src.services.core.airtable.missing_fields import (
    NO_PM_KEY,
    collect_gaps,
    format_message,
)

TODAY = date(2026, 11, 24)
TEAM = {"recPM1": "Hasanboy", "recPM2": "Dilbar"}
FULL = {"Sotuvchi": ["recS"], "Dizayner soatlari": 5, "PM va Muloqot soatlari": 2, "Pravkalar soni": 1}


def _rec(rid, **fields):
    return {"id": rid, "fields": fields}


def test_groups_missing_by_pm_and_skips_complete_and_old():
    projects = [
        _rec("r1", **{"Loyiha nomi": "A", "PM": ["recPM1"], "Dizayner soatlari": 3}),
        _rec("r2", **{"Loyiha nomi": "B", "PM": ["recPM2"], **FULL}),
        _rec("r3", **{"Loyiha nomi": "C", "PM": ["recPM2"], "END sana": "2026-01-01"}),
        _rec("r4", **{"Loyiha nomi": "D"}),
    ]
    report = collect_gaps(projects, TEAM, TODAY)
    assert set(report.by_pm) == {"Hasanboy", NO_PM_KEY}
    gap = report.by_pm["Hasanboy"][0]
    assert gap.name == "A"
    assert "Sotuvchi" in gap.missing and "Dizayner soatlari" not in gap.missing
    assert report.total == 2


def test_format_message_mentions_pm_and_unassigned_block():
    projects = [
        _rec("r1", **{"Loyiha nomi": "A<b>", "PM": ["recPM1"]}),
        _rec("r4", **{"Loyiha nomi": "D"}),
    ]
    text = format_message(collect_gaps(projects, TEAM, TODAY), "appX")
    assert "<b>Hasanboy</b>" in text
    assert "PM tayinlanmagan" in text
    assert "A&lt;b&gt;" in text
    assert "https://airtable.com/appX/" in text


def test_format_message_none_when_no_gaps():
    projects = [_rec("r2", **{"Loyiha nomi": "B", "PM": ["recPM2"], **FULL})]
    assert format_message(collect_gaps(projects, TEAM, TODAY), "appX") is None


def test_should_send_window_and_once_per_day():
    tue_10 = datetime(2026, 11, 24, 10, 5)
    assert should_send(tue_10, None)
    assert not should_send(tue_10, tue_10.date())
    assert not should_send(datetime(2026, 11, 24, 10, 45), None)
    assert not should_send(datetime(2026, 11, 29, 10, 5), None)  # yakshanba
