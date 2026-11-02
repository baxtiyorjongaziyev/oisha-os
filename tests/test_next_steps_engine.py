"""Unit tests for NextSteps Prioritizer and Reverse Funnel Engine."""
from src.services.command_center.next_steps_engine import (
    NextStepsEngine,
    PlanTarget,
    FunnelMath,
    TeamPulse,
    ActionItem,
    LostRevenueCategory,
    LeadSourceAttribution,
)


def test_compute_funnel_reverse_math():
    engine = NextStepsEngine()
    math_result = engine.compute_funnel(
        target_amount=694_000_000,
        avg_check=2_700_000,
        conv_rate=0.067,
        kval_rate=0.449,
    )
    assert math_result.target_amount == 694_000_000
    assert math_result.sales_needed == 258
    assert math_result.kval_leads_needed == 3851
    assert math_result.total_leads_needed == 8577


def test_aggregate_team_pulse():
    engine = NextStepsEngine()
    managers = [
        {"id": "m1", "name": "Kamola", "conv": 16.8, "score": 65, "hot_deals_sum": 588_900_000, "hot_deals_count": 90, "overdue_calls": 120, "overdue_tasks": 25},
        {"id": "m2", "name": "Mohira", "conv": 10.7, "score": 64, "hot_deals_sum": 57_500_000, "hot_deals_count": 45, "overdue_calls": 50, "overdue_tasks": 10},
        {"id": "m3", "name": "Feruza", "conv": 3.0, "score": 58, "hot_deals_sum": 22_000_000, "hot_deals_count": 15, "overdue_calls": 30, "overdue_tasks": 15},
    ]
    pulse = engine.aggregate_team_pulse(managers)
    assert pulse.avg_ai_score == 62.33
    assert pulse.top_conv_manager == "Kamola"
    assert pulse.hot_deals_sum == 668_400_000
    assert pulse.hot_deals_count == 150
    assert pulse.overdue_promises_count == 200
    assert pulse.overdue_tasks_count == 50


def test_generate_action_queue_financial_impact_sorting():
    engine = NextStepsEngine()
    managers = [
        {"id": "m1", "name": "Kamola Karimova", "hot_deals_sum": 588_900_000, "hot_deals_count": 90, "conv": 16.8},
        {"id": "m2", "name": "Feruza Karimova", "hot_deals_sum": 22_000_000, "hot_deals_count": 15, "conv": 3.0},
        {"id": "m3", "name": "Eldor Karimov", "hot_deals_sum": 0, "hot_deals_count": 0, "conv": 0.0, "quality_leads": 120},
    ]
    actions = engine.generate_action_queue(
        target_amount=694_000_000,
        current_fact=623_700_000,
        managers=managers,
        avg_check=2_700_000,
        team_avg_conv=6.7,
    )
    assert len(actions) >= 5
    hot_action = next(a for a in actions if a.kind == "hot_deals" and a.manager_name == "Kamola Karimova")
    assert hot_action.priority == "high"
    assert hot_action.impact == 176_670_000
    assert "30%" in hot_action.impact_note


def test_analyze_lost_revenue():
    engine = NextStepsEngine()
    lost_breakdown = [
        {"reason": "Vaqti toʻgʻri kelmadi", "count": 453, "type": "sales_process"},
        {"reason": "Telefonni koʻtarmadi", "count": 232, "type": "sales_process"},
        {"reason": "Murojaat qoldirmagan", "count": 881, "type": "lead_quality"},
        {"reason": "Dubl", "count": 878, "type": "lead_quality"},
        {"reason": "Sabab yozilmagan", "count": 1043, "type": "no_reason"},
    ]
    result = engine.analyze_lost_revenue(
        lost_items=lost_breakdown,
        avg_check=2_700_000,
        recoverable_conv=0.03,
    )
    assert "sales_process" in result
    assert "lead_quality" in result
    assert "no_reason" in result
    assert result["sales_process"].recoverable_sum == 55_485_000


def test_attribute_sources():
    engine = NextStepsEngine()
    sources_data = [
        {"name": "Sayt formasi", "leads": 7945, "kval": 3766, "won": 643, "revenue": 897_000_000},
        {"name": "Instagram Direct", "leads": 1563, "kval": 403, "won": 15, "revenue": 3_126_000},
        {"name": "Baza", "leads": 2313, "kval": 1556, "won": 502, "revenue": 902_000_000},
    ]
    attributions = engine.attribute_sources(sources_data)
    assert len(attributions) == 3
    insta = next(s for s in attributions if s.source_name == "Instagram Direct")
    assert insta.recommendation == "Tozalang"
    baza = next(s for s in attributions if s.source_name == "Baza")
    assert baza.recommendation == "Normal"
