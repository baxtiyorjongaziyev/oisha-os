from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any

from src.services.erp.action_queue import ActionQueue
from src.services.erp.identity_resolver import IdentityProfile
from src.services.erp.models import ERPAction, ERPWorkflow
from src.services.erp.negotiation_context import NegotiationContextBuilder
from src.services.erp.negotiation_policy import NegotiationPolicy
from src.services.erp.repository import ERPRepository
from src.time_utils import get_local_now


class SalesStage(str, Enum):
    NEW = "NEW"
    CONTACTED = "CONTACTED"
    QUALIFIED = "QUALIFIED"
    EXPERT_MEETING = "EXPERT_MEETING"
    PROPOSAL = "PROPOSAL"
    FOLLOW_UP = "FOLLOW_UP"
    NEGOTIATION = "NEGOTIATION"
    PAYMENT_PENDING = "PAYMENT_PENDING"
    WON = "WON"
    NURTURE = "NURTURE"
    LOST = "LOST"
    DISQUALIFIED = "DISQUALIFIED"
    HUMAN_TAKEOVER = "HUMAN_TAKEOVER"


TERMINAL_STAGES = {
    SalesStage.WON,
    SalesStage.NURTURE,
    SalesStage.LOST,
    SalesStage.DISQUALIFIED,
    SalesStage.HUMAN_TAKEOVER,
}

SALES_TRANSITIONS = {
    SalesStage.NEW: {SalesStage.CONTACTED, *TERMINAL_STAGES},
    SalesStage.CONTACTED: {SalesStage.QUALIFIED, *TERMINAL_STAGES},
    SalesStage.QUALIFIED: {SalesStage.EXPERT_MEETING, SalesStage.PROPOSAL, *TERMINAL_STAGES},
    SalesStage.EXPERT_MEETING: {SalesStage.PROPOSAL, SalesStage.FOLLOW_UP, *TERMINAL_STAGES},
    SalesStage.PROPOSAL: {SalesStage.FOLLOW_UP, SalesStage.NEGOTIATION, *TERMINAL_STAGES},
    SalesStage.FOLLOW_UP: {SalesStage.NEGOTIATION, SalesStage.PAYMENT_PENDING, *TERMINAL_STAGES},
    SalesStage.NEGOTIATION: {SalesStage.PAYMENT_PENDING, *TERMINAL_STAGES},
    SalesStage.PAYMENT_PENDING: {SalesStage.WON, SalesStage.HUMAN_TAKEOVER},
    SalesStage.WON: set(),
    SalesStage.NURTURE: {SalesStage.CONTACTED, SalesStage.LOST},
    SalesStage.LOST: set(),
    SalesStage.DISQUALIFIED: set(),
    SalesStage.HUMAN_TAKEOVER: set(),
}


class SalesWorkflowService:
    def __init__(
        self,
        repo: ERPRepository,
        action_queue: ActionQueue,
        *,
        context_builder: NegotiationContextBuilder | None = None,
        policy: NegotiationPolicy | None = None,
    ) -> None:
        self.repo = repo
        self.action_queue = action_queue
        self.context_builder = context_builder or NegotiationContextBuilder()
        self.policy = policy or NegotiationPolicy()

    async def start(
        self,
        *,
        client_id: str,
        lead_id: int,
        chat_id: int,
        reference_identity: IdentityProfile,
        context_identity: IdentityProfile,
        classification: str,
        context_kind: str,
        membership_verified: bool = False,
        telegram_messages: list[dict[str, Any]] | None = None,
        crm_history: list[dict[str, Any]] | None = None,
        approved_services: list[str] | None = None,
        approved_prices: dict[str, dict[str, float]] | None = None,
        commitments: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        context = self.context_builder.build(
            client_id=client_id,
            lead_id=lead_id,
            chat_id=chat_id,
            reference_identity=reference_identity,
            context_identity=context_identity,
            classification=classification,
            context_kind=context_kind,
            membership_verified=membership_verified,
            telegram_messages=telegram_messages or [],
            crm_history=crm_history or [],
            approved_services=approved_services or [],
            approved_prices=approved_prices or {},
            commitments=commitments or [],
        )
        workflow_id = f"sales-{uuid.uuid4().hex}"
        workflow = ERPWorkflow(
            workflow_id=workflow_id,
            workflow_type="sales",
            entity_type="amocrm_lead",
            entity_id=str(lead_id),
            correlation_id=f"client:{client_id}",
            data={
                "sales_stage": SalesStage.NEW.value,
                "context": context.to_dict(),
                "follow_up_count": 0,
                "follow_up_task_count": 0,
            },
        )
        await self.repo.create_workflow(workflow)
        return await self._workflow(workflow_id)

    async def transition(self, workflow_id: str, new_stage: SalesStage | str) -> dict[str, Any]:
        workflow = await self._workflow(workflow_id)
        current = SalesStage(workflow["data"]["sales_stage"])
        target = SalesStage(new_stage)
        if target == current:
            return workflow
        if target not in SALES_TRANSITIONS[current]:
            raise ValueError(f"illegal_sales_transition:{current.value}->{target.value}")
        data = dict(workflow["data"])
        data["sales_stage"] = target.value
        await self.repo.update_workflow_data(workflow_id, data)
        return await self._workflow(workflow_id)

    async def queue_first_reply(self, workflow_id: str, message: str) -> ERPAction:
        workflow = await self._workflow(workflow_id)
        if SalesStage(workflow["data"]["sales_stage"]) is not SalesStage.NEW:
            raise ValueError("first_reply_requires_new_stage")
        context = workflow["data"]["context"]
        action = self._action(
            workflow_id=workflow_id,
            action_type="telegram.send_message",
            target="telegram",
            payload={
                "chat_id": context["chat_id"],
                "text": message,
                "client_id": context["client_id"],
                "lead_id": context["lead_id"],
            },
            risk_level="medium",
            idempotency_key=f"{workflow_id}:first_reply",
            expected_result={"chat_id": context["chat_id"], "message_exists": True},
        )
        await self._enqueue_required(action)
        await self.transition(workflow_id, SalesStage.CONTACTED)
        return action

    async def queue_meeting(
        self,
        workflow_id: str,
        *,
        summary: str,
        start_time: str,
        duration_minutes: int,
    ) -> ERPAction:
        workflow = await self._workflow(workflow_id)
        current = SalesStage(workflow["data"]["sales_stage"])
        if current not in {SalesStage.QUALIFIED, SalesStage.EXPERT_MEETING}:
            raise ValueError("meeting_requires_qualified_stage")
        context = workflow["data"]["context"]
        action = self._action(
            workflow_id=workflow_id,
            action_type="calendar.create_meeting",
            target="calendar+amocrm",
            payload={
                "summary": summary,
                "start_time": start_time,
                "duration_minutes": int(duration_minutes),
                "lead_id": context["lead_id"],
                "client_id": context["client_id"],
                "chat_id": context["chat_id"],
            },
            risk_level="low",
            idempotency_key=f"{workflow_id}:meeting:{start_time}",
            expected_result={
                "calendar_event_exists": True,
                "amocrm_task_exists": True,
                "lead_id": context["lead_id"],
            },
        )
        await self._enqueue_required(action)
        if current is SalesStage.QUALIFIED:
            await self.transition(workflow_id, SalesStage.EXPERT_MEETING)
        return action

    async def queue_proposal(
        self,
        workflow_id: str,
        *,
        service: str,
        amount: float,
        message: str,
    ) -> ERPAction:
        workflow = await self._workflow(workflow_id)
        context = workflow["data"]["context"]
        decision = self.policy.evaluate_proposal(
            stage=workflow["data"]["sales_stage"],
            service=service,
            amount=amount,
            approved_prices=context.get("approved_prices") or {},
        )
        if not decision.allowed:
            raise ValueError(decision.reason)
        action = self._action(
            workflow_id=workflow_id,
            action_type="telegram.send_message",
            target="telegram",
            payload={
                "chat_id": context["chat_id"],
                "text": message,
                "client_id": context["client_id"],
                "lead_id": context["lead_id"],
                "service": service,
                "amount": amount,
                "operation": "proposal",
            },
            risk_level="medium",
            idempotency_key=f"{workflow_id}:proposal:{service}:{amount}",
            expected_result={"chat_id": context["chat_id"], "message_exists": True},
        )
        await self._enqueue_required(action)
        current = SalesStage(workflow["data"]["sales_stage"])
        if current in {SalesStage.QUALIFIED, SalesStage.EXPERT_MEETING}:
            await self.transition(workflow_id, SalesStage.PROPOSAL)
        return action

    async def queue_discount(
        self,
        workflow_id: str,
        *,
        discount_percent: float,
        message: str,
        owner_approved: bool = False,
    ) -> ERPAction:
        workflow = await self._workflow(workflow_id)
        decision = self.policy.evaluate_discount(
            discount_percent=discount_percent,
            owner_approved=owner_approved,
        )
        if not decision.allowed:
            raise ValueError(decision.reason)
        context = workflow["data"]["context"]
        action = self._action(
            workflow_id=workflow_id,
            action_type="negotiation.offer_discount",
            target="telegram",
            payload={
                "chat_id": context["chat_id"],
                "text": message,
                "client_id": context["client_id"],
                "lead_id": context["lead_id"],
                "discount_percent": discount_percent,
            },
            risk_level="high",
            idempotency_key=f"{workflow_id}:discount:{discount_percent}",
            expected_result={"chat_id": context["chat_id"], "message_exists": True},
        )
        await self._enqueue_required(action)
        return action

    async def queue_overdue_follow_up(
        self,
        workflow_id: str,
        *,
        due_at: datetime,
        message: str,
    ) -> list[ERPAction]:
        if due_at > get_local_now():
            raise ValueError("follow_up_not_due")
        workflow = await self._workflow(workflow_id)
        data = dict(workflow["data"])
        context = data["context"]
        task_number = int(data.get("follow_up_task_count") or 0) + 1
        created: list[ERPAction] = []
        task = self._action(
            workflow_id=workflow_id,
            action_type="amocrm.create_task",
            target="amocrm",
            payload={
                "lead_id": context["lead_id"],
                "text": f"Follow-up: {message}",
                "complete_till": get_local_now().isoformat(),
                "client_id": context["client_id"],
            },
            risk_level="low",
            idempotency_key=f"{workflow_id}:followup-task:{task_number}",
            expected_result={"lead_id": context["lead_id"], "task_exists": True},
        )
        if await self.action_queue.enqueue(task):
            created.append(task)
            data["follow_up_task_count"] = task_number

        follow_up_count = int(data.get("follow_up_count") or 0)
        decision = self.policy.evaluate_follow_up(unanswered_count=follow_up_count)
        if decision.allowed:
            send_number = follow_up_count + 1
            send = self._action(
                workflow_id=workflow_id,
                action_type="telegram.send_message",
                target="telegram",
                payload={
                    "chat_id": context["chat_id"],
                    "text": message,
                    "client_id": context["client_id"],
                    "lead_id": context["lead_id"],
                    "follow_up_number": send_number,
                },
                risk_level="medium",
                idempotency_key=f"{workflow_id}:followup-message:{send_number}",
                expected_result={"chat_id": context["chat_id"], "message_exists": True},
            )
            if await self.action_queue.enqueue(send):
                created.append(send)
                data["follow_up_count"] = send_number
        await self.repo.update_workflow_data(workflow_id, data)
        return created

    async def _workflow(self, workflow_id: str) -> dict[str, Any]:
        workflow = await self.repo.get_workflow(workflow_id)
        if not workflow or workflow.get("workflow_type") != "sales":
            raise ValueError(f"sales_workflow_not_found:{workflow_id}")
        return workflow

    async def _enqueue_required(self, action: ERPAction) -> None:
        if not await self.action_queue.enqueue(action):
            raise ValueError(f"duplicate_sales_action:{action.idempotency_key}")

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
