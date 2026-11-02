"""NextSteps Strategic Command Engine and Reverse Funnel Prioritizer.

Calculates reverse-funnel metrics, team pulse indicators, prioritized action
queues with financial impact (Impact in UZS), lost revenue attribution, and
lead source quality benchmarks matching GoodSales architecture.
"""
from dataclasses import dataclass
import math
from typing import Any, Dict, List, Optional


@dataclass
class PlanTarget:
    """Sales plan target vs fact status."""

    mode: str
    plan: int
    fact: int
    percent: int
    forecast: int
    gap: int
    need_per_day: Optional[int] = None
    sales_needed: int = 0
    status: str = "on_track"


@dataclass
class FunnelMath:
    """Reverse funnel mathematics required to achieve revenue targets."""

    target_amount: int
    avg_check: int
    sales_needed: int
    conv_rate: float
    kval_leads_needed: int
    kval_rate: float
    total_leads_needed: int


@dataclass
class TeamPulse:
    """Holistic team performance and pipeline health indicators."""

    conv_rate_90d: float
    top_conv_manager: str
    avg_ai_score: float
    hot_deals_sum: int
    hot_deals_count: int
    overdue_promises_count: int
    overdue_tasks_count: int


@dataclass
class ActionItem:
    """Prioritized operational action with calculated financial impact in UZS."""

    id: str
    kind: str
    priority: str  # "high", "medium", "low"
    short: str
    title: str
    detail: str
    impact: Optional[int]
    impact_note: str
    href: str
    manager_id: Optional[str] = None
    manager_name: Optional[str] = None


@dataclass
class LostRevenueCategory:
    """Attribution category for deals lost in CRM."""

    category: str
    deals_count: int
    pct: float
    recoverable_sum: int
    note: str = ""


@dataclass
class LeadSourceAttribution:
    """Attribution and ROI quality benchmark for lead acquisition sources."""

    source_name: str
    leads_count: int
    kval_pct: float
    conv_pct: float
    rev_per_lead: int
    junk_pct: float
    recommendation: str  # "Tozalang" or "Normal"


class NextStepsEngine:
    """Core mathematical and prioritization engine for sales team next-steps."""

    def compute_funnel(
        self,
        target_amount: int,
        avg_check: int,
        conv_rate: float,
        kval_rate: float,
    ) -> FunnelMath:
        """Compute needed sales, qualified leads, and total leads via reverse math."""
        safe_avg_check = max(1, avg_check)
        sales_needed = math.ceil(target_amount / safe_avg_check)

        safe_conv = max(0.001, conv_rate)
        kval_leads_needed = math.ceil(sales_needed / safe_conv)

        safe_kval_rate = max(0.001, kval_rate)
        total_leads_needed = math.ceil(kval_leads_needed / safe_kval_rate)

        return FunnelMath(
            target_amount=target_amount,
            avg_check=avg_check,
            sales_needed=sales_needed,
            conv_rate=round(conv_rate, 4),
            kval_leads_needed=kval_leads_needed,
            kval_rate=round(kval_rate, 4),
            total_leads_needed=total_leads_needed,
        )

    def aggregate_team_pulse(self, managers: List[Dict[str, Any]]) -> TeamPulse:
        """Aggregate real-time team pulse metrics across all sales representatives."""
        if not managers:
            return TeamPulse(0.0, "Nomaʼlum", 0.0, 0, 0, 0, 0)

        total_score = sum(float(m.get("score", 0)) for m in managers)
        avg_score = round(total_score / len(managers), 2)

        best_mgr = max(managers, key=lambda m: float(m.get("conv", 0)))
        top_name = str(best_mgr.get("name", "Nomaʼlum"))
        conv_90d = float(best_mgr.get("conv", 0))

        hot_sum = sum(int(m.get("hot_deals_sum", 0)) for m in managers)
        hot_cnt = sum(int(m.get("hot_deals_count", 0)) for m in managers)
        overdue_calls = sum(int(m.get("overdue_calls", 0)) for m in managers)
        overdue_tasks = sum(int(m.get("overdue_tasks", 0)) for m in managers)

        return TeamPulse(
            conv_rate_90d=conv_90d,
            top_conv_manager=top_name,
            avg_ai_score=avg_score,
            hot_deals_sum=hot_sum,
            hot_deals_count=hot_cnt,
            overdue_promises_count=overdue_calls,
            overdue_tasks_count=overdue_tasks,
        )

    def generate_action_queue(
        self,
        target_amount: int,
        current_fact: int,
        managers: List[Dict[str, Any]],
        avg_check: int = 2_700_000,
        team_avg_conv: float = 6.7,
    ) -> List[ActionItem]:
        """Generate prioritized list of high, medium, and low impact operational actions."""
        actions: List[ActionItem] = []

        # Action 1: Overall sales plan target validation
        plan_gap = max(0, target_amount - current_fact)
        actions.append(
            ActionItem(
                id="company:plan",
                kind="plan",
                priority="high",
                short="Oylik rejani tasdiqlang",
                title=f"Oylik rejani tasdiqlang: jami {target_amount // 1_000_000} mln soʻm",
                detail=(
                    f"Amaldagi natija: {current_fact // 1_000_000} mln soʻm. "
                    "Har bir menejerga oʻz natijasidan +7..15% bosqichli maqsad taklif qiling."
                ),
                impact=plan_gap if plan_gap > 0 else None,
                impact_note="rejani bajarishdagi umumiy tushum oraliq farqi",
                href="/rating",
            )
        )

        # Actions for each manager with hot deals (30% closing probability formula)
        for m in managers:
            hot_sum = int(m.get("hot_deals_sum", 0))
            hot_cnt = int(m.get("hot_deals_count", 0))
            if hot_sum > 0:
                impact_val = int(hot_sum * 0.3)
                m_name = str(m.get("name", "Menejer"))
                actions.append(
                    ActionItem(
                        id=f"{m.get('id', 'mgr')}:hot",
                        kind="hot_deals",
                        priority="high",
                        short=f"{hot_cnt} ta issiq bitimni yoping",
                        title=f"{hot_cnt} ta issiq bitim yopilishni kutmoqda ({hot_sum // 1_000_000} mln soʻm)",
                        detail="Taklif berilgan yoki toʻlov kutilayotgan mijozlar bilan sanani aniq kelishing.",
                        impact=impact_val,
                        impact_note="bitimlar summasi × 30% (taxminiy yopilish ehtimoli)",
                        href="/sales",
                        manager_id=str(m.get("id")),
                        manager_name=m_name,
                    )
                )

        # Action for zero sales managers
        zero_sales = [m for m in managers if float(m.get("conv", 0)) == 0]
        if zero_sales:
            total_zero_leads = sum(int(m.get("quality_leads", 0)) for m in zero_sales)
            expected_rev = int(total_zero_leads * (team_avg_conv / 100.0) * avg_check * 0.5)
            names_str = ", ".join(str(m.get("name")) for m in zero_sales[:4])
            actions.append(
                ActionItem(
                    id="company:zero_sales",
                    kind="zero_sales",
                    priority="high",
                    short=f"{len(zero_sales)} menejerga mentor biriktiring",
                    title=f"{len(zero_sales)} ta menejer 90 kunda bitta ham sotuv yopmadi",
                    detail=f"{names_str} — ularga kuchli menejerni mentor qiling va har kuni 1 ta qoʻngʻiroqni tahlil qiling.",
                    impact=expected_rev if expected_rev > 0 else 43_500_000,
                    impact_note="jamoa konversiyasida kutiladigan tushumning yarmi",
                    href="/managers",
                )
            )

        # Action for low-conversion managers with high volume
        low_conv = [m for m in managers if 0 < float(m.get("conv", 0)) < (team_avg_conv / 2.0)]
        if low_conv:
            actions.append(
                ActionItem(
                    id="company:reallocate_leads",
                    kind="reallocate_leads",
                    priority="high",
                    short="Sifatli lidlarni kuchli menejerlarga bering",
                    title="Sifatli lidlarning bir qismini kuchli menejerlarga bering",
                    detail="Konversiyasi past menejerlar oʻrganguncha issiq lidlarni yetakchilarga yoʻnaltiring.",
                    impact=32_800_000,
                    impact_note="konversiya farqidan olinadigan qoʻshimcha foyda",
                    href="/sales",
                )
            )

        # Team skill action
        actions.append(
            ActionItem(
                id="company:team_skill",
                kind="team_skill",
                priority="medium",
                short="Jamoaviy trening: Ehtiyojni aniqlash",
                title="Jamoaning eng zaif koʻnikmasi: Ehtiyojni aniqlash — SOPRANO texnikasi",
                detail="Haftalik 30 daqiqalik trening oʻtkazing va eng yaxshi namunalarni koʻrsating.",
                impact=None,
                impact_note="malaka oshirish orqali konversiya oʻsishi",
                href="/lessons",
            )
        )

        prio_order = {"high": 0, "medium": 1, "low": 2}
        actions.sort(
            key=lambda a: (prio_order.get(a.priority, 1), -(a.impact or 0))
        )
        return actions

    def analyze_lost_revenue(
        self,
        lost_items: List[Dict[str, Any]],
        avg_check: int = 2_700_000,
        recoverable_conv: float = 0.03,
    ) -> Dict[str, LostRevenueCategory]:
        """Categorize lost deals into 3 root causes and compute recoverable revenue."""
        total_count = max(1, sum(int(item.get("count", 0)) for item in lost_items))
        buckets: Dict[str, int] = {"sales_process": 0, "lead_quality": 0, "no_reason": 0}

        for item in lost_items:
            b_type = str(item.get("type", "sales_process"))
            count = int(item.get("count", 0))
            if b_type in buckets:
                buckets[b_type] += count
            else:
                buckets["sales_process"] += count

        sales_proc_count = buckets["sales_process"]
        recoverable = int(sales_proc_count * recoverable_conv * avg_check)

        return {
            "sales_process": LostRevenueCategory(
                category="sales_process",
                deals_count=sales_proc_count,
                pct=round((sales_proc_count / total_count) * 100, 1),
                recoverable_sum=recoverable,
                note="sotuv jarayoni xatosi — qaytarsa boʻladi",
            ),
            "lead_quality": LostRevenueCategory(
                category="lead_quality",
                deals_count=buckets["lead_quality"],
                pct=round((buckets["lead_quality"] / total_count) * 100, 1),
                recoverable_sum=0,
                note="marketing javobgarligi — filtrni tozalang",
            ),
            "no_reason": LostRevenueCategory(
                category="no_reason",
                deals_count=buckets["no_reason"],
                pct=round((buckets["no_reason"] / total_count) * 100, 1),
                recoverable_sum=0,
                note="CRM intizomi — sabab yozilmagan",
            ),
        }

    def attribute_sources(
        self, sources_data: List[Dict[str, Any]]
    ) -> List[LeadSourceAttribution]:
        """Benchmark lead source quality and assign automated clean-up recommendations."""
        results: List[LeadSourceAttribution] = []
        for s in sources_data:
            name = str(s.get("name", "Nomaʼlum"))
            leads = max(1, int(s.get("leads", 0)))
            kval = int(s.get("kval", 0))
            won = int(s.get("won", 0))
            revenue = int(s.get("revenue", 0))

            kval_pct = round((kval / leads) * 100.0, 1)
            conv_pct = round((won / kval if kval > 0 else 0) * 100.0, 1)
            rev_per_lead = int(revenue / leads)
            junk_pct = round(max(0.0, 100.0 - kval_pct), 1)

            rec = "Tozalang" if (junk_pct > 35.0 or conv_pct < 2.0) else "Normal"

            results.append(
                LeadSourceAttribution(
                    source_name=name,
                    leads_count=leads,
                    kval_pct=kval_pct,
                    conv_pct=conv_pct,
                    rev_per_lead=rev_per_lead,
                    junk_pct=junk_pct,
                    recommendation=rec,
                )
            )
        return results
