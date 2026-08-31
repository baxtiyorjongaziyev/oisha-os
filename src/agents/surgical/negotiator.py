"""
SurgicalNegotiator core orchestrator implementation.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import structlog

from src.agents.autonomous_sales_agent import get_autonomous_agent
from src.agents.contracts import ContractGenerator, RiskAssessor
from src.agents.deal_lifecycle_manager import (
    DealPriority,
    DealStage,
    get_lifecycle_manager,
)
from src.agents.surgical.handlers import SurgicalHandlersMixin
from src.services.core.gcontacts import GoogleContactsSync

logger = structlog.get_logger()


class SurgicalNegotiator(SurgicalHandlersMixin):
    """Asosiy negotiator - barcha komponentlarni muvofiqlashtiruvchi."""

    def __init__(self, db=None, amocrm=None, send_fn=None):
        self.db = db
        self.amocrm = amocrm
        self.send_fn = send_fn

        self.sales_agent = get_autonomous_agent(db=db)
        self.lifecycle = get_lifecycle_manager()
        if self.send_fn is not None and self.lifecycle.send_fn is None:
            self.lifecycle.send_fn = self.send_fn
        self.contract_gen = ContractGenerator()
        self.risk_assessor = RiskAssessor()
        self.gcontacts = GoogleContactsSync()

        self._register_handlers()
        self.active_sessions: Dict[str, Dict] = {}

    async def handle_lead(
        self,
        user_id: str,
        message: str,
        channel: str = "telegram",
        metadata: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        logger.info("Handling lead", user_id=user_id, channel=channel)
        deal = self.lifecycle.get_deal_by_user(user_id)
        if not deal:
            deal = self.lifecycle.create_deal(
                client_name=metadata.get("name", "Noma'lum") if metadata else "Noma'lum",
                user_id=user_id,
                channel=channel,
                priority=DealPriority.MEDIUM,
            )

        crm_data = await self._get_crm_data(user_id)
        context = {
            "deal_id": deal.deal_id,
            "stage": deal.stage.value,
            "budget": deal.budget,
            "service_type": deal.service_type,
            "channel": channel,
            "crm_data": crm_data,
            "metadata": metadata or {},
        }

        response = await self.sales_agent.generate_response(
            message=message,
            context=context,
        )

        assessment = await self.sales_agent.assess_lead(
            messages=[{"role": "user", "content": message}],
            context=context,
        )
        await self._update_deal_from_assessment(deal, assessment)

        autonomy_level = self._determine_autonomy(deal, message)
        needs_human = autonomy_level == "human_escalation"

        await self._save_to_crm(
            user_id,
            {
                "response": response,
                "assessment": assessment,
                "needs_human": needs_human,
            },
            deal,
        )

        return {
            "response": response,
            "deal_id": deal.deal_id,
            "stage": deal.stage.value,
            "autonomy_level": autonomy_level,
            "needs_human": needs_human,
            "assessment": assessment,
        }

    async def _update_deal_from_assessment(self, deal: Any, assessment: Dict):
        if assessment.get("budget"):
            deal.budget = assessment["budget"]
        if assessment.get("service_type"):
            deal.service_type = assessment["service_type"]
        if assessment.get("timeline"):
            deal.timeline = assessment["timeline"]
        if assessment.get("phone"):
            deal.phone = assessment["phone"]
        if assessment.get("name"):
            deal.client_name = assessment["name"]

        proposed_stage = assessment.get("proposed_stage")
        if proposed_stage and hasattr(DealStage, proposed_stage.upper()):
            target_stage = DealStage[proposed_stage.upper()]
            if self._is_stage_advanced(deal.stage, target_stage):
                self.lifecycle.transition_stage(
                    deal.deal_id,
                    target_stage,
                    reason="AI assessment advancement",
                )
        self.lifecycle.save_deal(deal)

    def _is_stage_advanced(self, current: DealStage, proposed: DealStage) -> bool:
        stage_order = [
            DealStage.LEAD,
            DealStage.QUALIFIED,
            DealStage.DISCOVERY,
            DealStage.PROPOSAL,
            DealStage.NEGOTIATION,
            DealStage.COMMITMENT,
            DealStage.WON,
        ]
        try:
            return stage_order.index(proposed) > stage_order.index(current)
        except ValueError:
            return False

    def _determine_autonomy(self, deal: Any, message: str) -> str:
        escalation_keywords = [
            "direktor", "rahbar", "shikoyat", "yurist", "sud",
            "muammo", "noto'g'ri", "aldadingiz",
        ]
        if any(w in message.lower() for w in escalation_keywords):
            return "human_escalation"
        if deal.budget and deal.budget > 50_000_000:
            return "semi_autonomous"
        return "fully_autonomous"

    async def run_daily_cycle(self) -> Dict[str, Any]:
        logger.info("Running daily surgical negotiation cycle")
        re_engaged = await self.lifecycle.auto_re_engage_stale_deals()

        deals = self.lifecycle.get_active_deals()
        at_risk = []
        for deal in deals:
            if deal.stage in [DealStage.PROPOSAL, DealStage.NEGOTIATION]:
                risk = self.risk_assessor.assess_deal_risk(
                    deal_id=deal.deal_id,
                    deal_value=deal.budget or 0,
                    client_type="standard",
                    service_type=deal.service_type or "branding_full",
                    has_contract=bool(deal.contract_draft),
                )
                if risk["risk_level"] in ["high", "critical"]:
                    at_risk.append(
                        {
                            "deal_id": deal.deal_id,
                            "client": deal.client_name,
                            "risk_level": risk["risk_level"],
                            "issues": risk.get("risk_factors", []),
                        }
                    )

        return {
            "re_engaged_count": len(re_engaged),
            "active_deals_count": len(deals),
            "at_risk_deals": at_risk,
            "timestamp": datetime.now().isoformat(),
        }

    def get_dashboard(self) -> Dict[str, Any]:
        return {
            "pipeline": self.lifecycle.get_pipeline_summary(),
            "active_sessions": len(self.active_sessions),
            "components": {
                "sales_agent": "ready",
                "lifecycle_manager": "ready",
                "contract_generator": "ready",
                "risk_assessor": "ready",
            },
        }


_surgical_negotiator_instance = None


def get_surgical_negotiator(db=None, amocrm=None, send_fn=None) -> SurgicalNegotiator:
    global _surgical_negotiator_instance
    if _surgical_negotiator_instance is None:
        _surgical_negotiator_instance = SurgicalNegotiator(
            db=db, amocrm=amocrm, send_fn=send_fn
        )
    return _surgical_negotiator_instance


async def negotiate(user_id: str, message: str, **kwargs) -> Dict[str, Any]:
    negotiator = get_surgical_negotiator()
    return await negotiator.handle_lead(user_id, message, **kwargs)
