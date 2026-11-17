"""Owner targets and planning assumptions remain distinct from observations."""
import pytest

from src.services.sales_quality.funnel_policy import daily_funnel_policy, planned_attempts


def test_owner_targets_are_customer_counts_not_attempts():
    p = daily_funnel_policy()
    assert [s["target"] for s in p["stages"]] == [50, 20, 10, 3, 1]
    assert p["stages"][0]["minimum_talk_seconds"] == 180
    assert p["counting_unit"] == "distinct_customer_per_stage"
    assert p["planning"]["minimum_talk_minutes"] == 50 * 180 / 60
    assert p["planning"]["attempts_are_kpi_target"] is False
    assert p["observed_counts"] is None
    assert p["payroll_enabled"] is False
    assert p["evqn"]["N"] == "Narx va mijoz munosabati"
    assert len(p["meaningful_criteria"]) == 3


def test_attempt_estimate_changes_with_answer_rate_without_changing_target():
    assert planned_attempts("0.5") == 100
    assert planned_attempts("0.6") == 84
    assert planned_attempts("1") == 50
    assert planned_attempts(None) is None
    policy = daily_funnel_policy()
    policy["stages"][0]["target"] = 100
    assert daily_funnel_policy()["stages"][0]["target"] == 50


@pytest.mark.parametrize("rate", [0, -1, 1.01, "nan", "inf", "unknown", True])
def test_invalid_assumed_rate_rejected(rate):
    with pytest.raises(ValueError, match="invalid_answer_rate"):
        planned_attempts(rate)
