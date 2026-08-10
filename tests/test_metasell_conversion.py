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


@pytest.mark.parametrize(
    "legacy,expected_converted",
    [
        # `services.ai.quality_analyzer` lug'ati
        ("sale", True),
        ("follow_up", False),
        ("callback", False),
        ("lost", False),
        ("not_sales", False),
        ("unknown", False),
        # `deal_hygiene` lug'ati
        ("no_interest", False),
        ("not_interested", False),
        ("wrong_number", False),
        ("spam", False),
        ("invalid", False),
    ],
)
def test_legacy_english_outcomes_are_translated(legacy, expected_converted):
    """Bitta ustunga bir nechta baholovchi yozadi — hammasi bir xil
    tushunilishi shart, aks holda konversiya past ko'rsatiladi."""
    assert normalise_outcome(legacy) != "aniqlanmadi" or legacy in {
        "not_sales",
        "unknown",
    }
    assert outcome_converted(legacy) is expected_converted


def test_legacy_sale_counts_as_conversion_in_diagnosis():
    """Regressiya: 'sale' natijali qatorlar konversiyaga kirmay qolgan edi."""
    rows = [_call(outcome="sale") for _ in range(6)]

    result = diagnose_seller("Aziz", rows)

    assert result.conversion_rate == pytest.approx(100.0)


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


# ── Trend (reklamadagi "+28% ↗") ────────────────────────────────────────


from src.services.core.metasell_conversion import (  # noqa: E402
    MIN_CALLS_FOR_TREND,
    ConversionTrend,
)


def _rows(n, converted):
    outcome = OUTCOME_MEETING if converted else OUTCOME_REFUSED
    return [_call(outcome=outcome) for _ in range(n)]


def test_trend_reports_percentage_points_not_relative_percent():
    """22% -> 50% bu +28 pp. Nisbiy '+127%' deb yozish chalg'itadi."""
    current = _rows(5, True) + _rows(5, False)
    previous = _rows(2, True) + _rows(8, False)

    trend = MetaSellConversionEngine.build_trend(current, previous, 30)

    assert trend.current_rate == pytest.approx(50.0)
    assert trend.previous_rate == pytest.approx(20.0)
    assert trend.delta_pp == pytest.approx(30.0)
    assert trend.direction == "o'smoqda"
    assert "pp" in trend.headline()


def test_trend_detects_decline():
    trend = MetaSellConversionEngine.build_trend(
        _rows(1, True) + _rows(9, False), _rows(8, True) + _rows(2, False), 30
    )

    assert trend.direction == "pasaymoqda"
    assert trend.arrow == "↘"


def test_trend_calls_small_change_stable():
    trend = MetaSellConversionEngine.build_trend(
        _rows(5, True) + _rows(5, False), _rows(5, True) + _rows(5, False), 30
    )

    assert trend.direction == "barqaror"
    assert trend.arrow == "→"


def test_trend_unreliable_without_enough_history():
    """Ikki qo'ng'iroqdan '+50%' chiqarish — chalg'ituvchi raqam."""
    trend = MetaSellConversionEngine.build_trend(
        _rows(10, True), _rows(MIN_CALLS_FOR_TREND - 1, False), 30
    )

    assert trend.reliable is False
    assert trend.direction == "noaniq"
    assert "yetarli emas" in trend.reason or "kerak" in trend.reason
    assert "pp" not in trend.headline()


def test_unreliable_trend_still_shows_current_rate():
    trend = MetaSellConversionEngine.build_trend(_rows(10, True), [], 30)

    assert "100%" in trend.headline()


# ── Pul ko'rsatkichlari ─────────────────────────────────────────────────


def _paid_call(lead_id, price, won, outcome=OUTCOME_MEETING, close=80):
    call = _call(outcome=outcome, stages={
        "salomlashish": 80, "ehtiyojlar": 80, "qiymat": 75,
        "etirozlar": 75, "yakunlash": close, "muloqot_sifati": 78,
    })
    call.update({"lead_id": lead_id, "lead_price": price, "lead_won": won,
                 "created_at": f"2026-08-{lead_id:02d}"})
    return call


def test_diagnosis_carries_money():
    rows = [_paid_call(i, 10_000_000, 1) for i in range(1, 5)] + [
        _paid_call(i, 20_000_000, 0, OUTCOME_THINKING, close=20) for i in range(5, 9)
    ]

    result = diagnose_seller("Aziz", rows)

    assert result.deals_won == 4
    assert result.revenue_won == 40_000_000
    assert result.revenue_at_risk == 80_000_000


def test_seller_card_shows_money():
    rows = [_paid_call(i, 10_000_000, 1) for i in range(1, 5)] + [
        _paid_call(i, 20_000_000, 0, OUTCOME_THINKING, close=20) for i in range(5, 9)
    ]

    card = MetaSellConversionEngine.build_seller_card(diagnose_seller("Aziz", rows))

    assert "so'm" in card
    assert "40 000 000" in card


def test_team_report_includes_trend_headline():
    rows = [_paid_call(i, 5_000_000, 1) for i in range(1, 9)]
    engine = MetaSellConversionEngine(db=None)
    trend = ConversionTrend(
        days=30, current_rate=68.0, previous_rate=40.0,
        current_calls=20, previous_calls=20, reliable=True,
    )

    report = engine.build_team_report(engine.diagnose_rows(rows), trend)

    assert "+28 pp" in report
    assert "↗" in report


def test_team_report_without_trend_still_works():
    rows = [_paid_call(i, 5_000_000, 1) for i in range(1, 9)]
    engine = MetaSellConversionEngine(db=None)

    report = engine.build_team_report(engine.diagnose_rows(rows))

    assert "Konversiya:" in report
