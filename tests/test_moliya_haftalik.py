from datetime import date, datetime

import pytest

from src.schedulers.moliya import haftalik

WEEK = date(2026, 11, 16)  # dushanba
TODAY = date(2026, 11, 23)


def _tx(name, sana, turi="Chiqim", kat="recKAT1", summa=100_000, **extra):
    fields = {
        "Tranzaksiya": name,
        "Sana": sana,
        "Turi": turi,
        "Summa UZS": summa,
        "Kategoriya": [kat] if kat else [],
        "Hisob": ["recBANK"],
        "Hujjat": [{"url": "x"}],
        "Hisobot oyi": sana[:7],
        "Loyiha": ["recP"],
    }
    fields.update(extra)
    return {"id": f"rec{name}{sana}", "fields": fields}


def _hisob(nom, joriy, fakt, sana, faol=True):
    return {
        "id": f"rec{nom}",
        "fields": {
            "Hisob nomi": nom,
            "Faol": faol,
            "Valyuta": "UZS",
            "Joriy balans (hisob valyutasida)": joriy,
            "Fakt saldo (hisob valyutasida)": fakt,
            "Fakt saldo sanasi": sana,
        },
    }


def test_target_only_monday_09_returns_previous_week_start():
    assert haftalik.haftalik_target(datetime(2026, 11, 23, 9, 2)) == WEEK
    assert haftalik.haftalik_target(datetime(2026, 11, 23, 10, 0)) is None
    assert haftalik.haftalik_target(datetime(2026, 11, 24, 9, 0)) is None


@pytest.mark.asyncio
async def test_report_aggregates_week_and_flags_empty_workdays():
    records = [
        _tx("Ijara", "2026-11-01"),
        _tx("Ijara", "2026-11-16"),
        _tx("Tolov", "2026-11-17", turi="Kirim", summa=500_000),
        _tx("Taksi", "2026-11-18", Hujjat=None),
        _tx("Eski", "2026-11-10"),
    ]
    hisoblar = [
        _hisob("Kassa", 1_000_000, 900_000, "2026-11-22"),
        _hisob("Bank", 2_000_000, 2_000_000, "2026-11-10"),
    ]
    text = await haftalik.build_haftalik_report(
        WEEK,
        today=TODAY,
        records=records,
        hisoblar=hisoblar,
        nomlar={},
        observations={"2026-11-16": {"messages": 4}},
    )
    assert "Yozuvlar: <b>3</b>" in text
    assert "kirim 500 000" in text and "chiqim 200 000" in text
    assert "Du 11-16: 1 yozuv, 4 xabar" in text
    assert "Ish kunida yozuv yoʻq: Pa, Ju, Sh" in text
    assert "Taxmin mosligi: <b>1/1</b>" in text
    assert "Kamchilikli yozuvlar:</b> 1 ta" in text
    assert "Kassa" in text and "-100 000" in text
    assert "Bank: fakt saldo" in text


@pytest.mark.asyncio
async def test_report_does_not_invent_numbers_when_sources_fail():
    text = await haftalik.build_haftalik_report(
        WEEK,
        today=TODAY,
        records=[],
        records_ok=False,
        hisoblar=[],
        hisoblar_ok=False,
        observations={},
    )
    assert "Tranzaksiyalar: maʼlumot olinmadi" in text
    assert "Hisoblar: maʼlumot olinmadi" in text
    assert "Yozuvlar:" not in text


@pytest.mark.asyncio
async def test_clean_balances_report_ok():
    text = await haftalik.build_haftalik_report(
        WEEK,
        today=TODAY,
        records=[],
        hisoblar=[_hisob("Kassa", 100, 100, "2026-11-22")],
        nomlar={},
        observations={},
    )
    assert "✅ Farq va eskirgan fakt saldo yoʻq" in text
