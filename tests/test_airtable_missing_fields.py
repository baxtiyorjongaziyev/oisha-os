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



SENTINEL = -100777


def _patch_projects(monkeypatch, value):
    from src.settings import settings

    monkeypatch.setattr(settings, "PROJECTS_GROUP_ID", value, raising=False)
    monkeypatch.setattr(settings, "CRM_GROUP_ID", -100111, raising=False)


def test_loop_routes_to_configured_projects_group(monkeypatch):
    import asyncio
    from datetime import datetime

    from src.schedulers import airtable_missing_fields_scheduler as sched

    monkeypatch.delenv("AIRTABLE_GAPS_GROUP_ID", raising=False)
    monkeypatch.setenv("AIRTABLE_GAPS_TOPIC_ID", "77")
    _patch_projects(monkeypatch, SENTINEL)
    monkeypatch.setattr(
        "src.services.core.airtable.missing_fields.build_report_message", lambda today: "x"
    )
    monkeypatch.setattr(sched, "get_local_now", lambda: datetime(2026, 11, 24, 10, 5))
    sent = {}

    class Stop(Exception):
        pass

    async def fake_sleep(sec):
        if sent:
            raise Stop

    monkeypatch.setattr(sched.asyncio, "sleep", fake_sleep)

    class Bot:
        async def send_message(self, chat, text, **kw):
            sent.update(chat=chat, **kw)

    try:
        asyncio.run(sched.airtable_missing_fields_loop(Bot(), -1))
    except Stop:
        pass
    assert sent["chat"] == SENTINEL
    assert "message_thread_id" not in sent


def test_crm_equal_projects_group_falls_back(monkeypatch):
    from src.schedulers.airtable_missing_fields_scheduler import resolve_group_id

    monkeypatch.delenv("AIRTABLE_GAPS_GROUP_ID", raising=False)
    _patch_projects(monkeypatch, -100111)
    assert resolve_group_id(-1) == -1003114662117


def test_resolve_group_id_override_and_malformed(monkeypatch):
    from src.schedulers.airtable_missing_fields_scheduler import resolve_group_id

    _patch_projects(monkeypatch, SENTINEL)
    monkeypatch.setenv("AIRTABLE_GAPS_GROUP_ID", "-100555")
    assert resolve_group_id(-1) == -100555
    monkeypatch.setenv("AIRTABLE_GAPS_GROUP_ID", "--5")
    assert resolve_group_id(-1) == SENTINEL


def test_resolve_group_id_default_when_settings_none(monkeypatch):
    from src.schedulers.airtable_missing_fields_scheduler import resolve_group_id

    monkeypatch.delenv("AIRTABLE_GAPS_GROUP_ID", raising=False)
    _patch_projects(monkeypatch, None)
    assert resolve_group_id(-999) == -1003114662117
