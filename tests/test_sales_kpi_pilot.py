"""Synthetic independent worked examples; no actual salary or payment writes."""
import pytest

from src.services.sales_quality.kpi_pilot import quality_component, simulate_kpi


def test_known_example_and_currency_rounding():
    result = simulate_kpi(actual=80, target=100, completed_on_time=9, tasks_due=10,
                          quality={"score": 80}, bonus_pool=1000000, currency="UZS")
    assert result["total_score"] == 82.5
    assert result["projected_bonus"] == "825000.00"
    assert result["payroll_enabled"] is False
    assert result["payment_created"] is False


def test_missing_quality_is_not_zero_and_weights_are_not_renormalized():
    result = simulate_kpi(actual=100, target=100, completed_on_time=10, tasks_due=10, quality={"score": None})
    assert result["components"]["quality"] is None
    assert result["total_score"] is None
    assert result["complete"] is False


def test_zero_actual_and_zero_quality_are_real_scores():
    result = simulate_kpi(actual=0, target=100, completed_on_time=0, tasks_due=10, quality={"score": 0})
    assert result["total_score"] == 0
    assert result["complete"] is True


def test_quality_excludes_unapproved_non_sales_other_manager_and_outside_window():
    row = {"call_id": "one", "manager_id": "7", "quality_approved": True, "sales_quality": True,
           "score": 100, "reviewed_score": 80, "call_type": "discovery", "reviews": [{"created_at": 100}]}
    rows = [row, row, {**row, "call_id": "two", "quality_approved": False},
            {**row, "call_id": "three", "sales_quality": False}, {**row, "call_id": "four", "manager_id": "8"}]
    q = quality_component(rows, "7", 90, 110, minimum=2)
    assert q["reviewed_calls"] == 1
    assert q["score"] is None
    assert quality_component(rows, "7", 110, 120, minimum=1)["reviewed_calls"] == 0
    assert quality_component([row], "7", 90, 110, minimum=1)["score"] == 80


def test_invalid_task_counts_rejected():
    with pytest.raises(ValueError, match="completed_exceeds_due"):
        simulate_kpi(actual=100, target=100, completed_on_time=11, tasks_due=10, quality={"score": 90})


@pytest.mark.parametrize("actual,target", [(None, 100), (100, None), (100, 0), (float('nan'), 100)])
def test_unknown_or_invalid_result_has_no_total(actual, target):
    result = simulate_kpi(actual=actual, target=target, completed_on_time=1, tasks_due=1, quality={"score": 100})
    assert result["total_score"] is None
