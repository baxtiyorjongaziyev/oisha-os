"""Kunlik murabbiylik hisoboti va AI takliflari.

Talab: har bir qo'ng'iroq baholanadi, kun oxirida eng yaxshi sotuvchi va
eng past natijali menejerga nimani yaxshilash kerakligi aytiladi.
"""

import json
from types import SimpleNamespace

import pytest

from src.services.core.sales_quality_coach import (
    MIN_CALLS_FOR_RANKING,
    SalesQualityCoach,
)


def _row(manager, score, weaknesses=(), strengths=(), outcome="follow_up"):
    return {
        "manager_name": manager,
        "overall_score": score,
        "category": "good" if score >= 75 else "poor",
        "weaknesses": json.dumps(list(weaknesses), ensure_ascii=False),
        "strengths": json.dumps(list(strengths), ensure_ascii=False),
        "outcome": outcome,
        "call_id": f"{manager}-{score}",
        "duration_seconds": 300,
    }


DAY = "2026-07-21"


def test_report_names_best_and_weakest_manager():
    rows = [
        _row("Sardor", 92, strengths=["Aniq tanishtirish"]),
        _row("Sardor", 88, strengths=["Aniq tanishtirish", "Uchrashuv kelishildi"]),
        _row("Aziz", 45, weaknesses=["Keyingi qadam kelishilmadi"]),
        _row("Aziz", 35, weaknesses=["Keyingi qadam kelishilmadi", "Narx qat'iy aytildi"]),
    ]

    report = SalesQualityCoach(db=None).build_daily_report(rows, DAY)

    assert "Sardor" in report
    assert "eng yaxshi sotuvchisi" in report
    assert "Aziz" in report
    # Eng ko'p takrorlangan kamchilik aynan ko'rsatiladi
    assert "Keyingi qadam kelishilmadi" in report
    # Eng yaxshining kuchli tomoni ham
    assert "Aniq tanishtirish" in report


def test_report_counts_red_calls():
    rows = [_row("Aziz", 30), _row("Aziz", 20), _row("Sardor", 80)]

    report = SalesQualityCoach(db=None).build_daily_report(rows, DAY)

    assert "Baholangan qo'ng'iroqlar: 3" in report
    assert "Qizil qo'ng'iroqlar (<40): 2" in report


def test_manager_with_too_few_calls_is_not_ranked():
    """Bitta qo'ng'iroq bo'yicha menejerni 'eng yomon' deb e'lon qilish adolatsiz."""
    assert MIN_CALLS_FOR_RANKING == 2
    rows = [_row("Sardor", 90), _row("Aziz", 20)]  # har birida 1 tadan

    report = SalesQualityCoach(db=None).build_daily_report(rows, DAY)

    assert "eng yaxshi sotuvchisi" not in report
    assert "kamida" in report  # sabab tushuntiriladi


def test_no_calls_means_no_report():
    assert SalesQualityCoach(db=None).build_daily_report([], DAY) is None


@pytest.mark.asyncio
async def test_daily_report_reads_only_requested_day():
    captured = {}

    class FakeDB:
        async def execute(self, sql, params):
            captured["sql"] = sql
            captured["params"] = params
            return [_row("Sardor", 80), _row("Sardor", 90)]

    report = await SalesQualityCoach(db=FakeDB()).generate_daily_report(DAY)

    assert captured["params"] == [f"{DAY}%"]
    assert "call_analyses" in captured["sql"]
    assert "Sardor" in report


@pytest.mark.asyncio
async def test_db_failure_does_not_crash_the_scheduler():
    class BrokenDB:
        async def execute(self, sql, params):
            raise RuntimeError("db down")

    report = await SalesQualityCoach(db=BrokenDB()).generate_daily_report(DAY)

    assert report is None


@pytest.mark.asyncio
async def test_ideal_script_needs_enough_samples():
    class ThinDB:
        async def execute(self, sql, params):
            return [{"transcript": "salom" * 100, "overall_score": 90, "outcome": "sale"}]

    coach = SalesQualityCoach(db=ThinDB(), gemini_client=SimpleNamespace())

    assert await coach.generate_ideal_script() is None


@pytest.mark.asyncio
async def test_ideal_script_built_from_top_calls(monkeypatch):
    samples = [
        {"transcript": f"Sotuvchi: namuna {i} " * 50, "overall_score": 90, "outcome": "sale"}
        for i in range(3)
    ]

    class DB:
        async def execute(self, sql, params):
            return samples

    captured = {}

    async def fake_generate(client, **kwargs):
        captured["prompt"] = kwargs.get("contents")
        return SimpleNamespace(text="1. Salomlashish: ..."), "gemini-1.5-pro"

    monkeypatch.setattr(
        "src.services.utils.gemini_fallback.generate_content_with_fallback",
        fake_generate,
    )

    coach = SalesQualityCoach(db=DB(), gemini_client=SimpleNamespace())
    script = await coach.generate_ideal_script()

    assert script.startswith("1. Salomlashish")
    # Skript rasmiy playbook mezonlariga tayanadi
    assert "RASMIY SOTUV RUBRIKASI" in captured["prompt"]
    assert "namuna 0" in captured["prompt"]


@pytest.mark.asyncio
async def test_playbook_suggestions_are_advisory_only(monkeypatch):
    """AI playbook faylini o'zgartirmaydi — faqat matn qaytaradi."""
    weak_rows = [{"weaknesses": json.dumps(["Yakunlash yo'q"])} for _ in range(10)]

    class DB:
        async def execute(self, sql, params):
            return weak_rows

    async def fake_generate(client, **kwargs):
        assert "TAKLIF" in kwargs.get("contents")
        return SimpleNamespace(text="Yakunlash bo'yicha trening kerak."), "gemini-1.5-pro"

    monkeypatch.setattr(
        "src.services.utils.gemini_fallback.generate_content_with_fallback",
        fake_generate,
    )

    import src.services.core.sales_playbook as playbook

    before = playbook.rubric_prompt_uz()
    coach = SalesQualityCoach(db=DB(), gemini_client=SimpleNamespace())
    result = await coach.suggest_playbook_improvements()

    assert "trening" in result
    # Rasmiy playbook tegilmagan
    assert playbook.rubric_prompt_uz() == before


@pytest.mark.asyncio
async def test_llm_failure_is_survivable(monkeypatch):
    class DB:
        async def execute(self, sql, params):
            return [
                {"transcript": "x" * 300, "overall_score": 90, "outcome": "sale"}
                for _ in range(3)
            ]

    async def boom(client, **kwargs):
        raise RuntimeError("gemini down")

    monkeypatch.setattr(
        "src.services.utils.gemini_fallback.generate_content_with_fallback", boom
    )

    coach = SalesQualityCoach(db=DB(), gemini_client=SimpleNamespace())

    assert await coach.generate_ideal_script() is None
