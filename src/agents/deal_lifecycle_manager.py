"""
Deal Lifecycle Manager - Pipeline orchestration
Oisha-OS Surgical Pipeline
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Callable
from datetime import datetime, timedelta
from enum import Enum
import asyncio


class DealStage(Enum):
    """Bitim bosqichlari"""

    NEW = "new_lead"
    QUALIFIED = "qualified"
    PROPOSAL = "proposal_sent"
    NEGOTIATION = "negotiation"
    COMMITMENT = "commitment"
    CLOSED_WON = "closed_won"
    CLOSED_LOST = "closed_lost"
    NO_RESPONSE = "no_response"


class DealPriority(Enum):
    """Prioritet darajalari"""

    HOT = "hot"  # 24 soat ichida javob
    WARM = "warm"  # 72 soat
    COLD = "cold"  # 1 hafta


@dataclass
class Deal:
    """Bitim obyekti"""

    id: str
    user_id: str
    stage: DealStage = DealStage.NEW
    priority: DealPriority = DealPriority.WARM
    value: Optional[float] = None
    service_type: str = ""
    source: str = ""

    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    next_action_due: Optional[datetime] = None

    history: List[Dict[str, Any]] = field(default_factory=list)
    tasks: List[Dict[str, Any]] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    crm_lead_id: Optional[str] = None
    crm_contact_id: Optional[str] = None

    def update_stage(self, new_stage: DealStage, reason: str = ""):
        """Bosqichni yangilash"""
        old_stage = self.stage
        self.stage = new_stage
        self.updated_at = datetime.now()

        self.history.append(
            {
                "from": old_stage.value,
                "to": new_stage.value,
                "timestamp": datetime.now().isoformat(),
                "reason": reason,
            }
        )

        # Auto-set next action due
        self._update_next_action()

    def _update_next_action(self):
        """Keyingi harakat vaqtini yangilash"""
        hours_map = {DealPriority.HOT: 4, DealPriority.WARM: 24, DealPriority.COLD: 72}
        hours = hours_map.get(self.priority, 24)
        self.next_action_due = datetime.now() + timedelta(hours=hours)

    def is_overdue(self) -> bool:
        """Muddati o'tganmi"""
        if not self.next_action_due:
            return False
        return datetime.now() > self.next_action_due

    def days_in_stage(self) -> int:
        """Bosqichda qancha kun"""
        return (datetime.now() - self.updated_at).days

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "stage": self.stage.value,
            "priority": self.priority.value,
            "value": self.value,
            "service_type": self.service_type,
            "days_in_stage": self.days_in_stage(),
            "is_overdue": self.is_overdue(),
            "next_action": (
                self.next_action_due.isoformat() if self.next_action_due else None
            ),
        }


class DealLifecycleManager:
    """
    Bitim lifecycle boshqaruvchisi - to'liq pipeline orchestration
    """

    def __init__(self):
        self.deals: Dict[str, Deal] = {}
        self.stage_handlers: Dict[DealStage, List[Callable]] = {
            stage: [] for stage in DealStage
        }
        self.automation_rules: List[Dict] = []

        # Default automation rules
        self._setup_default_rules()

    def _setup_default_rules(self):
        """Default avtomatlashtirish qoidalari"""
        self.automation_rules = [
            {
                "name": "Stale Lead Revival",
                "condition": lambda d: d.days_in_stage() > 3
                and d.stage == DealStage.NEW,
                "action": "send_revival_message",
                "priority": DealPriority.WARM,
            },
            {
                "name": "Proposal Follow-up",
                "condition": lambda d: d.days_in_stage() > 2
                and d.stage == DealStage.PROPOSAL,
                "action": "send_proposal_reminder",
                "priority": DealPriority.HOT,
            },
            {
                "name": "Negotiation Push",
                "condition": lambda d: d.days_in_stage() > 5
                and d.stage == DealStage.NEGOTIATION,
                "action": "create_urgency",
                "priority": DealPriority.HOT,
            },
            {
                "name": "Commitment Close",
                "condition": lambda d: d.stage == DealStage.COMMITMENT,
                "action": "prepare_contract",
                "priority": DealPriority.HOT,
            },
        ]

    def create_deal(
        self,
        user_id: str,
        service_type: str = "",
        source: str = "telegram",
        initial_value: Optional[float] = None,
    ) -> Deal:
        """Yangi bitim yaratish"""

        deal_id = f"deal_{user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        deal = Deal(
            id=deal_id,
            user_id=user_id,
            service_type=service_type,
            source=source,
            value=initial_value,
            stage=DealStage.NEW,
            next_action_due=datetime.now() + timedelta(hours=24),
        )

        self.deals[deal_id] = deal

        # Trigger new deal handlers
        asyncio.create_task(self._trigger_handlers(deal, DealStage.NEW))

        return deal

    def get_deal(self, deal_id: str) -> Optional[Deal]:
        """Bitimni olish"""
        return self.deals.get(deal_id)

    def get_deal_by_user(self, user_id: str) -> Optional[Deal]:
        """User bo'yicha aktiv bitimni olish"""
        for deal in self.deals.values():
            if deal.user_id == user_id and deal.stage not in [
                DealStage.CLOSED_WON,
                DealStage.CLOSED_LOST,
                DealStage.NO_RESPONSE,
            ]:
                return deal
        return None

    def advance_stage(
        self,
        deal_id: str,
        new_stage: DealStage,
        reason: str = "",
        metadata: Dict = None,
    ) -> Optional[Deal]:
        """Bitimni keyingi bosqichga o'tkazish"""

        deal = self.deals.get(deal_id)
        if not deal:
            return None

        old_stage = deal.stage
        deal.update_stage(new_stage, reason)

        # Log metadata
        if metadata:
            deal.history.append(
                {
                    "type": "metadata",
                    "data": metadata,
                    "timestamp": datetime.now().isoformat(),
                }
            )

        # Trigger stage change handlers
        asyncio.create_task(self._trigger_handlers(deal, new_stage, old_stage))

        return deal

    def register_stage_handler(
        self, stage: DealStage, handler: Callable[[Deal, Optional[DealStage]], Any]
    ):
        """Bosqich handler'ini ro'yxatdan o'tkazish"""
        self.stage_handlers[stage].append(handler)

    async def _trigger_handlers(
        self, deal: Deal, stage: DealStage, old_stage: Optional[DealStage] = None
    ):
        """Handler'larni chaqirish"""
        handlers = self.stage_handlers.get(stage, [])

        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(deal, old_stage)
                else:
                    handler(deal, old_stage)
            except Exception as e:
                print(f"Handler error: {e}")

    async def run_automation_cycle(self) -> List[Dict]:
        """Avtomatlashtirish tsiklini ishlatish"""

        triggered_actions = []

        for deal in self.deals.values():
            # Skip closed deals
            if deal.stage in [DealStage.CLOSED_WON, DealStage.CLOSED_LOST]:
                continue

            # Check automation rules
            for rule in self.automation_rules:
                try:
                    if rule["condition"](deal):
                        action = await self._execute_action(
                            deal, rule["action"], rule["name"]
                        )
                        if action:
                            triggered_actions.append(
                                {
                                    "deal_id": deal.id,
                                    "rule": rule["name"],
                                    "action": rule["action"],
                                    "result": action,
                                }
                            )
                        break  # Only first matching rule
                except Exception as e:
                    print(f"Rule error: {e}")

        return triggered_actions

    async def _execute_action(
        self, deal: Deal, action_type: str, rule_name: str
    ) -> Optional[Dict]:
        """Harakatni bajarish"""

        actions = {
            "send_revival_message": self._action_revival,
            "send_proposal_reminder": self._action_proposal_reminder,
            "create_urgency": self._action_urgency,
            "prepare_contract": self._action_prepare_contract,
        }

        handler = actions.get(action_type)
        if handler:
            return await handler(deal)

        return None

    async def _action_revival(self, deal: Deal) -> Dict:
        """Eski lead'ni qayta jonlantirish"""
        deal.notes.append(f"[{datetime.now().isoformat()}] Revival message scheduled")
        return {
            "type": "message",
            "content": "Sizga yuborgan ma'lumotlar yetib bordimi? Qanday savollaringiz bor?",
            "priority": "medium",
        }

    async def _action_proposal_reminder(self, deal: Deal) -> Dict:
        """Taklif eslatmasi"""
        return {
            "type": "message",
            "content": f"Taklifimiz bo'yicha savollaringiz bormi? {deal.service_type} loyihasi qiziqtirayaptimi?",
            "priority": "high",
        }

    async def _action_urgency(self, deal: Deal) -> Dict:
        """Shoshilish yaratish"""
        return {
            "type": "offer",
            "content": "Cheklangan vaqtli taklif: 10% chegirma agar shu hafta boshlasangiz",
            "priority": "high",
        }

    async def _action_prepare_contract(self, deal: Deal) -> Dict:
        """Shartnoma tayyorlash"""
        return {
            "type": "contract",
            "content": f"Shartnoma tayyor: {deal.service_type} - ${deal.value}",
            "priority": "urgent",
            "metadata": {
                "service": deal.service_type,
                "value": deal.value,
                "user_id": deal.user_id,
            },
        }

    def get_pipeline_stats(self) -> Dict[str, Any]:
        """Pipeline statistikasi"""

        stage_counts = {stage.value: 0 for stage in DealStage}
        total_value = 0
        overdue_count = 0

        for deal in self.deals.values():
            stage_counts[deal.stage.value] += 1
            if deal.value:
                total_value += deal.value
            if deal.is_overdue():
                overdue_count += 1

        return {
            "total_deals": len(self.deals),
            "active_deals": len(
                [
                    d
                    for d in self.deals.values()
                    if d.stage not in [DealStage.CLOSED_WON, DealStage.CLOSED_LOST]
                ]
            ),
            "stage_distribution": stage_counts,
            "total_pipeline_value": total_value,
            "overdue_actions": overdue_count,
            "hot_deals": len(
                [
                    d
                    for d in self.deals.values()
                    if d.priority == DealPriority.HOT
                    and d.stage not in [DealStage.CLOSED_WON, DealStage.CLOSED_LOST]
                ]
            ),
        }

    def get_deals_by_stage(self, stage: DealStage) -> List[Deal]:
        """Bosqich bo'yicha bitimlarni olish"""
        return [d for d in self.deals.values() if d.stage == stage]

    def get_overdue_deals(self) -> List[Deal]:
        """Muddati o'tgan bitimlar"""
        return [
            d
            for d in self.deals.values()
            if d.is_overdue()
            and d.stage not in [DealStage.CLOSED_WON, DealStage.CLOSED_LOST]
        ]

    def close_deal(
        self,
        deal_id: str,
        won: bool,
        reason: str = "",
        final_value: Optional[float] = None,
    ) -> Optional[Deal]:
        """Bitimni yopish"""

        deal = self.deals.get(deal_id)
        if not deal:
            return None

        new_stage = DealStage.CLOSED_WON if won else DealStage.CLOSED_LOST

        if final_value:
            deal.value = final_value

        deal.update_stage(new_stage, reason)

        # Log close reason
        deal.history.append(
            {
                "type": "closed",
                "won": won,
                "reason": reason,
                "final_value": deal.value,
                "timestamp": datetime.now().isoformat(),
            }
        )

        return deal

    def export_pipeline_report(self) -> str:
        """Pipeline hisobotini eksport qilish"""
        stats = self.get_pipeline_stats()

        report = f"""
# Oisha-OS Pipeline Report
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}

## Summary
- Total Deals: {stats['total_deals']}
- Active Deals: {stats['active_deals']}
- Pipeline Value: ${stats['total_pipeline_value']:,.2f}
- Overdue Actions: {stats['overdue_actions']}
- Hot Deals: {stats['hot_deals']}

## Stage Distribution
"""
        for stage, count in stats["stage_distribution"].items():
            if count > 0:
                report += f"- {stage}: {count}\n"

        report += "\n## Overdue Deals\n"
        for deal in self.get_overdue_deals()[:10]:  # Top 10
            report += f"- {deal.id}: {deal.stage.value} ({deal.days_in_stage()} days)\n"

        return report


# Singleton
_lifecycle_manager: Optional[DealLifecycleManager] = None


def get_lifecycle_manager() -> DealLifecycleManager:
    """Global lifecycle manager"""
    global _lifecycle_manager
    if _lifecycle_manager is None:
        _lifecycle_manager = DealLifecycleManager()
    return _lifecycle_manager
