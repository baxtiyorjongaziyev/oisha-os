from __future__ import annotations

from typing import Any

from .models import ExecutionOutcome
from .policy import classify_tool
from .store import payload_digest
import logging
logger = logging.getLogger(__name__)


_default_executor: "ApprovalExecutor | None" = None


class ApprovalExecutor:
    def __init__(self, store: Any, upstream: Any, owner_id: int):
        self.store = store
        self.upstream = upstream
        self.owner_id = int(owner_id or 0)

    async def approve(self, operation_id: str, actor_id: int) -> ExecutionOutcome:
        if not self.owner_id or int(actor_id) != self.owner_id:
            return ExecutionOutcome(
                "denied", "Bu amal faqat egaga ruxsat.", "⛔ Rad etildi", operation_id
            )
        operation = await self.store.claim(operation_id, int(actor_id), self.owner_id)
        if operation is None:
            return ExecutionOutcome(
                "not_pending",
                "So‘rov topilmadi, muddati o‘tgan yoki avval bajarilgan.",
                "ℹ️ Faol emas",
                operation_id,
            )
        if payload_digest(operation.tool_name, operation.arguments) != operation.payload_hash:
            await self.store.finish(operation_id, "failed", "payload hash mismatch")
            return ExecutionOutcome(
                "failed", "So‘rov yaxlitligi buzilgan.", "⚠️ Bajarilmadi", operation_id
            )
        decision = classify_tool(operation.tool_name, None)
        if decision.automatic:
            await self.store.finish(operation_id, "failed", "policy changed unexpectedly")
            return ExecutionOutcome(
                "failed", "Siyosat tekshiruvi muvaffaqiyatsiz.", "⚠️ Bajarilmadi", operation_id
            )
        try:
            result = await self.upstream.call_tool(
                operation.tool_name, operation.arguments
            )
        except Exception as exc:
            logger.error("Exception handled in %s", __name__, exc_info=True)
            await self.store.finish(operation_id, "failed", type(exc).__name__)
            return ExecutionOutcome(
                "failed", "Telegram amali bajarilmadi.", "⚠️ Xato", operation_id
            )
        summary = _result_summary(result)
        await self.store.finish(operation_id, "succeeded", summary)
        return ExecutionOutcome(
            "succeeded", "Amal bajarildi.", "✅ Bajarildi", operation_id, result
        )

    async def cancel(self, operation_id: str, actor_id: int) -> ExecutionOutcome:
        if not self.owner_id or int(actor_id) != self.owner_id:
            return ExecutionOutcome(
                "denied", "Bu amal faqat egaga ruxsat.", "⛔ Rad etildi", operation_id
            )
        cancelled = await self.store.cancel(operation_id, int(actor_id), self.owner_id)
        if not cancelled:
            return ExecutionOutcome(
                "not_pending", "So‘rov faol emas.", "ℹ️ Faol emas", operation_id
            )
        return ExecutionOutcome(
            "cancelled", "Amal bekor qilindi.", "❌ Bekor qilindi", operation_id
        )


def _result_summary(result: Any) -> str:
    # Never persist Telegram message bodies returned by the upstream tool.
    is_error = bool(getattr(result, "isError", False))
    return f"{type(result).__name__}:is_error={is_error}"


async def get_default_executor() -> ApprovalExecutor:
    """Return the process-wide executor used by AdminBot callbacks."""
    global _default_executor
    if _default_executor is not None:
        return _default_executor

    from src.settings import settings
    from .store import ApprovalStore
    from .upstream import UpstreamClient

    if not settings.TELEGRAM_MCP_ENABLED:
        raise RuntimeError("Telegram MCP is disabled")
    store = ApprovalStore("data/telegram_mcp_approvals.db")
    await store.initialize()
    upstream = UpstreamClient(settings.TELEGRAM_MCP_UPSTREAM_URL)
    _default_executor = ApprovalExecutor(store, upstream, settings.OWNER_ID)
    return _default_executor
