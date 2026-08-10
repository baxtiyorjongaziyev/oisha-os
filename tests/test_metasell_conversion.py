"""MetaSell konversiya dvigateli testlari.

Asosiy talab: sotuvchiga BALL emas, konversiyani oshiradigan aniq bitta
o'sish nuqtasi ko'rsatilsin — va namuna yetarli bo'lmaganda modul jim
tursin (yolg'on ishonch bilan noto'g'ri maslahat bermasin).
"""

import json

import pytest

from src.services.core.metasell_conversion import (
    MIN_CALLS_FOR_DIAGNOSIS,
    MetaSellConversionEngine,
    diagnose_seller,
)
from src.services.core.sales_playbook import (
    OUTCOME_MEETING,
    OUTCOME_REFUSED,
    OUTCOME_THINKING,
    normalise_outcome,
    outcome_converted,
)


def _call(
    *,
    manager="Aziz",
    score=70,
    outcome=OUTCOME_MEETING,
    stages=None,
    weaknesses=None,
    objections=None,
):
    stages = stages or {
        "salomlashish": 70,
        "ehtiyojlar": 70,
        "qiymat": 70,
        "etirozlar": 70,
        "yakunlash": 70,
        "muloqot_sifati": 70,
    }
    return {
        "manager_name": manager,
        "overall_score": score,
        "scores": json.dumps(stages),
        "outcome": outcome,
        "converted": 1 if outcome_converted(outcome) else 0,
        "weaknesses": json.dumps(weaknesses or []),
        "objections": json.dumps(objections or []),
        "category": "Mijoz",
    }


# ── Natija taksonomiyasi ────────────────────────────────────────────────


@pytest.mark.parametrize(
    "raw,expected_converted",
    [
        (OUTCOME_MEETING, True),
        ("uchrashuv kelishildi", True),
        ("To'lov kelishildi", True),
        ("KP yuborish kelishildi", True),
        (OUTCOME_THINKING, False),
        (OUTCOME_REFUSED, False),
        ("mijoz rad etdi", False),
        ("", False),
        (None, False),
    ],
)
def test_outcome_conversion_mapping(raw, expected_converted):
    assert outcome_converted(raw) is expected_converted


def test_normalise_outcome_falls_back_to_unknown():
    assert normalise_outcome("umuman tushunarsiz matn") == "aniqlanmadi"


# ── Diagnoz ─────────────────────────────────────────────────────────────


def test_diagnosis_needs_minimum_sample():
    rows = [_call() for _ in range(MIN_CALLS_FOR_DIAGNOSIS - 1)]
    result = diagnose_seller("Aziz", rows)

    assert result.has_diagnosis is False
    assert "yetarli emas" in result.reason


def test_diagnosis_finds_stage_that_loses_deals():
    """Yakunlash bosqichi konvertirlangan qo'ng'iroqlarda keskin yuqori —
    demak aynan shu bosqich bitimni hal qilmoqda."""
    strong_close = {
        "salomlashish": 80, "ehtiyojlar": 75, "qiymat": 75,
        "etirozlar": 75, "yakunlash": 90, "muloqot_sifati": 80,
    }
    weak_close = {
        "salomlashish": 80, "ehtiyojlar": 75, "qiymat": 75,
        "etirozlar": 75, "yakunlash": 30, "muloqot_sifati": 80,
    }
    rows = [
        _call(outcome=OUTCOME_MEETING, stages=strong_close, score=82) for _ in range(4)
    ] + [
        _call(outcome=OUTCOME_THINKING, stages=weak_close, score=68) for _ in range(4)
    ]

    result = diagnose_seller("Aziz", rows)

    assert result.has_diagnosis is True
    assert result.growth_stage == "yakunlash"
    assert result.conversion_rate == pytest.approx(50.0)
    assert result.projected_lift > 0
    assert "yakunlash" in result.reason.lower() or "Yakunlash" in result.reason


def test_no_meaningful_gap_reports_honestly():
    """Bosqich ballari bir xil bo'lsa — muammo texnikada emas, buni
    to'g'ridan-to'g'ri aytish kerak, tasodifiy bosqich tanlash emas."""
    rows = [_call(outcome=OUTCOME_MEETING) for _ in range(4)] + [
        _call(outcome=OUTCOME_REFUSED) for _ in range(4)
    ]

    result = diagnose_seller("Aziz", rows)

    assert result.has_diagnosis is False
    assert "sezilarli bosqich farqi yo'q" in result.reason


def test_single_group_falls_back_to_weakest_stage_with_caveat():
    """Hammasi konvertirlangan bo'lsa solishtirish yo'q — eng past bosqich
    ko'rsatiladi, lekin bu dalil emasligi aytiladi."""
    stages = {
        "salomlashish": 90, "ehtiyojlar": 90, "qiymat": 90,
        "etirozlar": 25, "yakunlash": 90, "muloqot_sifati": 90,
    }
    rows = [_call(outcome=OUTCOME_MEETING, stages=stages) for _ in range(8)]

    result = diagnose_seller("Aziz", rows)

    assert result.growth_stage == "etirozlar"
    assert "namuna yetarli emas" in result.reason


def test_weighted_stage_wins_over_raw_gap():
    """E'tirozlar (og'irlik 2.0) va salomlashish (1.0) bir xil farq
    ko'rsatsa — og'irroq bosqich tanlanadi, chunki u pulga yaqinroq."""
    won = {
        "salomlashish": 90, "ehtiyojlar": 70, "qiymat": 70,
        "etirozlar": 90, "yakunlash": 70, "muloqot_sifati": 70,
    }
    lost = {
        "salomlashish": 60, "ehtiyojlar": 70, "qiymat": 70,
        "etirozlar": 60, "yakunlash": 70, "muloqot_sifati": 70,
    }
    rows = [_call(outcome=OUTCOME_MEETING, stages=won) for _ in range(4)] + [
        _call(outcome=OUTCOME_REFUSED, stages=lost) for _ in range(4)
    ]

    result = diagnose_seller("Aziz", rows)

    assert result.growth_stage == "etirozlar"


def test_repeated_weaknesses_and_objections_surface():
    rows = [
        _call(
            outcome=OUTCOME_THINKING,
            weaknesses=["Keyingi qadam belgilanmadi"],
            objections=["qimmat"],
        )
        for _ in range(8)
    ]

    result = diagnose_seller("Aziz", rows)

    assert "Keyingi qadam belgilanmadi" in result.top_weaknesses
    assert "qimmat" in result.top_objections


def test_unscored_calls_are_excluded():
    """Baholanmagan (0 ball) qo'ng'iroq konversiyani sun'iy pasaytirmasin."""
    rows = [_call(outcome=OUTCOME_MEETING) for _ in range(4)] + [
        _call(outcome="aniqlanmadi", score=0) for _ in range(10)
    ]

    result = diagnose_seller("Aziz", rows)

    assert result.total_calls == 4
    assert result.conversion_rate == pytest.approx(100.0)


# ── Guruhlash va hisobot ────────────────────────────────────────────────


def test_diagnose_rows_groups_by_manager_and_ranks_by_conversion():
    rows = (
        [_call(manager="Aziz", outcome=OUTCOME_MEETING) for _ in range(6)]
        + [_call(manager="Bek", outcome=OUTCOME_REFUSED) for _ in range(6)]
    )

    result = MetaSellConversionEngine.diagnose_rows(rows)

    assert [d.manager_name for d in result] == ["Aziz", "Bek"]
    assert result[0].conversion_rate == pytest.approx(100.0)
    assert result[1].conversion_rate == pytest.approx(0.0)


def test_rows_without_manager_are_skipped():
    rows = [_call(manager="", outcome=OUTCOME_MEETING) for _ in range(6)]
    assert MetaSellConversionEngine.diagnose_rows(rows) == []


def test_team_report_flags_high_score_low_conversion():
    """Eng qimmat signal: skript bajarilyapti, lekin bitim yopilmayapti."""
    rows = (
        [_call(manager="Aziz", score=88, outcome=OUTCOME_THINKING) for _ in range(8)]
        + [_call(manager="Bek", score=60, outcome=OUTCOME_MEETING) for _ in range(8)]
    )
    engine = MetaSellConversionEngine(db=None)

    report = engine.build_team_report(engine.diagnose_rows(rows))

    assert report is not None
    assert "Ball yuqori, konversiya past" in report
    assert "Aziz" in report.split("Ball yuqori, konversiya past")[1]


def test_team_report_none_without_enough_data():
    engine = MetaSellConversionEngine(db=None)
    assert engine.build_team_report(engine.diagnose_rows([_call()])) is None


def test_seller_card_gives_one_task_and_a_drill():
    strong = {
        "salomlashish": 80, "ehtiyojlar": 85, "qiymat": 80,
        "etirozlar": 80, "yakunlash": 90, "muloqot_sifati": 80,
    }
    weak = {
        "salomlashish": 80, "ehtiyojlar": 35, "qiymat": 80,
        "etirozlar": 80, "yakunlash": 80, "muloqot_sifati": 80,
    }
    rows = [_call(outcome=OUTCOME_MEETING, stages=strong) for _ in range(4)] + [
        _call(outcome=OUTCOME_REFUSED, stages=weak) for _ in range(4)
    ]

    card = MetaSellConversionEngine.build_seller_card(diagnose_seller("Aziz", rows))

    assert "KONVERSIYA KARTOCHKASI — Aziz" in card
    assert "SHU HAFTA BITTA VAZIFA" in card
    assert "Ehtiyojni aniqlash" in card
    assert "Mashq:" in card


def test_seller_card_without_diagnosis_explains_why():
    card = MetaSellConversionEngine.build_seller_card(
        diagnose_seller("Aziz", [_call()])
    )

    assert "SHU HAFTA BITTA VAZIFA" not in card
    assert "yetarli emas" in card


@pytest.mark.asyncio
async def test_team_summary_shape():
    rows = [_call(manager="Aziz", outcome=OUTCOME_MEETING) for _ in range(6)]

    class FakeDB:
        async def execute(self, sql, params=None):
            return rows

    summary = await MetaSellConversionEngine(db=FakeDB()).team_summary(days=30)

    assert summary["has_data"] is True
    assert summary["total_calls"] == 6
    assert summary["conversion_rate"] == pytest.approx(100.0)
    assert summary["sellers"][0]["manager_name"] == "Aziz"


@pytest.mark.asyncio
async def test_team_summary_empty_when_db_read_fails():
    class BrokenDB:
        async def execute(self, sql, params=None):
            raise RuntimeError("db down")

    summary = await MetaSellConversionEngine(db=BrokenDB()).team_summary()

    assert summary["has_data"] is False
    assert summary["total_calls"] == 0
