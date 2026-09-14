"""Tests for the weak-stages aggregation used by the Sifat nazorati tab."""
import pytest

from src.api.rbac import Principal, Role
from src.api.routes.state import api_state
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


@pytest.mark.asyncio
async def test_weak_stages_route_scopes_rows_for_seller_principal(monkeypatch):
    """A SELLER principal must only see stages computed from their own rows,
    even if a manager_id query param tries to widen the view."""
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

    seller = Principal(subject="1", role=Role.SELLER, auth_type="test")

    result = await get_sales_quality_weak_stages(principal=seller)

    assert result["available"] is True
    assert len(result["stages"]) == 1
    assert result["stages"][0]["rate"] == 20.0

    # Even attempting to pass another manager's id must not widen the view.
    result_with_param = await get_sales_quality_weak_stages(
        manager_id=2, principal=seller
    )
    assert result_with_param["available"] is False
    assert result_with_param["stages"] == []


@pytest.mark.asyncio
async def test_weak_stages_route_manager_id_with_no_matching_rows(monkeypatch):
    from src.services.sales_quality.router import get_sales_quality_weak_stages

    async def fake_fetch_rows():
        return [
            {
                "manager_id": 1,
                "scores": '{"qiymat": 20}',
                "weaknesses": "[]",
            },
        ]

    monkeypatch.setattr(
        "src.services.sales_quality.router._fetch_call_analysis_rows",
        fake_fetch_rows,
    )

    result = await get_sales_quality_weak_stages(manager_id=999)

    assert result["available"] is False
    assert result["stages"] == []


def test_compute_weak_stages_ignores_unknown_stage_key():
    records = [
        {
            "scores": '{"salomlashish": 40, "unknown_stage": 10}',
            "weaknesses": "[]",
        },
    ]

    result = _compute_weak_stages(records)

    assert len(result) == 1
    assert result[0]["stage_key"] == "salomlashish"
    assert result[0]["rate"] == 40.0
