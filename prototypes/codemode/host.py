"""CodeModeHost: one entry point for telegram.* (gateway) + amo.* (read-only) + batch approval."""
from __future__ import annotations

from typing import Any

from amo_api import AMO_READS, call_amo, render_amo_api
from batch import BatchPlan
from bridge import run_script
from src.services.core.telegram_mcp.policy import classify_tool
from ts_api import render_api


class CodeModeHost:
    def __init__(self, service: Any, amo_client: Any = None, *, allow_mutation_batch: bool = False,
                 sandbox: str = "node"):
        self.service = service
        self.amo = amo_client
        self.allow_mutation_batch = allow_mutation_batch
        self.sandbox = sandbox

    async def describe(self) -> str:
        tools = [
            t for t in await self.service.list_tools()
            if classify_tool(t.name, getattr(t, "annotations", None)).automatic
        ]
        parts = [render_api(tools, "telegram")]
        if self.amo is not None:
            parts.append(render_amo_api())
        return "\n".join(parts)

    async def run(self, script: str, **kw: Any) -> dict:
        await self.service.list_tools()
        tools = self.service._tools
        plan = BatchPlan(tools) if self.allow_mutation_batch else None
        namespaces = ("telegram", "amo") if self.amo is not None else ("telegram",)

        def is_read(q: str) -> bool:
            ns, _, name = q.partition(".")
            if ns == "amo":
                return self.amo is not None and name in AMO_READS
            t = tools.get(name)
            return ns == "telegram" and t is not None and classify_tool(
                name, getattr(t, "annotations", None)).automatic

        async def call(q: str, args: dict) -> Any:
            ns, _, name = q.partition(".")
            if ns == "amo":
                return await call_amo(self.amo, name, args)
            res = await self.service.call_tool(name, args, requester="codemode")
            sc = getattr(res, "structuredContent", None)
            if sc is not None:
                return sc
            content = getattr(res, "content", None)
            return [getattr(c, "text", None) for c in content] if content is not None else res

        result = await run_script(
            script, call, is_read, namespaces=namespaces, sandbox=self.sandbox,
            queue_mutation=plan.queue if plan else None, **kw)
        approval = await plan.submit(self.service) if plan else None
        return {"result": result, "approval": approval}
