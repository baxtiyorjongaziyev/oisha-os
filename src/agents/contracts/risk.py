"""
Deal Risk Assessment and Approval requirements.
"""
from __future__ import annotations

from typing import Any, Dict, List


class RiskAssessor:
    """
    Bitim risklarini baholash tizimi
    """

    def __init__(self):
        self.risk_factors = {
            "price_pressure": {"weight": 0.3, "level": "medium"},
            "competitive_pressure": {"weight": 0.4, "level": "high"},
            "legal_review": {"weight": 0.2, "level": "medium"},
            "negative_sentiment": {"weight": 0.5, "level": "high"},
            "discount_request": {"weight": 0.3, "level": "medium"},
            "unrealistic_timeline": {"weight": 0.4, "level": "high"},
            "budget_mismatch": {"weight": 0.35, "level": "medium"},
            "scope_creep": {"weight": 0.25, "level": "low"},
        }

    def assess_deal_risk(
        self,
        deal_value: float,
        client_history: Dict,
        negotiation_flags: List[str],
        service_complexity: str = "medium",
    ) -> Dict[str, Any]:
        """Bitim riskini baholash"""

        total_risk_score = 0
        risk_breakdown = []
        recommendations = []

        # Flag-based risks
        for flag in negotiation_flags:
            if flag in self.risk_factors:
                factor = self.risk_factors[flag]
                total_risk_score += factor["weight"]
                risk_breakdown.append(
                    {
                        "factor": flag,
                        "weight": factor["weight"],
                        "level": factor["level"],
                    }
                )

                # Add recommendations
                if flag == "price_pressure":
                    recommendations.append(
                        "Qiymat asoslangan ROI hisobotini taqdim eting"
                    )
                elif flag == "competitive_pressure":
                    recommendations.append(
                        "Differentiation strategiyasini kuchaytiring"
                    )
                elif flag == "negative_sentiment":
                    recommendations.append(
                        "Human manager qo'llab-quvvatlashini talab qiling"
                    )

        # Value-based risks
        if deal_value > 20000:
            total_risk_score += 0.2
            risk_breakdown.append(
                {"factor": "high_value_deal", "weight": 0.2, "level": "high"}
            )
            recommendations.append("Katta bitim: Katta direktor tasdiqlashi kerak")

        if deal_value < 1000:
            total_risk_score += 0.15
            risk_breakdown.append(
                {"factor": "low_value_deal", "weight": 0.15, "level": "low"}
            )

        # Client history risks
        if client_history.get("previous_deals", 0) == 0:
            total_risk_score += 0.1
            risk_breakdown.append(
                {"factor": "new_client", "weight": 0.1, "level": "medium"}
            )
            recommendations.append("Yangi mijoz: 100% oldindan to'lov talab qiling")

        if client_history.get("payment_issues", False):
            total_risk_score += 0.4
            risk_breakdown.append(
                {"factor": "payment_history", "weight": 0.4, "level": "high"}
            )
            recommendations.append("To'lov muammolari: Faqat 100% oldindan to'lov")

        # Complexity risk
        complexity_weights = {"low": 0, "medium": 0.1, "high": 0.25, "enterprise": 0.35}
        complexity_risk = complexity_weights.get(service_complexity, 0.1)
        total_risk_score += complexity_risk

        # Normalize score (0-1)
        final_score = min(1.0, total_risk_score)

        # Determine level
        if final_score < 0.3:
            level = "low"
            autonomy_allowed = True
        elif final_score < 0.6:
            level = "medium"
            autonomy_allowed = True
        else:
            level = "high"
            autonomy_allowed = False

        return {
            "score": round(final_score, 2),
            "level": level,
            "autonomy_allowed": autonomy_allowed,
            "requires_approval": final_score > 0.5,
            "breakdown": risk_breakdown,
            "recommendations": recommendations,
            "contract_clauses_needed": final_score > 0.4,
        }

    def get_approval_requirements(self, risk_assessment: Dict) -> List[str]:
        """Tasdiqlash talablarini olish"""

        requirements = []

        if risk_assessment["score"] > 0.7:
            requirements.extend(
                [
                    "Senior manager tasdiqlashi",
                    "Yuridik ko'rib chiqishi",
                    "Moliyaviy tekshiruv",
                ]
            )
        elif risk_assessment["score"] > 0.5:
            requirements.extend(
                ["Manager tasdiqlashi", "Shartnoma shartlari ko'rib chiqilsin"]
            )

        if risk_assessment.get("contract_clauses_needed"):
            requirements.append("Qo'shimcha himoya bandlari qo'shilsin")

        return requirements
