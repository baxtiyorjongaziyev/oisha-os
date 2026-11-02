"""Compensation and Attendance (Davomat) KPI Matrix Engine.

Calculates multi-component sales compensation integrating telephony talk time (MoiZvonki),
AI call audit quality score, CRM task discipline, sales revenue commission, and attendance penalties.
"""
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class AttendanceRecord:
    """Monthly attendance and lateness record for a sales representative."""

    manager_id: str
    work_days: int
    late_days: int
    late_minutes: int
    absent_days: int
    day_offs: int


@dataclass
class TelephonyRecord:
    """MoiZvonki telephony volume metrics for a sales representative."""

    manager_id: str
    talk_minutes: int
    avg_duration_seconds: int
    calls_count: int


@dataclass
class CompensationCalculation:
    """Final compensation and KPI breakdown matching GoodSales payroll matrix."""

    manager_id: str
    manager_name: str
    base_salary: int
    talk_bonus: int
    quality_bonus: int
    crm_bonus: int
    sales_kpi_bonus: int
    late_penalty: int
    net_salary: int


class CompensationDavomatEngine:
    """Engine computing monthly compensation matrix based on operations and discipline."""

    def calculate_talk_bonus(self, talk_minutes: int) -> int:
        """Calculate telephony talk time bonus."""
        if talk_minutes >= 1800:
            return 1_000_000
        elif talk_minutes >= 1200:
            return 600_000
        elif talk_minutes >= 600:
            return 300_000
        return 0

    def calculate_quality_bonus(self, ai_score: float) -> int:
        """Calculate AI call audit quality score bonus."""
        if ai_score >= 70.0:
            return 1_500_000
        elif ai_score >= 60.0:
            return 1_000_000
        elif ai_score >= 50.0:
            return 500_000
        return 0

    def calculate_crm_bonus(self, overdue_tasks: int) -> int:
        """Calculate CRM discipline and task timeliness bonus."""
        if overdue_tasks <= 3:
            return 500_000
        elif overdue_tasks <= 10:
            return 250_000
        return 0

    def calculate_sales_bonus(self, fact_revenue: int, plan_percent: int) -> int:
        """Calculate sales commission bonus based on plan realization percentage."""
        if plan_percent >= 100:
            return int(fact_revenue * 0.03)  # 3% commission on full plan
        elif plan_percent >= 70:
            return int(fact_revenue * 0.015)  # 1.5%
        return int(fact_revenue * 0.005)  # 0.5% base

    def calculate_penalties(self, late_minutes: int, absent_days: int) -> int:
        """Calculate attendance penalties (grace period 15 min, 2000 UZS/min, 150k/day absent)."""
        chargeable_late = max(0, late_minutes - 15)
        late_fine = chargeable_late * 2_000
        absent_fine = absent_days * 150_000
        return late_fine + absent_fine

    def compute_manager_compensation(
        self,
        manager_id: str,
        manager_name: str,
        base_salary: int,
        attendance: AttendanceRecord,
        telephony: TelephonyRecord,
        ai_quality_score: float,
        overdue_tasks: int,
        fact_revenue: int,
        plan_percent: int,
    ) -> CompensationCalculation:
        """Calculate net compensation for single sales representative."""
        t_bonus = self.calculate_talk_bonus(telephony.talk_minutes)
        q_bonus = self.calculate_quality_bonus(ai_quality_score)
        c_bonus = self.calculate_crm_bonus(overdue_tasks)
        s_bonus = self.calculate_sales_bonus(fact_revenue, plan_percent)
        penalty = self.calculate_penalties(attendance.late_minutes, attendance.absent_days)

        gross = base_salary + t_bonus + q_bonus + c_bonus + s_bonus
        net = max(0, gross - penalty)

        return CompensationCalculation(
            manager_id=manager_id,
            manager_name=manager_name,
            base_salary=base_salary,
            talk_bonus=t_bonus,
            quality_bonus=q_bonus,
            crm_bonus=c_bonus,
            sales_kpi_bonus=s_bonus,
            late_penalty=penalty,
            net_salary=net,
        )

    def compute_team_matrix(
        self,
        managers_data: List[Dict[str, Any]],
        default_base_salary: int = 3_000_000,
    ) -> List[CompensationCalculation]:
        """Compute full team payroll compensation matrix."""
        results: List[CompensationCalculation] = []
        for m in managers_data:
            m_id = str(m.get("id", "mgr"))
            m_name = str(m.get("name", "Menejer"))
            base = int(m.get("base_salary", default_base_salary))

            att = AttendanceRecord(
                manager_id=m_id,
                work_days=int(m.get("work_days", 22)),
                late_days=int(m.get("late_days", 0)),
                late_minutes=int(m.get("late_minutes", 0)),
                absent_days=int(m.get("absent_days", 0)),
                day_offs=int(m.get("day_offs", 8)),
            )

            tel = TelephonyRecord(
                manager_id=m_id,
                talk_minutes=int(m.get("talk_minutes", 0)),
                avg_duration_seconds=int(m.get("avg_duration_seconds", 120)),
                calls_count=int(m.get("calls_count", 0)),
            )

            comp = self.compute_manager_compensation(
                manager_id=m_id,
                manager_name=m_name,
                base_salary=base,
                attendance=att,
                telephony=tel,
                ai_quality_score=float(m.get("ai_score", 50.0)),
                overdue_tasks=int(m.get("overdue_tasks", 0)),
                fact_revenue=int(m.get("fact_revenue", 0)),
                plan_percent=int(m.get("plan_percent", 0)),
            )
            results.append(comp)

        return results
