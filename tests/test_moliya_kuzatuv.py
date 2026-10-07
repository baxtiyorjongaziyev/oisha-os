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
    assert "Bugun Airtable: <b>3</b> ta yozuv" in report
    assert "Guruhda: <b>4</b> ta xabar" in report
    assert "Taxmin mosligi: <b>1/2</b> (50%)" in report
    assert "Ijara" in report


@pytest.mark.asyncio
async def test_report_says_no_data_instead_of_fake_metrics():
    report = await kuzatuv.build_kuzatuv_report(NOW, records=[], nomlar={}, observation={})
    assert "Bugun Airtable: <b>0</b> ta yozuv" in report
    assert "Taxmin mosligi: ma'lumot yo'q" in report


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
