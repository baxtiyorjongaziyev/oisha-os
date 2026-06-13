from __future__ import annotations

import hashlib
import uuid
from enum import Enum
from typing import Any

from src.services.erp.action_queue import ActionQueue
from src.services.erp.finance_policy import FinancePolicy
from src.services.erp.models import ERPAction, ERPWorkflow
from src.services.erp.repository import ERPRepository


class FinanceStage(str, Enum):
    INCOME_ANNOUNCED = "INCOME_ANNOUNCED"
    FINANCE_REVIEW = "FINANCE_REVIEW"
    CONFIRMED = "CONFIRMED"
    AIRTABLE_RECORDED = "AIRTABLE_RECORDED"
    CRM_UPDATED = "CRM_UPDATED"
    SALES_CONGRATULATED = "SALES_CONGRATULATED"
    REJECTED = "REJECTED"


FINANCE_TRANSITIONS = {
    FinanceStage.INCOME_ANNOUNCED: {FinanceStage.FINANCE_REVIEW, FinanceStage.REJECTED},
    FinanceStage.FINANCE_REVIEW: {FinanceStage.CONFIRMED, FinanceStage.REJECTED},
    FinanceStage.CONFIRMED: {FinanceStage.AIRTABLE_RECORDED},
    FinanceStage.AIRTABLE_RECORDED: {FinanceStage.CRM_UPDATED},
    FinanceStage.CRM_UPDATED: {FinanceStage.SALES_CONGRATULATED},
    FinanceStage.SALES_CONGRATULATED: set(),
    FinanceStage.REJECTED: set(),
}


class FinanceWorkflowService:
    def __init__(
        self,
        repo: ERPRepository,
        action_queue: ActionQueue,
        *,
        policy: FinancePolicy | None = None,
    ) -> None:
        self.repo = repo
        self.action_queue = action_queue
        self.policy = policy or FinancePolicy()

    async def announce_income(
        self,
        *,
        source_event_id: str,
        amount: float,
        currency: str,
        client_id: str,
        seller_id: str,
        lead_id: int,
        deal_link: str,
        airtable_project_id: str,
        celebration_chat_id: int,
        celebration_text: str,
    ) -> dict[str, Any]:
        self.policy.validate_announcement(
            source_event_id=source_event_id,
            amount=amount,
            currency=currency,
            client_id=client_id,
            seller_id=seller_id,
            lead_id=lead_id,
            deal_link=deal_link,
            airtable_project_id=airtable_project_id,
        )
        workflow_id = self._workflow_id(source_event_id)
        existing = await self.repo.get_workflow(workflow_id)
        if existing:
            return existing
        workflow = ERPWorkflow(
            workflow_id=workflow_id,
            workflow_type="finance",
            entity_type="amocrm_lead",
            entity_id=str(lead_id),
            correlation_id=f"payment:{source_event_id}",
            data={
                "finance_stage": FinanceStage.FINANCE_REVIEW.value,
                "source_event_id": source_event_id,
                "amount": float(amount),
                "currency": str(currency),
                "client_id": str(client_id),
                "seller_id": str(seller_id),
                "lead_id": int(lead_id),
                "deal_link": str(deal_link),
                "airtable_project_id": str(airtable_project_id),
                "celebration_chat_id": int(celebration_chat_id),
                "celebration_text": str(celebration_text),
            },
        )
        await self.repo.create_workflow(workflow)
        return await self._workflow(workflow_id)

    async def confirm_income(
        self,
        workflow_id: str,
        *,
        confirmed_by: str,
        confirmer_role: str,
    ) -> ERPAction:
        workflow = await self._require_stage(workflow_id, FinanceStage.FINANCE_REVIEW)
        decision = self.policy.evaluate_confirmation(confirmer_role)
        if not decision.allowed:
            raise ValueError(decision.reason)
        data = dict(workflow["data"])
        action = self._action(
            workflow_id=workflow_id,
            action_type="airtable.create_income",
            target="airtable",
            payload={
                "source_event_id": data["source_event_id"],
                "amount": data["amount"],
                "currency": data["currency"],
                "client_id": data["client_id"],
                "seller_id": data["seller_id"],
                "lead_id": data["lead_id"],
                "project_id": data["airtable_project_id"],
            },
            risk_level="low",
            idempotency_key=f"{workflow_id}:airtable-income",
            expected_result={
                "record_exists": True,
                "source_event_id": data["source_event_id"],
            },
        )
        await self._enqueue_required(action)
        data["confirmed_by"] = str(confirmed_by)
        data["airtable_action_id"] = action.action_id
        await self._set_stage(workflow_id, data, FinanceStage.CONFIRMED)
        return action

    async def reject_income(
        self,
        workflow_id: str,
        *,
        rejected_by: str,
        reason: str,
        rejecter_role: str,
    ) -> dict[str, Any]:
        workflow = await self._require_stage(workflow_id, FinanceStage.FINANCE_REVIEW)
        decision = self.policy.evaluate_confirmation(rejecter_role)
        if not decision.allowed:
            raise ValueError(decision.reason)
        data = dict(workflow["data"])
        data["rejected_by"] = str(rejected_by)
        data["rejection_reason"] = str(reason)
        return await self._set_stage(workflow_id, data, FinanceStage.REJECTED)

    async def mark_airtable_recorded(
        self,
        workflow_id: str,
        *,
        airtable_record_id: str,
    ) -> ERPAction:
        workflow = await self._require_stage(workflow_id, FinanceStage.CONFIRMED)
        data = dict(workflow["data"])
        await self._require_completed_action(data.get("airtable_action_id"))
        data["airtable_record_id"] = str(airtable_record_id)
        note = (
            f"Tasdiqlangan kirim: {data['amount']:.0f} {data['currency']}\n"
            f"Airtable record: {airtable_record_id}\n"
            f"Manba: {data['source_event_id']}"
        )
        action = self._action(
            workflow_id=workflow_id,
            action_type="amocrm.add_note",
            target="amocrm",
            payload={
                "lead_id": data["lead_id"],
                "text": note,
                "client_id": data["client_id"],
            },
            risk_level="low",
            idempotency_key=f"{workflow_id}:amocrm-income-note",
            expected_result={
                "lead_id": data["lead_id"],
                "note_exists": True,
                "text": note,
            },
        )
        await self._enqueue_required(action)
        data["crm_action_id"] = action.action_id
        await self._set_stage(workflow_id, data, FinanceStage.AIRTABLE_RECORDED)
        return action

    async def mark_crm_updated(self, workflow_id: str) -> ERPAction:
        workflow = await self._require_stage(workflow_id, FinanceStage.AIRTABLE_RECORDED)
        data = dict(workflow["data"])
        await self._require_completed_action(data.get("crm_action_id"))
        action = self._action(
            workflow_id=workflow_id,
            action_type="telegram.send_message",
            target="telegram",
            payload={
                "chat_id": data["celebration_chat_id"],
                "text": data["celebration_text"],
                "client_id": data["client_id"],
                "lead_id": data["lead_id"],
            },
            risk_level="low",
            idempotency_key=f"{workflow_id}:sales-celebration",
            expected_result={
                "chat_id": data["celebration_chat_id"],
                "message_exists": True,
            },
        )
        await self._enqueue_required(action)
        data["celebration_action_id"] = action.action_id
        await self._set_stage(workflow_id, data, FinanceStage.CRM_UPDATED)
        return action

    async def mark_sales_congratulated(self, workflow_id: str) -> dict[str, Any]:
        workflow = await self._require_stage(workflow_id, FinanceStage.CRM_UPDATED)
        data = dict(workflow["data"])
        await self._require_completed_action(data.get("celebration_action_id"))
        return await self._set_stage(workflow_id, data, FinanceStage.SALES_CONGRATULATED)

    async def queue_adjustment(
        self,
        workflow_id: str,
        *,
        operation: str,
        amount: float,
        owner_approved: bool,
    ) -> ERPAction:
        workflow = await self._workflow(workflow_id)
        decision = self.policy.evaluate_adjustment(
            operation=operation,
            amount=amount,
            owner_approved=owner_approved,
        )
        if not decision.allowed:
            raise ValueError(decision.reason)
        data = workflow["data"]
        action = self._action(
            workflow_id=workflow_id,
            action_type=f"finance.{operation}",
            target="finance",
            payload={
                "operation": operation,
                "amount": float(amount),
                "lead_id": data["lead_id"],
                "client_id": data["client_id"],
            },
            risk_level="critical",
            idempotency_key=f"{workflow_id}:{operation}:{amount}",
            expected_result={"operation_recorded": True},
        )
        await self._enqueue_required(action)
        return action

    def assert_final_file_handoff_allowed(
        self,
        *,
        contract_total: float,
        confirmed_paid: float,
    ) -> bool:
        return self.policy.assert_final_file_handoff_allowed(
            contract_total=contract_total,
            confirmed_paid=confirmed_paid,
        )

    async def _require_completed_action(self, action_id: Any) -> None:
        action = await self.repo.get_action(str(action_id or ""))
        if not action or action.get("status") != "completed":
            raise ValueError(f"verified_action_required:{action_id}")

    async def _require_stage(
        self,
        workflow_id: str,
        stage: FinanceStage,
    ) -> dict[str, Any]:
        workflow = await self._workflow(workflow_id)
        actual = FinanceStage(workflow["data"]["finance_stage"])
        if actual is not stage:
            raise ValueError(f"finance_stage_required:{stage.value}:actual:{actual.value}")
        return workflow

    async def _set_stage(
        self,
        workflow_id: str,
        data: dict[str, Any],
        stage: FinanceStage,
    ) -> dict[str, Any]:
        current = FinanceStage(data["finance_stage"])
        if stage not in FINANCE_TRANSITIONS[current]:
            raise ValueError(f"illegal_finance_transition:{current.value}->{stage.value}")
        data["finance_stage"] = stage.value
        await self.repo.update_workflow_data(workflow_id, data)
        return await self._workflow(workflow_id)

    async def _workflow(self, workflow_id: str) -> dict[str, Any]:
        workflow = await self.repo.get_workflow(workflow_id)
        if not workflow or workflow.get("workflow_type") != "finance":
            raise ValueError(f"finance_workflow_not_found:{workflow_id}")
        return workflow

    async def _enqueue_required(self, action: ERPAction) -> None:
        if not await self.action_queue.enqueue(action):
            raise ValueError(f"duplicate_finance_action:{action.idempotency_key}")

    @staticmethod
    def _workflow_id(source_event_id: str) -> str:
        digest = hashlib.sha256(str(source_event_id).encode("utf-8")).hexdigest()[:32]
        return f"finance-{digest}"

    @staticmethod
    def _action(
        *,
        workflow_id: str,
        action_type: str,
        target: str,
        payload: dict[str, Any],
        risk_level: str,
        idempotency_key: str,
        expected_result: dict[str, Any],
    ) -> ERPAction:
        return ERPAction(
            action_id=f"action-{uuid.uuid4().hex}",
            workflow_id=workflow_id,
            action_type=action_type,
            target=target,
            payload=payload,
            risk_level=risk_level,
            idempotency_key=idempotency_key,
            expected_result=expected_result,
        )
