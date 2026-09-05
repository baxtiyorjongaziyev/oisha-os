"""
Dynamic Proposal generator and pricing engine for Autonomous Closer.
"""
from __future__ import annotations

from typing import Dict, List
from src.agents.closer.models import DealProposal


class PricingEngine:
    """Dinamik narx va taklif yaratuvchi"""
    """Dinamik taklif yaratuvchi"""

    def __init__(self):
        self.base_prices = {
            "branding_full": 15_000_000,
            "logo_design": 5_000_000,
            "packaging": 8_000_000,
            "rebranding": 12_000_000,
            "strategy": 7_000_000,
        }

    async def generate_proposal(
        self,
        service_type: str,
        context: Dict,
        negotiation_margin: float = 0.15,
    ) -> DealProposal:
        base = self.base_prices.get(service_type, 10_000_000)
        budget = context.get("budget", base)

        discount = 0.0
        if budget < base and (base - budget) / base <= negotiation_margin:
            discount = ((base - budget) / base) * 100

        scope = {
            "tier": "standard" if discount > 0 else "premium",
            "includes": self._get_scope_includes(service_type, "standard"),
            "revisions": 3 if discount > 0 else 5,
        }

        timeline = self._get_timeline(scope["tier"], context.get("urgency", "normal"))

        return DealProposal(
            service_type=service_type,
            base_price=base,
            scope=scope,
            timeline=timeline,
            discount_pct=discount,
            special_terms=["30 kunlik kafolat", "Bepul konsultatsiya"],
        )

    def get_price_range(self, context: Dict) -> Dict:
        service = context.get("service_type", "branding_full")
        base = self.base_prices.get(service, 10_000_000)
        return {"min": base * 0.85, "standard": base, "premium": base * 1.5}

    def _get_scope_includes(self, service: str, scope: str) -> List[str]:
        scopes = {
            "branding_full": ["Logo dizayn", "Brandbook", "Vizitka", "Blank", "Ijtimoiy tarmoq shablonlari"],
            "logo_design": ["3 ta logo varianti", "Fayllar (AI, PNG, SVG)", "Ranglar palitrasi"],
            "packaging": ["Qadoq dizayni", "3D vizualizatsiya", "Boshqa formatlar"],
            "rebranding": ["Audit", "Yangi vizual til", "Brendbook yangilanishi"],
            "strategy": ["Bozor tahlili", "Pozitsiyalash", "Mijoz portreti"],
        }
        return scopes.get(service, ["Standart xizmatlar to'plami"])

    def _get_timeline(self, scope: str, urgency: str) -> str:
        if urgency == "urgent":
            return "3-5 ish kuni"
        elif scope == "premium":
            return "2-3 hafta"
        return "1-2 hafta"

ProposalEngine = PricingEngine
