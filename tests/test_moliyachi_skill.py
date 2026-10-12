from types import SimpleNamespace

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
