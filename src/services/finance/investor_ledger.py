from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class Investor:
    investor_id: str
    name: str
    total_invested: float
    available_capital: float
    default_profit_share_pct: float = 20.0
    created_at: str = field(
        default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M")
    )


@dataclass
class InvestorDeal:
    deal_id: str
    investor_id: str
    project_id: str
    allocated_amount: float
    profit_share_pct: float
    status: str = "faol"
    investor_profit: float = 0.0
    total_payout_due: float = 0.0
    paid_out: bool = False
    closed_at: Optional[str] = None


class InvestorLedgerService:
    def __init__(self):
        self._investors: Dict[str, Investor] = {}
        self._deals: Dict[str, InvestorDeal] = {}

    def register_investor(
        self,
        investor_id: str,
        name: str,
        initial_capital: float,
        default_profit_share_pct: float = 20.0,
    ) -> Investor:
        capital = float(initial_capital)
        inv = Investor(
            investor_id=investor_id,
            name=name,
            total_invested=capital,
            available_capital=capital,
            default_profit_share_pct=float(default_profit_share_pct),
        )
        self._investors[investor_id] = inv
        return inv

    def get_investor(self, investor_id: str) -> Investor:
        if investor_id not in self._investors:
            raise ValueError(f"Investor topilmadi: {investor_id}")
        return self._investors[investor_id]

    def get_deal(self, deal_id: str) -> InvestorDeal:
        if deal_id not in self._deals:
            raise ValueError(f"Bitim topilmadi: {deal_id}")
        return self._deals[deal_id]

    def allocate_deal(
        self,
        deal_id: str,
        investor_id: str,
        project_id: str,
        allocated_amount: float,
        profit_share_pct: Optional[float] = None,
    ) -> InvestorDeal:
        inv = self.get_investor(investor_id)
        amount = float(allocated_amount)

        if amount > inv.available_capital:
            raise ValueError(f"Mablagʻ yetarli emas: mavjud {inv.available_capital:,.2f}")

        inv.available_capital = round(inv.available_capital - amount, 2)
        share_pct = (
            float(profit_share_pct)
            if profit_share_pct is not None
            else inv.default_profit_share_pct
        )

        deal = InvestorDeal(
            deal_id=deal_id,
            investor_id=investor_id,
            project_id=project_id,
            allocated_amount=amount,
            profit_share_pct=share_pct,
            status="faol",
        )
        self._deals[deal_id] = deal
        return deal

    def close_deal(self, deal_id: str, project_net_profit: float) -> InvestorDeal:
        deal = self.get_deal(deal_id)
        if deal.status != "faol":
            raise ValueError("Bitim allaqachon yopilgan")

        profit = float(project_net_profit)
        investor_share = (
            round((profit * deal.profit_share_pct) / 100.0, 2) if profit > 0 else 0.0
        )
        total_due = round(deal.allocated_amount + investor_share, 2)

        deal.status = "yakunlangan"
        deal.investor_profit = investor_share
        deal.total_payout_due = total_due
        deal.closed_at = datetime.now().strftime("%Y-%m-%d %H:%M")
        return deal

    def mark_payout_complete(self, deal_id: str) -> InvestorDeal:
        deal = self.get_deal(deal_id)
        deal.paid_out = True
        return deal

    def get_investor_summary(self, investor_id: str) -> Dict[str, Any]:
        inv = self.get_investor(investor_id)
        deals = [d for d in self._deals.values() if d.investor_id == investor_id]
        total_profit = sum(d.investor_profit for d in deals if d.status == "yakunlangan")
        unpaid = sum(
            d.total_payout_due
            for d in deals
            if d.status == "yakunlangan" and not d.paid_out
        )
        return {
            "investor_id": inv.investor_id,
            "name": inv.name,
            "total_invested": inv.total_invested,
            "available_capital": inv.available_capital,
            "total_profit_earned": round(total_profit, 2),
            "unpaid_dividends": round(unpaid, 2),
            "deals_count": len(deals),
            "active_deals": len([d for d in deals if d.status == "faol"]),
        }
