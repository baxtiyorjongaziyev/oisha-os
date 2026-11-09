from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class ProjectCostInput:
    project_id: str
    project_name: str
    client_name: str
    contract_amount: float
    direct_expenses: float = 0.0
    internal_hours: float = 0.0
    hourly_rate_override: Optional[float] = None
    tax_rate_override: Optional[float] = None


@dataclass
class ProjectMarginResult:
    project_id: str
    project_name: str
    client_name: str
    contract_amount: float
    direct_expenses: float
    internal_labor_cost: float
    taxes_amount: float
    total_cost: float
    gross_profit: float
    net_profit: float
    gross_margin_pct: float
    net_margin_pct: float
    health_status: str
    insights: List[str] = field(default_factory=list)


class ProjectMarginCalculator:
    def __init__(
        self, default_hourly_rate: float = 150000.0, default_tax_rate: float = 0.04
    ):
        self.default_hourly_rate = default_hourly_rate
        self.default_tax_rate = default_tax_rate

    def calculate(self, data: ProjectCostInput) -> ProjectMarginResult:
        contract = float(data.contract_amount)
        direct = float(data.direct_expenses)
        hours = float(data.internal_hours)

        hourly_rate = (
            data.hourly_rate_override
            if data.hourly_rate_override is not None
            else self.default_hourly_rate
        )
        tax_rate = (
            data.tax_rate_override
            if data.tax_rate_override is not None
            else self.default_tax_rate
        )

        internal_labor = round(hours * hourly_rate, 2)
        taxes = round(contract * tax_rate, 2)
        total_cost = round(direct + internal_labor + taxes, 2)

        gross_profit = round(contract - direct, 2)
        net_profit = round(contract - total_cost, 2)

        gross_margin = (
            round((gross_profit / contract) * 100, 2) if contract > 0 else 0.0
        )
        net_margin = (
            round((net_profit / contract) * 100, 2) if contract > 0 else 0.0
        )

        health = "foydali" if net_margin >= 30.0 else ("past_marja" if net_margin >= 0.0 else "zararli")

        insights = []
        if net_margin < 0:
            insights.append("Diqqat: Loyiha zarar keltirmoqda. Ichki soatlar va pravkalar xarajati shartnoma byudjetidan oshib ketgan.")
        elif net_margin < 20:
            insights.append("Ogohlantirish: Loyiha marjasi 20% dan past.")

        if contract > 0 and (direct / contract) > 0.4:
            insights.append("Tashqi frilanser xarajatlari shartnoma summasining 40% idan yuqori.")

        if contract > 0 and (internal_labor / contract) > 0.6:
            insights.append("Jamoaning sarflagan soatlari shartnomaning 60% idan koʻpini tashkil etdi.")

        if not insights:
            insights.append("Loyiha moliyaviy meʼyorlarga toʻliq javob beradi (yuqori marja).")

        return ProjectMarginResult(
            project_id=data.project_id,
            project_name=data.project_name,
            client_name=data.client_name,
            contract_amount=round(contract, 2),
            direct_expenses=round(direct, 2),
            internal_labor_cost=internal_labor,
            taxes_amount=taxes,
            total_cost=total_cost,
            gross_profit=gross_profit,
            net_profit=net_profit,
            gross_margin_pct=gross_margin,
            net_margin_pct=net_margin,
            health_status=health,
            insights=insights,
        )
