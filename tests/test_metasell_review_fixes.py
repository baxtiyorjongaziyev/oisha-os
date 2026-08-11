"""PR #473 review'ida topilgan to'rtta nuqson uchun regressiya testlari.

Sharhlar merge'dan keyin kelgan, shuning uchun bu tuzatishlar alohida
o'zgarishda. Har biri prod'da jim turib noto'g'ri raqam ko'rsatardi.
"""

import json
from unittest.mock import MagicMock

import pytest

from src.services.core.call_analyzer import CallAnalyzer
from src.services.core.metasell_conversion import (
    MetaSellConversionEngine,
    _is_converted,
    _stage_scores,
    diagnose_seller,
)
from src.services.core.sales_playbook import OUTCOME_MEETING, OUTCOME_REFUSED
from src.services.utils.transcript import has_timestamps


# ── 1. `converted` DEFAULT 0 natijani bo'g'ib qo'ymasin ─────────────────


@pytest.mark.parametrize(
    "outcome,converted,expected",
    [
        # Boshqa yozuvchilar `converted` ni umuman yozmaydi -> DEFAULT 0
        ("sale", 0, True),
        ("won", 0, True),
        ("meeting", 0, True),
        (OUTCOME_MEETING, 0, True),
        # Haqiqiy "yo'q" javoblari o'zgarmaydi
        ("lost", 0, False),
        (OUTCOME_REFUSED, 0, False),
        ("", 0, False),
        # converted=1 har doim ishonchli "ha"
        (OUTCOME_REFUSED, 1, True),
        # Ustun umuman yo'q
        ("sale", None, True),
    ],
)
def test_converted_zero_is_not_authoritative(outcome, converted, expected):
    row = {"outcome": outcome}
    if converted is not None:
        row["converted"] = converted

    assert _is_converted(row) is expected


def test_ingested_sale_rows_count_towards_conversion():
    """Regressiya: ingest yo'lidan kelgan 'sale' qatorlari 0% ko'rsatardi."""
    rows = [
        {
            "manager_name": "Aziz",
            "overall_score": 80,
            "scores": json.dumps({"yakunlash": 80}),
            "outcome": "sale",
            "converted": 0,  # DEFAULT — yozuvchi to'ldirmagan
            "weaknesses": "[]", "objections": "[]", "strengths": "[]",
        }
        for _ in range(6)
    ]

    assert diagnose_seller("Aziz", rows).conversion_rate == pytest.approx(100.0)


# ── 2. `scores` metrik ro'yxati sifatida saqlangan bo'lsa ───────────────


def test_metric_list_scores_are_mapped_to_stages():
    """ConversationEngine/ingest ballarni metrik kesimida saqlaydi."""
    raw = json.dumps([
        {"metric": "closing", "score": 90},
        {"metric": "follow_up", "score": 70},
        {"metric": "introduction", "score": 80},
        {"metric": "objection_handling", "score": 40},
    ])

    stages = _stage_scores({"scores": raw})

    assert stages["yakunlash"] == pytest.approx(80.0)  # (90+70)/2
    assert stages["salomlashish"] == pytest.approx(80.0)
    assert stages["etirozlar"] == pytest.approx(40.0)


def test_stage_dict_format_still_works():
    stages = _stage_scores({"scores": json.dumps({"yakunlash": 85, "qiymat": 60})})

    assert stages["yakunlash"] == 85.0
    assert stages["qiymat"] == 60.0


@pytest.mark.parametrize("raw", ["", "not json", "[]", "null", None, 42])
def test_unparseable_scores_are_safe(raw):
    assert _stage_scores({"scores": raw}) == {}


def test_metric_list_ignores_unknown_metrics():
    raw = json.dumps([{"metric": "made_up_metric", "score": 99}])

    assert _stage_scores({"scores": raw}) == {}


def test_diagnosis_works_from_metric_list_rows():
    """Regressiya: bu yo'ldan kelgan sotuvchi o'sish nuqtasini olmasdi."""
    def row(outcome, closing):
        return {
            "manager_name": "Aziz", "overall_score": 75,
            "scores": json.dumps([
                {"metric": "introduction", "score": 80},
                {"metric": "closing", "score": closing},
                {"metric": "follow_up", "score": closing},
            ]),
            "outcome": outcome, "converted": 0,
            "weaknesses": "[]", "objections": "[]", "strengths": "[]",
        }

    rows = [row(OUTCOME_MEETING, 95) for _ in range(4)] + [
        row(OUTCOME_REFUSED, 25) for _ in range(4)
    ]

    result = diagnose_seller("Aziz", rows)

    assert result.has_diagnosis is True
    assert result.growth_stage == "yakunlash"


# ── 3. Vaqt belgisisiz transkripsiyada uzilish lahzasi to'qilmasin ──────


TIMED = "\n".join(f"[00:{i:02d}] Sotuvchi: gap {i} " + "so'z " * 6 for i in range(0, 50, 5))
UNTIMED = "\n".join(f"Sotuvchi: gap {i} " + "so'z " * 6 for i in range(0, 50, 5))


def test_has_timestamps_detects_both_forms():
    assert has_timestamps(TIMED) is True
    assert has_timestamps(UNTIMED) is False
    assert has_timestamps("") is False


def _analyzer():
    return CallAnalyzer(amocrm=MagicMock(), voice_processor=MagicMock(), db=MagicMock())


def test_breakdown_kept_when_transcript_is_timed():
    result = _analyzer()._normalise_analysis(
        {"category": "Mijoz", "uzilish_vaqti": "00:20", "uzilish_sababi": "Ehtiyoj aniqlanmadi"},
        TIMED, 60,
    )

    assert result["uzilish_vaqti"] == "00:20"
    assert result["uzilish_sababi"] == "Ehtiyoj aniqlanmadi"


def test_breakdown_dropped_without_timestamps():
    """Bepul STT yo'lida vaqt belgisi yo'q — LLM lahzani faqat TAXMIN qiladi."""
    result = _analyzer()._normalise_analysis(
        {"category": "Mijoz", "uzilish_vaqti": "00:20", "uzilish_sababi": "Ehtiyoj aniqlanmadi"},
        UNTIMED, 60,
    )

    assert result["uzilish_vaqti"] is None
    assert result["uzilish_sababi"] == ""


def test_pauses_empty_without_timestamps():
    result = _analyzer()._normalise_analysis({"category": "Mijoz"}, UNTIMED, 60)

    assert result["pauzalar"] == []
    assert result["eng_uzun_pauza"] == 0.0


# ── 4. Dashboard brauzer sessiyasi bilan ishlashi ───────────────────────


def test_dashboard_calls_a_session_authorised_endpoint():
    """`/api/ai/...` yo'li OISHA_API_SECRET talab qiladi — sahifa bilolmaydi."""
    html = open("src/api/templates/sales_quality_dashboard.html").read()

    assert "/api/sales-quality/conversion-overview" in html
    assert "/api/ai/conversion/overview" not in html


def test_conversion_overview_endpoint_is_registered():
    from src.api.routes.sales_quality import router

    paths = {r.path for r in router.routes}
    assert "/api/sales-quality/conversion-overview" in paths
