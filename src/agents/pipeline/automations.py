"""
Automation rules and lifecycle actions mixin.
"""
from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional
from datetime import datetime

from src.agents.pipeline.models import Deal, DealPriority, DealStage

logger = logging.getLogger(__name__)


class LifecycleAutomationsMixin:
    """Automation cycle, actions dispatch and reporting."""

    def _setup_default_rules(self):
        self.rules = [
            {
                "name": "revive_no_response",
                "condition": lambda d: d.stage == DealStage.NO_RESPONSE and d.days_in_stage() >= 3,
                "action": self._action_revival,
            },
            {
                "name": "proposal_followup",
                "condition": lambda d: d.stage == DealStage.PROPOSAL and d.days_in_stage() >= 2,
                "action": self._action_proposal_reminder,
            },
            {
                "name": "negotiation_urgency",
                "condition": lambda d: d.stage == DealStage.NEGOTIATION and d.days_in_stage() >= 5,
                "action": self._action_urgency,
            },
            {
                "name": "commitment_to_close",
                "condition": lambda d: d.stage == DealStage.COMMITMENT and d.days_in_stage() >= 1,
                "action": self._action_prepare_contract,
            },
        ]

    async def run_automation_cycle(self) -> List[Dict]:
        actions_taken = []
        for deal in list(self.deals.values()):
            if deal.stage in [DealStage.CLOSED_WON, DealStage.CLOSED_LOST]:
                continue
            for rule in self.rules:
                try:
                    if rule["condition"](deal):
                        result = await rule["action"](deal)
                        actions_taken.append(
                            {
                                "deal_id": deal.id,
                                "rule": rule["name"],
                                "result": result,
                                "timestamp": datetime.now().isoformat(),
                            }
                        )
                except Exception as e:
                    logger.error(f"Rule {rule['name']} failed for deal {deal.id}: {e}")
        return actions_taken

    async def _action_revival(self, deal: Deal) -> Dict:
        text = "Salom! Sizning loyihangiz bo'yicha yana bir bor aloqaga chiqmoqchi edik. Yangi takliflarimiz bor!"
        await self._dispatch(deal.user_id, text)
        return {"action": "revival_sent", "user_id": deal.user_id}

    async def _action_proposal_reminder(self, deal: Deal) -> Dict:
        text = "Salom! Yuborilgan taklif bilan tanishib chiqishga ulgurdingizmi? Savollaringiz bo'lsa, javob berishga tayyormiz."
        await self._dispatch(deal.user_id, text)
        return {"action": "proposal_reminder_sent", "user_id": deal.user_id}

    async def _action_urgency(self, deal: Deal) -> Dict:
        text = "Hurmatli mijoz, ushbu narx taklifimiz faqat shu hafta oxirigacha amal qiladi."
        await self._dispatch(deal.user_id, text)
        return {"action": "urgency_sent", "user_id": deal.user_id}

    async def _action_prepare_contract(self, deal: Deal) -> Dict:
        return {"action": "contract_preparation_ready", "deal_id": deal.id}

    async def _dispatch(self, user_id: str, text: str) -> None:
        if self.send_fn is not None:
            try:
                await self.send_fn(int(user_id), text)
            except Exception as e:
                logger.error(f"Failed to dispatch proactive message to {user_id}: {e}")
        else:
            logger.debug(f"[PROACTIVE NO-SEND] No send_fn wired; would send to {user_id}: {text[:50]}...")

    def get_pipeline_stats(self) -> Dict[str, Any]:
        deals = list(self.deals.values())
        stage_counts = {}
        stage_values = {}
        for stage in DealStage:
            matching = [d for d in deals if d.stage == stage]
            stage_counts[stage.value] = len(matching)
            stage_values[stage.value] = sum((d.value or d.budget or 0) for d in matching)

        total_active = sum(1 for d in deals if d.stage not in [DealStage.CLOSED_WON, DealStage.CLOSED_LOST])
        total_won = len([d for d in deals if d.stage == DealStage.CLOSED_WON])
        total_lost = len([d for d in deals if d.stage == DealStage.CLOSED_LOST])
        total_concluded = total_won + total_lost

        return {
            "total_deals": len(deals),
            "active_deals": total_active,
            "stage_counts": stage_counts,
            "stage_values": stage_values,
            "total_pipeline_value": sum((d.value or d.budget or 0) for d in deals),
            "win_rate": round(total_won / total_concluded * 100, 1) if total_concluded > 0 else 0,
            "overdue_count": len([d for d in deals if d.is_overdue()]),
        }

    def get_pipeline_summary(self) -> Dict[str, Any]:
        return self.get_pipeline_stats()

    def export_pipeline_report(self) -> str:
        stats = self.get_pipeline_stats()
        report = f"""
*Jon Branding Pipeline Hisoboti*
Sana: {datetime.now().strftime('%Y-%m-%d %H:%M')}

Jami bitimlar: {stats['total_deals']}
Aktiv bitimlar: {stats['active_deals']}
Muddati o'tganlar: {stats['overdue_count']}
Win rate: {stats['win_rate']}%

*Bosqichlar bo'yicha:*
"""
        for stage, count in stats["stage_counts"].items():
            val = stats["stage_values"].get(stage, 0)
            report += f"- {stage}: {count} ta ({val:,.0f} so'm)\n"
        return report.strip()
