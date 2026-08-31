"""
DealLifecycleManager core service implementation.
"""
from __future__ import annotations

import asyncio
from typing import Any, Callable, Dict, List, Optional
import uuid

from src.agents.pipeline.automations import LifecycleAutomationsMixin
from src.agents.pipeline.models import Deal, DealPriority, DealStage


class DealLifecycleManager(LifecycleAutomationsMixin):
    """Bitim lifecycle'ni boshqarish."""

    def __init__(self, send_fn: Optional[Callable] = None):
        self.deals: Dict[str, Deal] = {}
        self.stage_handlers: Dict[DealStage, List[Callable]] = {}
        self.send_fn = send_fn
        self._setup_default_rules()

    def create_deal(
        self,
        client_name: str = "",
        user_id: str = "",
        channel: str = "telegram",
        priority: DealPriority = DealPriority.WARM,
        service_type: str = "",
        value: Optional[float] = None,
        source: str = "telegram",
    ) -> Deal:
        deal_id = f"deal_{uuid.uuid4().hex[:8]}"
        deal = Deal(
            id=deal_id,
            user_id=user_id,
            client_name=client_name,
            channel=channel,
            priority=priority,
            service_type=service_type,
            value=value,
            budget=value,
            source=source,
        )
        deal._update_next_action()
        self.deals[deal_id] = deal
        return deal

    def save_deal(self, deal: Deal):
        self.deals[deal.id] = deal

    def get_deal(self, deal_id: str) -> Optional[Deal]:
        return self.deals.get(deal_id)

    def get_deal_by_user(self, user_id: str) -> Optional[Deal]:
        for deal in reversed(list(self.deals.values())):
            if deal.user_id == str(user_id) and deal.stage not in [
                DealStage.CLOSED_WON,
                DealStage.CLOSED_LOST,
            ]:
                return deal
        return None

    def get_active_deals(self) -> List[Deal]:
        return [
            d for d in self.deals.values()
            if d.stage not in [DealStage.CLOSED_WON, DealStage.CLOSED_LOST]
        ]

    def advance_stage(
        self,
        deal_id: str,
        new_stage: DealStage,
        reason: str = "",
    ) -> Optional[Deal]:
        deal = self.get_deal(deal_id)
        if not deal:
            return None
        old_stage = deal.stage
        deal.update_stage(new_stage, reason)
        asyncio.create_task(self._trigger_handlers(deal, old_stage))
        return deal

    def transition_stage(
        self,
        deal_id: str,
        new_stage: DealStage,
        reason: str = "",
    ) -> Optional[Deal]:
        return self.advance_stage(deal_id, new_stage, reason)

    def on_stage_change(self, stage: DealStage, handler: Callable):
        self.register_stage_handler(stage, handler)

    def register_stage_handler(
        self, stage: DealStage, handler: Callable[[Deal, Optional[DealStage]], Any]
    ):
        if stage not in self.stage_handlers:
            self.stage_handlers[stage] = []
        self.stage_handlers[stage].append(handler)

    async def _trigger_handlers(self, deal: Deal, old_stage: DealStage):
        if deal.stage in self.stage_handlers:
            for handler in self.stage_handlers[deal.stage]:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        await handler(deal, old_stage)
                    else:
                        handler(deal, old_stage)
                except Exception:
                    pass

    def get_deals_by_stage(self, stage: DealStage) -> List[Deal]:
        return [d for d in self.deals.values() if d.stage == stage]

    def get_overdue_deals(self) -> List[Deal]:
        return [d for d in self.deals.values() if d.is_overdue()]

    def close_deal(
        self,
        deal_id: str,
        won: bool = True,
        reason: str = "",
        final_value: Optional[float] = None,
    ) -> Optional[Deal]:
        target = DealStage.CLOSED_WON if won else DealStage.CLOSED_LOST
        deal = self.advance_stage(deal_id, target, reason)
        if deal and final_value:
            deal.value = final_value
            deal.budget = final_value
        return deal

    async def auto_re_engage_stale_deals(self) -> List[Dict]:
        return await self.run_automation_cycle()


_lifecycle_manager_instance = None


def get_lifecycle_manager(send_fn: Optional[Callable] = None) -> DealLifecycleManager:
    global _lifecycle_manager_instance
    if _lifecycle_manager_instance is None:
        _lifecycle_manager_instance = DealLifecycleManager(send_fn=send_fn)
    elif send_fn is not None and _lifecycle_manager_instance.send_fn is None:
        _lifecycle_manager_instance.send_fn = send_fn
    return _lifecycle_manager_instance
