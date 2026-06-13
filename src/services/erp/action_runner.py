from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Mapping, Optional

from src.services.erp.action_queue import ActionQueue, QueueItem
from src.services.erp.approval_service import Approval, ApprovalService
from src.services.erp.compensation import CompensationService
from src.services.erp.models import VerificationResult
from src.services.erp.retry_policy import RetryPolicy
from src.services.erp.risk_policy import ERPRiskPolicy, RiskDecision


Executor = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]
Verifier = Callable[
    [dict[str, Any], dict[str, Any]],
    Awaitable[VerificationResult | dict[str, Any]],
]
ApprovalNotifier = Callable[
    [Approval, dict[str, Any], RiskDecision],
    Awaitable[None],
]


@dataclass(frozen=True)
class ActionRunResult:
    action_id: Optional[str]
    status: str
    reason: str
    retry_after_seconds: int = 0


class ActionRunner:
    def __init__(
        self,
        queue: ActionQueue,
        *,
        executors: Mapping[str, Executor],
        verifiers: Mapping[str, Verifier],
        retry_policy: Optional[RetryPolicy] = None,
        risk_policy: Optional[ERPRiskPolicy] = None,
        approval_service: Optional[ApprovalService] = None,
        approval_requested_from: str = "owner",
        approval_notifier: Optional[ApprovalNotifier] = None,
        compensation_service: Optional[CompensationService] = None,
    ):
        self.queue = queue
        self.executors = dict(executors)
        self.verifiers = dict(verifiers)
        self.retry_policy = retry_policy or RetryPolicy()
        self.risk_policy = risk_policy or ERPRiskPolicy(queue.repo.db)
        self.approval_service = approval_service or ApprovalService(queue.repo)
        self.approval_requested_from = approval_requested_from
        self.approval_notifier = approval_notifier
        self.compensation_service = compensation_service or CompensationService(queue)

    async def run_once(self, worker_id: str) -> ActionRunResult:
        item = await self.queue.claim_next(worker_id)
        if item is None:
            return ActionRunResult(None, "idle", "queue_empty")

        action_type = str(item.action["action_type"])
        if self.risk_policy is not None:
            approved = bool(
                self.approval_service
                and await self.approval_service.is_approved(item.action["action_id"])
            )
            decision = await self.risk_policy.evaluate(
                action_type=action_type,
                payload=dict(item.action.get("payload") or {}),
                module=str(item.action.get("target") or ""),
                client_id=str(
                    item.action.get("payload", {}).get("client_id")
                    or item.action.get("payload", {}).get("lead_id")
                    or ""
                ),
                approved=approved,
            )
            if not decision.allowed:
                if decision.requires_approval and self.approval_service is not None:
                    approval = await self.approval_service.request(
                        action_id=item.action["action_id"],
                        requested_from=self.approval_requested_from,
                        reason=decision.reason,
                    )
                    if self.approval_notifier is not None:
                        await self.approval_notifier(approval, item.action, decision)
                    await self.queue.wait_for_approval(item, decision.reason)
                    return ActionRunResult(
                        item.action["action_id"],
                        "waiting_approval",
                        decision.reason,
                    )
                return await self._retry_or_dead_letter(
                    item,
                    reason=decision.reason,
                )

        executor = self.executors.get(action_type)
        if executor is None:
            return await self._fail(
                item,
                RuntimeError(f"executor_missing:{action_type}"),
                force_permanent=True,
            )

        try:
            execution = await executor(item.action)
        except Exception as exc:
            return await self._fail(item, exc)

        verifier = self.verifiers.get(action_type)
        if verifier is None:
            return await self._retry_or_dead_letter(
                item,
                reason="verifier_missing",
                result=execution,
            )

        try:
            raw_verification = await verifier(item.action, execution)
            verification = self._verification_result(item, raw_verification)
        except Exception as exc:
            return await self._fail(item, exc)

        await self.queue.repo.record_verification(item.action["action_id"], verification)
        if not verification.success:
            compensation = await self.compensation_service.enqueue_for_partial_failure(
                item.action,
                verification,
            )
            if compensation is not None:
                await self.queue.wait_for_compensation(item, verification.reason)
                return ActionRunResult(
                    item.action["action_id"],
                    "compensating",
                    verification.reason,
                )
            return await self._retry_or_dead_letter(
                item,
                reason=verification.reason or "verification_failed",
                result=execution,
            )

        await self.queue.complete(item, result=execution)
        return ActionRunResult(
            action_id=item.action["action_id"],
            status="completed",
            reason=verification.reason,
        )

    async def _fail(
        self,
        item: QueueItem,
        error: BaseException,
        *,
        force_permanent: bool = False,
    ) -> ActionRunResult:
        reason = f"{type(error).__name__}:{error}"[:1000]
        if force_permanent or self.retry_policy.is_permanent(error):
            await self.queue.dead_letter(item, reason)
            return ActionRunResult(item.action["action_id"], "dead_letter", reason)
        return await self._retry_or_dead_letter(item, reason=reason)

    async def _retry_or_dead_letter(
        self,
        item: QueueItem,
        *,
        reason: str,
        result: Optional[dict[str, Any]] = None,
    ) -> ActionRunResult:
        if item.attempt_number >= self.retry_policy.max_attempts:
            await self.queue.dead_letter(item, reason, result)
            return ActionRunResult(item.action["action_id"], "dead_letter", reason)
        delay = self.retry_policy.delay_for_attempt(item.attempt_number)
        await self.queue.retry(item, reason, delay, result)
        return ActionRunResult(
            item.action["action_id"],
            "retrying",
            reason,
            retry_after_seconds=delay,
        )

    @staticmethod
    def _verification_result(
        item: QueueItem,
        value: VerificationResult | dict[str, Any],
    ) -> VerificationResult:
        if isinstance(value, VerificationResult):
            return value
        return VerificationResult(
            success=bool(value.get("success")),
            source=str(value.get("source") or item.action["target"]),
            expected=dict(value.get("expected") or item.action["expected_result"]),
            actual=dict(value.get("actual") or {}),
            reason=str(value.get("reason") or "verification_failed"),
        )
