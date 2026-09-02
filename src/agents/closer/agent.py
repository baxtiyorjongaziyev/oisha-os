"""
AutonomousSalesAgent core service implementation.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from src.agents.closer.decisions import AutonomousDecisionsMixin
from src.agents.closer.models import ConversationState
from src.agents.closer.proposals import PricingEngine
from src.agents.core import BaseAgent
from src.agents.negotiation_engine import NegotiationEngine

logger = logging.getLogger(__name__)


class AutonomousSalesAgent(BaseAgent, AutonomousDecisionsMixin):
    """Avtonom sotuv agenti"""

    def __init__(self, db=None):
        super().__init__(
            agent_id="SurgicalCloser",
            system_prompt="Self-directed AI sales agent that navigates complex negotiations",
            api_keys={},
            db=db,
        )
        self.name = "Surgical Closer"
        self.description = "Self-directed AI sales agent that navigates complex negotiations"
        self.db = db
        self.pricing_engine = PricingEngine()
        self.proposal_engine = self.pricing_engine
        self.states: Dict[str, ConversationState] = {}

    async def process_task(self, task_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        if task_type == "handle_message":
            return await self.handle_incoming(
                user_id=str(payload.get("user_id")),
                message=payload.get("message", ""),
                metadata=payload.get("metadata", {}),
            )
        elif task_type == "follow_up_stale":
            return {"followed_up": await self.follow_up_stale_leads()}
        return {"error": f"Unknown task: {task_type}"}

    async def handle_incoming(
        self,
        user_id: str,
        message: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        state = await self._get_or_create_state(user_id)
        state.add_message(role="user", content=message, metadata=metadata)

        assessment = await NegotiationEngine.assess_async(
            message=message,
            crm_status=state.stage,
        )

        decision = await self._make_autonomous_decision(
            message=message,
            state=state,
            assessment=assessment,
        )

        response_text = await self._generate_response(
            message=message,
            state=state,
            decision=decision,
            assessment=assessment,
        )

        state.add_message(role="assistant", content=response_text)
        state.stage = decision["next_stage"]
        state.autonomy_level = decision["autonomy_level"]
        await self._save_state_to_db(state)

        proposal = None
        if decision.get("offer_proposal"):
            proposal = await self.proposal_engine.generate_proposal(
                service_type=state.context.get("service_type", "branding_full"),
                context=state.context,
                negotiation_margin=0.15,
            )

        return {
            "response": response_text,
            "assessment": assessment.to_payload(),
            "decision": decision,
            "stage": state.stage,
            "proposal": proposal.to_dict() if proposal else None,
            "escalate": decision.get("escalate_to_human", False),
        }

    async def generate_response(self, message: str, context: Optional[Dict] = None) -> str:
        user_id = str((context or {}).get("user_id", "default_user"))
        state = await self._get_or_create_state(user_id)
        if context:
            state.context.update(context)
        assessment = await NegotiationEngine.assess_async(message=message, crm_status=state.stage)
        decision = await self._make_autonomous_decision(message, state, assessment)
        return await self._generate_response(message, state, decision, assessment)

    async def assess_lead(self, messages: List[Dict], context: Optional[Dict] = None) -> Dict[str, Any]:
        text = " ".join(m.get("content", "") for m in messages)
        assessment = await NegotiationEngine.assess_async(message=text)
        return assessment.to_payload()

    async def _get_or_create_state(self, user_id: str) -> ConversationState:
        if user_id in self.states:
            return self.states[user_id]
        state = ConversationState(user_id=user_id)
        self.states[user_id] = state
        return state

    async def _save_state_to_db(self, state: ConversationState):
        if self.db:
            try:
                pass
            except Exception as e:
                logger.error(f"Failed to save state to DB: {e}")

    def get_active_deals(self) -> List[Dict]:
        return [
            {
                "user_id": s.user_id,
                "stage": s.stage,
                "deal_value": s.deal_value,
                "last_interaction": s.last_interaction.isoformat(),
                "is_stale": s.is_stale(),
            }
            for s in self.states.values()
            if s.stage not in ["closed_won", "closed_lost"]
        ]

    async def follow_up_stale_leads(self) -> List[Dict]:
        stale_deals = [s for s in self.states.values() if s.is_stale(hours=24)]
        results = []
        for state in stale_deals:
            followup_text = await self._generate_follow_up(state)
            results.append({"user_id": state.user_id, "message": followup_text})
        return results


_autonomous_sales_agent_instance = None


def get_autonomous_agent(db=None) -> AutonomousSalesAgent:
    global _autonomous_sales_agent_instance
    if _autonomous_sales_agent_instance is None:
        _autonomous_sales_agent_instance = AutonomousSalesAgent(db=db)
    return _autonomous_sales_agent_instance
