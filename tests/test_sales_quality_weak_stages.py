"""Tests for the weak-stages aggregation used by the Sifat nazorati tab."""
from src.services.sales_quality.weak_stages import _compute_weak_stages, STAGE_LABELS


def test_compute_weak_stages_empty_records_returns_empty_list():
    assert _compute_weak_stages([]) == []


def test_compute_weak_stages_ranks_lowest_average_first():
    records = [
        {
            "scores": '{"salomlashish": 90, "etirozlar": 40}',
            "weaknesses": '["Etiroz javobi kech berildi"]',
        },
        {
            "scores": '{"salomlashish": 80, "etirozlar": 30}',
            "weaknesses": '["Narx e\'tiroziga tayyor javob yo\'q"]',
        },
    ]

    result = _compute_weak_stages(records, limit=4)

    assert result[0]["stage_key"] == "etirozlar"
    assert result[0]["label"] == "E'tirozlar"
    assert result[0]["rate"] == 35.0
    assert result[0]["count"] == 2  # both calls scored below SCORE_AVERAGE (60)
    assert result[0]["weak_example"] == "Etiroz javobi kech berildi"
    assert result[1]["stage_key"] == "salomlashish"
    assert result[1]["rate"] == 85.0
    assert result[1]["count"] == 0  # neither call scored below 60 on this stage


def test_compute_weak_stages_respects_limit():
    records = [
        {
            "scores": (
                '{"salomlashish": 50, "ehtiyojlar": 55, "qiymat": 60, '
                '"etirozlar": 45, "yakunlash": 70, "muloqot_sifati": 65}'
            ),
            "weaknesses": "[]",
        },
    ]

    result = _compute_weak_stages(records, limit=4)

    assert len(result) == 4
    assert result[0]["rate"] <= result[1]["rate"] <= result[2]["rate"] <= result[3]["rate"]


def test_compute_weak_stages_ignores_rows_with_no_scores():
    records = [
        {"scores": None, "weaknesses": None},
        {"scores": "{}", "weaknesses": "[]"},
    ]

    assert _compute_weak_stages(records) == []


def test_compute_weak_stages_weak_example_blank_when_no_weaknesses():
    records = [
        {"scores": '{"qiymat": 20}', "weaknesses": "[]"},
    ]

    result = _compute_weak_stages(records)

    assert result[0]["stage_key"] == "qiymat"
    assert result[0]["weak_example"] == ""


import pytest
from src.api.routes.state import api_state


@pytest.mark.asyncio
async def test_weak_stages_route_returns_unavailable_when_db_missing(monkeypatch):
    from src.services.sales_quality.router import get_sales_quality_weak_stages

    monkeypatch.setattr(api_state, "db_instance", None)

    result = await get_sales_quality_weak_stages()

    assert result["available"] is False
    assert result["stages"] == []


@pytest.mark.asyncio
async def test_weak_stages_route_filters_by_manager_id(monkeypatch):
    from src.services.sales_quality.router import get_sales_quality_weak_stages

    async def fake_fetch_rows():
        return [
            {
                "manager_id": 1,
                "scores": '{"qiymat": 20}',
                "weaknesses": "[]",
            },
            {
                "manager_id": 2,
                "scores": '{"qiymat": 95}',
                "weaknesses": "[]",
            },
        ]

    monkeypatch.setattr(
        "src.services.sales_quality.router._fetch_call_analysis_rows",
        fake_fetch_rows,
    )

    result = await get_sales_quality_weak_stages(manager_id=1)

    assert result["available"] is True
    assert result["stages"][0]["rate"] == 20.0
