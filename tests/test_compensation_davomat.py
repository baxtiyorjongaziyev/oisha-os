"""Unit tests for Compensation and Attendance (Davomat) KPI Matrix Engine."""
from src.services.command_center.compensation_davomat import (
    CompensationDavomatEngine,
    AttendanceRecord,
    TelephonyRecord,
    CompensationCalculation,
)


def test_calculate_bonuses_and_penalties():
    engine = CompensationDavomatEngine()

    assert engine.calculate_talk_bonus(1850) == 1_000_000
    assert engine.calculate_talk_bonus(1300) == 600_000
    assert engine.calculate_talk_bonus(400) == 0

    assert engine.calculate_quality_bonus(72.5) == 1_500_000
    assert engine.calculate_quality_bonus(62.0) == 1_000_000
    assert engine.calculate_quality_bonus(45.0) == 0

    assert engine.calculate_crm_bonus(2) == 500_000
    assert engine.calculate_crm_bonus(15) == 0

    # Penalties: 35 late minutes (15 min grace -> 20 min chargeable * 2000 = 40,000) + 1 absent (150,000) = 190,000
    assert engine.calculate_penalties(late_minutes=35, absent_days=1) == 190_000


def test_compute_manager_compensation():
    engine = CompensationDavomatEngine()
    att = AttendanceRecord("m1", work_days=22, late_days=2, late_minutes=25, absent_days=0, day_offs=8)
    tel = TelephonyRecord("m1", talk_minutes=1900, avg_duration_seconds=130, calls_count=450)

    # 3m base + 1m talk + 1.5m quality (75) + 500k crm (1 task) + 369.7m * 0.03 (11,091,000 sales) - 20k late = 17,071,000
    res = engine.compute_manager_compensation(
        manager_id="m1",
        manager_name="Kamola Karimova",
        base_salary=3_000_000,
        attendance=att,
        telephony=tel,
        ai_quality_score=75.0,
        overdue_tasks=1,
        fact_revenue=369_700_000,
        plan_percent=246,
    )
    assert res.base_salary == 3_000_000
    assert res.talk_bonus == 1_000_000
    assert res.quality_bonus == 1_500_000
    assert res.crm_bonus == 500_000
    assert res.sales_kpi_bonus == 11_091_000
    assert res.late_penalty == 20_000  # (25 - 15) * 2000
    assert res.net_salary == 17_071_000


def test_compute_team_matrix():
    engine = CompensationDavomatEngine()
    team_data = [
        {"id": "m1", "name": "Kamola", "talk_minutes": 2000, "ai_score": 75, "overdue_tasks": 0, "fact_revenue": 300_000_000, "plan_percent": 150},
        {"id": "m2", "name": "Jasur", "talk_minutes": 300, "ai_score": 45, "overdue_tasks": 15, "fact_revenue": 0, "plan_percent": 0, "late_minutes": 50, "absent_days": 2},
    ]
    matrix = engine.compute_team_matrix(team_data)
    assert len(matrix) == 2
    assert matrix[0].net_salary > 10_000_000
    # Jasur gets base 3m - penalties ((50-15)*2000 = 70k + 300k = 370k) = 2,630,000
    assert matrix[1].net_salary == 2_630_000
