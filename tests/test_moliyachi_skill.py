from types import SimpleNamespace

import pytest

from src.schedulers.moliya import moliyachi_skill as ms


def _rec(created, turi="Chiqim", hujjat=True, nom="Taxi Yandex", kat="recKat"):
    return {
        "createdTime": created,
        "fields": {
            "Turi": turi,
            "Tranzaksiya": nom,
            "Kategoriya": [kat],
            "Hujjat": [{"url": "x"}] if hujjat else None,
            "Sana": created[:10],
        },
    }


def test_airtable_events_filters_day_and_converts_tz():
    records = [
        _rec("2026-10-12T04:30:00.000Z"),  # 09:30 Toshkent
        _rec("2026-10-11T20:00:00.000Z"),  # 01:00 12-okt
        _rec("2026-10-10T04:30:00.000Z"),  # boshqa kun
    ]
    events = ms.airtable_events(records, "2026-10-12")
    assert [e["t"] for e in events] == ["09:30", "01:00"]
    assert events[0]["a"] == "at_chiqim"


def test_profile_accumulates_sequence_and_is_idempotent():
    events = ms.merge_day(
        [{"t": "09:00", "a": "tg_photo", "topic": "chiqim", "amount": True}],
        [{"t": "09:10", "a": "at_chiqim", "hujjat": False, "gaps": ["hujjat yo'q"]}],
    )
    p = ms.update_profile({}, "2026-10-12", events)
    assert p["transitions"] == {"tg_photo>at_chiqim": 1}
    assert p["first_action"] == {"tg_photo": 1}
    assert p["gaps"] == {"hujjat yo'q": 1}
    assert ms.update_profile(p, "2026-10-12", events) == p


def test_render_skill_says_when_data_is_thin():
    doc = ms.render_skill({}, {})
    assert "Ma'lumot hali yetarli emas" in doc
    assert "Ma'lumot yo'q" in doc


def test_render_skill_lists_steps():
    p = ms.update_profile(
        {}, "2026-10-12",
        [{"t": "09:00", "a": "tg_photo"}, {"t": "09:05", "a": "at_chiqim", "hujjat": True}],
    )
    doc = ms.render_skill(p, {"taxi yandex": {"kategoriya": "recK", "count": 4, "hisob": ""}}, {"recK": "Transport"})
    assert "Guruhga chek/rasm yubordi → Airtable'ga CHIQIM kiritdi" in doc
    assert '"taxi yandex" → Transport' in doc


def test_classify_message():
    assert ms.classify_message(SimpleNamespace(photo=1)) == "tg_photo"
    assert ms.classify_message(SimpleNamespace(photo=None, voice=1)) == "tg_voice"
    assert ms.classify_message(SimpleNamespace()) == "tg_text"


def test_hisobchi_inactive_by_default(monkeypatch):
    from src.schedulers.moliya.loop import hisobchi_active

    monkeypatch.delenv("HISOBCHI_ACTIVE", raising=False)
    assert hisobchi_active() is False
    monkeypatch.setenv("HISOBCHI_ACTIVE", "1")
    assert hisobchi_active() is True


def test_is_moliyachi_by_username(monkeypatch):
    monkeypatch.delenv("MOLIYACHI_TELEGRAM_ID", raising=False)
    monkeypatch.delenv("MOLIYACHI_TELEGRAM_USERNAME", raising=False)
    assert ms.is_moliyachi(5, "jonbranding_finansist")
    assert ms.is_moliyachi(5, "@JonBranding_Finansist")
    assert not ms.is_moliyachi(5, "someone_else")
    monkeypatch.setenv("MOLIYACHI_TELEGRAM_ID", "77")
    assert ms.is_moliyachi(77, "")


def test_gmail_header_parsing_keeps_metadata_only():
    from src.schedulers.moliya.moliyachi_sources import parse_gmail_headers

    raw = (
        b"From: Kapitalbank <noreply@kapitalbank.uz>\r\n"
        b"Subject: Hisob-faktura #12\r\n"
        b"Date: Mon, 12 Oct 2026 05:00:00 +0000\r\n\r\n"
    )
    ev = parse_gmail_headers(raw, direction="in", has_attachment=True)
    assert ev == {
        "day": "2026-10-12", "t": "10:00", "a": "gm_in",
        "kind": "hisob-faktura", "domain": "kapitalbank.uz", "attachment": True,
    }


def test_sheet_revisions_filtered_by_email_and_day():
    from src.schedulers.moliya.moliyachi_sources import revisions_to_events

    revs = [
        {"modifiedTime": "2026-10-12T06:00:00Z", "lastModifyingUser": {"emailAddress": "dilbar@x.uz"}},
        {"modifiedTime": "2026-10-12T07:00:00Z", "lastModifyingUser": {"emailAddress": "boss@x.uz"}},
        {"modifiedTime": "2026-10-11T07:00:00Z", "lastModifyingUser": {"emailAddress": "dilbar@x.uz"}},
    ]
    evs = revisions_to_events(revs, file_name="Kassa.xlsx", day="2026-10-12", email_filter="Dilbar@x.uz")
    assert evs == [{"t": "11:00", "a": "xl_edit", "file": "Kassa.xlsx"}]


def test_skill_includes_mail_and_excel():
    p = ms.update_profile({}, "2026-10-12", [
        {"t": "10:00", "a": "gm_in", "kind": "to'lov", "domain": "bank.uz"},
        {"t": "10:20", "a": "xl_edit", "file": "Kassa.xlsx"},
    ])
    doc = ms.render_skill(p, {})
    assert "Xat keladi: to'lov (bank.uz)" in doc
    assert "Jadval tahrirlaydi: Kassa.xlsx" in doc
    assert "Gmail'ga xat keldi → Excel/Sheets jadvalini tahrirladi" in doc


def test_empty_username_env_falls_back_to_default(monkeypatch):
    monkeypatch.setenv("MOLIYACHI_TELEGRAM_USERNAME", "")
    monkeypatch.delenv("MOLIYACHI_TELEGRAM_ID", raising=False)
    assert ms.moliyachi_username() == "jonbranding_finansist"
    assert not ms.is_moliyachi(5, "someone_else")


def test_distant_events_are_not_steps():
    p = ms.update_profile({}, "2026-10-12", [
        {"t": "09:00", "a": "gm_in"},
        {"t": "14:00", "a": "at_chiqim"},
        {"t": "14:30", "a": "xl_edit"},
    ])
    assert p["transitions"] == {"at_chiqim>xl_edit": 1}


def test_days_are_not_truncated():
    p = {}
    for i in range(95):
        p = ms.update_profile(p, f"d{i:03d}", [{"t": "10:00", "a": "tg_text"}])
    assert len(p["days"]) == 95 and p["hours"]["10"] == 95


def test_sheets_fail_closed_without_editor_email(monkeypatch):
    from src.schedulers.moliya import moliyachi_sources as src

    monkeypatch.setenv("MOLIYACHI_SHEET_IDS", "abc")
    monkeypatch.setenv("MOLIYACHI_EMAIL", "")
    assert src._fetch_sheet_revisions("2026-10-12") == []


def test_render_skill_functions_under_60_lines():
    import inspect

    for fn in (ms.render_skill, ms.update_profile, ms.run_skill_update):
        assert len(inspect.getsource(fn).splitlines()) <= 60, fn.__name__


@pytest.mark.asyncio
async def test_run_skill_update_retries_on_source_failure(monkeypatch):
    from datetime import datetime
    from unittest.mock import AsyncMock
    from src.schedulers.moliya import helpers, moliyachi_sources as src

    monkeypatch.setattr(helpers, "read_table", AsyncMock(return_value=[_rec("2026-10-12T04:30:00.000Z")]))
    monkeypatch.setattr(src, "gmail_events", AsyncMock(return_value=None))
    monkeypatch.setattr(src, "sheet_events", AsyncMock(return_value=[]))
    db = SimpleNamespace(get_state=AsyncMock(return_value={}), set_state=AsyncMock())
    monkeypatch.setattr("src.db.get_db", lambda: db)
    assert await ms.run_skill_update(datetime(2026, 10, 12)) is False
    db.set_state.assert_not_called()
