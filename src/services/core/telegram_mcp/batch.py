"""Batch approval: script-queued mutations become ONE owner approval, not N."""
from __future__ import annotations

from typing import Any

from .policy import classify_tool

BATCH_TOOL = "codemode_batch"
MAX_ACTIONS = 20


class BatchPlan:
    def __init__(self, tools: dict[str, Any]):
        self._tools = tools
        self.actions: list[dict[str, Any]] = []

    def queue(self, qname: str, args: dict) -> dict:
        ns, _, tool = qname.partition(".")
        if ns != "telegram" or tool not in self._tools:
            raise ValueError(f"{qname}: not queueable")
        decision = classify_tool(tool, getattr(self._tools[tool], "annotations", None))
        if decision.automatic:
            raise ValueError(f"{qname}: read tools run directly")
        if decision.risk == "destructive":
            raise ValueError(f"{qname}: destructive actions need individual approval")
        if len(self.actions) >= MAX_ACTIONS:
            raise ValueError(f"batch limit {MAX_ACTIONS} reached")
        self.actions.append({"tool": tool, "arguments": dict(args)})
        return {"queued": len(self.actions) - 1}

    async def submit(self, service: Any, requester: str = "codemode") -> dict | None:
        if not self.actions:
            return None
        op = await service.store.create(
            BATCH_TOOL,
            {"actions": self.actions, "count": len(self.actions)},
            requester,
            service.approval_ttl_seconds,
            risk="mutation",
        )
        try:
            await service.notifier.notify(op)
        except Exception as exc:
            await service.store.finish_notification_failure(op.id, type(exc).__name__)
            raise RuntimeError("Owner approval notification failed") from exc
        return {"status": "pending_approval", "operation_id": op.id, "actions": len(self.actions)}


class BatchUpstream:
    """Wrap the real upstream for ApprovalExecutor: expands codemode_batch after approval."""

    def __init__(self, real: Any):
        self.real = real

    async def list_tools(self):
        return await self.real.list_tools()

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        if name != BATCH_TOOL:
            return await self.real.call_tool(name, arguments)
        actions = arguments.get("actions") or []
        if not 0 < len(actions) <= MAX_ACTIONS:
            raise ValueError("invalid batch size")
        tools = {t.name: t for t in await self.real.list_tools()}
        for a in actions:  # re-validate at execution time, policy may have changed
            t = tools.get(a["tool"])
            if t is None or classify_tool(a["tool"], getattr(t, "annotations", None)).risk != "mutation":
                raise ValueError("batch contains a disallowed action")
        results = []
        for a in actions:  # sequential, stop at first failure
            r = await self.real.call_tool(a["tool"], a["arguments"])
            results.append(r)
            if getattr(r, "isError", False):
                break
        return {"executed": len(results), "total": len(actions), "results": results}
