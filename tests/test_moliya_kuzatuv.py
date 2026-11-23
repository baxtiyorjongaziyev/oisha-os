from datetime import datetime

import pytest

from src.schedulers.moliya import kuzatuv

NOW = datetime(2026, 10, 7, 21, 0)


def _tx(name, sana, turi="Chiqim", kat="recKAT1", **extra):
    fields = {
        "Tranzaksiya": name,
        "Sana": sana,
        "Turi": turi,
        "Summa UZS": 100_000,
        "Kategoriya": [kat] if kat else [],
        "Hisob": ["recBANK"],
        "Hujjat": [{"url": "x"}],
        "Hisobot oyi": sana[:7],
    }
    fields.update(extra)
    return {"id": f"rec{name}{sana}", "createdTime": f"{sana}T10:00:00.000Z", "fields": fields}


def test_rule_key_normalizes_digits_and_case():
    assert kuzatuv.rule_key("Taxi 50 000 — Yandex!") == "taxi yandex"
    assert kuzatuv.rule_key("") == ""


def test_learn_rules_keeps_majority_category():
    records = [
        _tx("Ijara ofis", "2026-09-01", kat="recIJARA"),
        _tx("Ijara ofis", "2026-09-15", kat="recIJARA"),
        _tx("Ijara ofis", "2026-09-20", kat="recBOSHQA"),
    ]
    rules = kuzatuv.learn_rules(records)
    assert rules["ijara ofis"]["kategoriya"] == "recIJARA"
    assert rules["ijara ofis"]["count"] == 3


def test_quality_gaps_flag_missing_document_category_and_project():
    rec = _tx("Mijoz to'lovi", "2026-10-07", turi="Kirim", kat=None, Hujjat=[])
    gaps = kuzatuv.quality_gaps(rec["fields"])
    assert "hujjat yo'q" in gaps
    assert "kategoriya yo'q" in gaps
    assert "kirimda loyiha yo'q" in gaps


def test_quality_gaps_flag_report_month_mismatch_and_usd_without_rate():
    rec = _tx("Domen", "2026-10-07", Valyuta="USD", **{"Hisobot oyi": "2026-09"})
    gaps = kuzatuv.quality_gaps(rec["fields"])
    assert "hisobot oyi sanaga mos emas" in gaps
    assert "USD kursi yo'q" in gaps


@pytest.mark.asyncio
async def test_report_measures_prediction_agreement_without_inventing_numbers():
    history = [_tx("Ijara ofis", "2026-09-01", kat="recIJARA")] * 2
    today = [
        _tx("Ijara ofis", "2026-10-07", kat="recIJARA"),   # predicted right
        _tx("Ijara ofis", "2026-10-07", kat="recBOSHQA"),  # predicted wrong
        _tx("Yangi xarajat", "2026-10-07", kat="recIJARA"),  # no rule yet
    ]
    report = await kuzatuv.build_kuzatuv_report(
        NOW,
        records=history + today,
        nomlar={"recIJARA": "Ijara", "recBOSHQA": "Boshqa"},
        observation={"messages": 4, "photos": 1},
    )
    assert "Airtable: <b>3</b> ta yozuv" in report
    assert "Guruhda: <b>4</b> ta xabar" in report
    assert "Taxmin mosligi: <b>1/2</b> (50%)" in report
    assert "Ijara" in report


@pytest.mark.asyncio
async def test_report_says_no_data_instead_of_fake_metrics():
    report = await kuzatuv.build_kuzatuv_report(NOW, records=[], nomlar={}, observation={})
    assert "Airtable: <b>0</b> ta yozuv" in report
    assert "Taxmin mosligi: ma'lumot yo'q" in report
    assert "topilmadi" not in report


def test_observation_day_buckets_late_night_into_previous_day():
    assert kuzatuv.observation_day(datetime(2026, 11, 22, 1, 15)) == "2026-11-21"
    assert kuzatuv.observation_day(datetime(2026, 11, 22, 2, 59)) == "2026-11-21"
    assert kuzatuv.observation_day(datetime(2026, 11, 22, 3, 0)) == "2026-11-22"
    assert kuzatuv.observation_day(datetime(2026, 11, 22, 21, 0)) == "2026-11-22"


@pytest.mark.asyncio
async def test_report_warns_when_photos_exist_without_airtable_records():
    report = await kuzatuv.build_kuzatuv_report(
        NOW, records=[], nomlar={}, observation={"messages": 5, "photos": 2}
    )
    assert "Airtable: <b>0</b> ta yozuv" in report
    assert "Guruhda chek/rasm bor, lekin Airtable yozuvi topilmadi" in report


def test_kuzatuv_runs_at_09_for_yesterday():
    from src.schedulers.moliya.loop import kuzatuv_target

    assert kuzatuv_target(datetime(2026, 11, 23, 9, 0)) == datetime(2026, 11, 22, 9, 0)
    assert kuzatuv_target(datetime(2026, 11, 23, 9, 4)) == datetime(2026, 11, 22, 9, 4)
    assert kuzatuv_target(datetime(2026, 11, 23, 9, 5)) is None
    assert kuzatuv_target(datetime(2026, 11, 22, 21, 0)) is None


@pytest.mark.asyncio
async def test_report_does_not_warn_missing_entries_when_airtable_unavailable(monkeypatch):
    from unittest.mock import AsyncMock

    monkeypatch.setattr(kuzatuv, "read_table_checked", AsyncMock(return_value=([], False)))
    report = await kuzatuv.build_kuzatuv_report(
        NOW, nomlar={}, observation={"messages": 5, "photos": 2}
    )
    assert "Airtable: maʼlumot olinmadi (manba tekshirilmadi)" in report
    assert "Airtable manbasi tekshirilmadi" in report
    assert "Airtable yozuvi topilmadi" not in report
    assert "Airtable: <b>0</b> ta yozuv" not in report


@pytest.mark.asyncio
async def test_read_table_checked_distinguishes_failure_from_verified_success(monkeypatch):
    from types import SimpleNamespace
    from src.schedulers.moliya import helpers

    class _NoCreds:
        def __init__(self, table_name):
            self.api_key = ""
            self.base_id = ""

        def _current_bearer(self):
            return ""

    monkeypatch.setattr("src.services.core.airtable_sync.AirtableSync", _NoCreds)
    assert await helpers.read_table_checked("Tranzaksiyalar") == ([], False)

    class _ServerErr:
        def __init__(self, table_name):
            self.api_key = "tok"
            self.base_id = "app123"
            self.endpoint = "https://example.invalid"

        def _current_bearer(self):
            return "tok"

        def _request(self, method, url, params=None):
            return SimpleNamespace(status_code=500)

    monkeypatch.setattr("src.services.core.airtable_sync.AirtableSync", _ServerErr)
    assert await helpers.read_table_checked("Tranzaksiyalar") == ([], False)

    class _PaginatedOk:
        def __init__(self, table_name):
            self.api_key = "tok"
            self.base_id = "app123"
            self.endpoint = "https://example.invalid"
            self.calls = 0

        def _current_bearer(self):
            return "tok"

        def _request(self, method, url, params=None):
            self.calls += 1
            if self.calls == 1:
                assert params == {"pageSize": 100}
                return SimpleNamespace(
                    status_code=200,
                    json=lambda: {"records": [{"id": "rec1"}], "offset": "p2"},
                )
            assert params == {"pageSize": 100, "offset": "p2"}
            return SimpleNamespace(
                status_code=200,
                json=lambda: {"records": [{"id": "rec2"}]},
            )

    monkeypatch.setattr("src.services.core.airtable_sync.AirtableSync", _PaginatedOk)
    assert await helpers.read_table_checked("Tranzaksiyalar") == (
        [{"id": "rec1"}, {"id": "rec2"}],
        True,
    )


@pytest.mark.asyncio
async def test_observe_mode_counts_finance_group_message_and_stays_silent(monkeypatch):
    from types import SimpleNamespace

    from src.handlers.msg_pipeline import hisobchi

    monkeypatch.delenv("HISOBCHI_AI_AUTO_ENTRY_ENABLED", raising=False)
    seen = []

    async def fake_record(*, has_photo):
        seen.append(has_photo)

    monkeypatch.setattr(kuzatuv, "record_observation", fake_record)
    monkeypatch.setattr(
        "src.services.core.finance.handlers._get_finance_config", lambda: (-100, 1, 2)
    )

    class Client:
        async def get_me(self):
            return SimpleNamespace(id=1)

        async def __call__(self, *_):
            raise AssertionError("observe mode must not send typing/any request")

    event = SimpleNamespace(
        is_private=False, chat_id=-100, out=False,
        message=SimpleNamespace(photo=object(), voice=None),
    )
    handled = await hisobchi.process_hisobchi(
        event, client=Client(), sender=None, message_text="50000 taxi",
        msg_controller=SimpleNamespace(db=None), voice_processor=None, settings=None,
    )
    assert handled is False
    assert seen == [True]
