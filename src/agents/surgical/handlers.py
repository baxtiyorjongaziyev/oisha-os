"""
Lifecycle hooks, CRM sync, and proactive actions mixin for SurgicalNegotiator.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from src.agents.deal_lifecycle_manager import DealStage

logger = logging.getLogger(__name__)


class SurgicalHandlersMixin:
    """Lifecycle event callbacks, CRM storage and notification delivery."""

    def _register_handlers(self):
        self.lifecycle.on_stage_change(
            DealStage.PROPOSAL, self._on_proposal_stage
        )
        self.lifecycle.on_stage_change(
            DealStage.COMMITMENT, self._on_commitment_stage
        )
        self.lifecycle.on_stage_change(DealStage.WON, self._on_deal_won)

    async def _on_proposal_stage(
        self, deal: Any, old_stage: Optional[DealStage] = None
    ):
        logger.info("Deal reached PROPOSAL stage", deal_id=deal.deal_id)
        if not deal.contract_draft:
            contract = await self._generate_contract_if_needed(deal)
            if contract:
                deal.contract_draft = contract
                self.lifecycle.save_deal(deal)

    async def _on_commitment_stage(
        self, deal: Any, old_stage: Optional[DealStage] = None
    ):
        logger.info("Deal reached COMMITMENT stage", deal_id=deal.deal_id)
        if deal.budget:
            risk = self.risk_assessor.assess_deal_risk(
                deal_id=deal.deal_id,
                deal_value=deal.budget,
                client_type="standard",
                service_type=deal.service_type or "branding_full",
                has_contract=bool(deal.contract_draft),
            )
            deal.risk_level = risk["risk_level"]
            self.lifecycle.save_deal(deal)

    async def _on_deal_won(
        self, deal: Any, old_stage: Optional[DealStage] = None
    ):
        logger.info("Deal WON!", deal_id=deal.deal_id, budget=deal.budget)
        if deal.user_id:
            await self._save_to_contacts(
                {
                    "user_id": deal.user_id,
                    "name": deal.client_name,
                    "phone": deal.phone,
                    "company": deal.company,
                }
            )

    async def _generate_contract_if_needed(self, deal: Any) -> Optional[str]:
        if not deal.service_type:
            return None

        contract_data = self.contract_gen.quick_contract(
            service_type=deal.service_type,
            client_name=deal.client_name or "Mijoz",
            total_price=deal.budget or 0,
            timeline=deal.timeline or "2-3 hafta",
        )
        return contract_data.get("contract_text")

    async def _save_to_contacts(self, user_info: Dict):
        try:
            phone = user_info.get("phone")
            name = user_info.get("name")
            if phone and name:
                await self.gcontacts.save_contact(
                    name=name,
                    phone=phone,
                    company=user_info.get("company", ""),
                    notes=f"Jon Branding client (Telegram ID: {user_info.get('user_id')})",
                )
        except Exception as e:
            logger.error("Failed to save to Google Contacts", error=str(e))

    async def _get_crm_data(self, user_id: str) -> Dict:
        crm_data = {}
        if self.db:
            try:
                user_info = self.db.get_user(int(user_id))
                if user_info:
                    crm_data["user_info"] = user_info
                history = self.db.get_conversation_history(int(user_id), limit=10)
                if history:
                    crm_data["history"] = history
            except Exception as e:
                logger.error("Failed to get DB data", error=str(e))

        if self.amocrm:
            try:
                pass
            except Exception as e:
                logger.error("Failed to get AmoCRM data", error=str(e))

        return crm_data

    async def _save_to_crm(self, user_id: str, result: Dict, deal: Any):
        if self.db:
            try:
                self.db.save_negotiation_result(
                    user_id=int(user_id),
                    deal_id=deal.deal_id,
                    stage=deal.stage.value,
                    result=result,
                )
            except Exception as e:
                logger.error("Failed to save to DB", error=str(e))

        if self.amocrm and deal.budget:
            try:
                pass
            except Exception as e:
                logger.error("Failed to save to AmoCRM", error=str(e))

    async def _send_proactive(self, user_id: int, text: str):
        if self.send_fn is not None:
            await self.send_fn(user_id, text)
        else:
            logger.warning(
                "send_fn not configured; cannot send proactive message",
                user_id=user_id,
            )
