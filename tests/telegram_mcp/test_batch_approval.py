import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace as NS

import pytest

from src.services.core.telegram_mcp.approval_ui import build_approval_card
from src.services.core.telegram_mcp.batch import BATCH_TOOL, MAX_ACTIONS, BatchPlan, BatchUpstream
from src.services.core.telegram_mcp.models import PendingOperation


def _tool(name, ro=False):
    return NS(name=name, annotations={"readOnlyHint": True} if ro else {})


class _Upstream:
    def __init__(self):
        self.calls = []
        self.tools = [_tool("send_message"), _tool("delete_message"), _tool("get_me", ro=True)]

    async def list_tools(self):
        return self.tools

    async def call_tool(self, name, args):
        self.calls.append((name, args))
        return {"ok": name}


def _op(actions):
    now = datetime.now(timezone.utc)
    return PendingOperation(
        id="op_1", tool_name=BATCH_TOOL, arguments={"actions": actions}, requester="codemode",
        payload_hash="h", risk="mutation", status="pending",
        created_at=now, expires_at=now + timedelta(minutes=15),
    )


def test_card_lists_every_action_not_truncated_json():
    actions = [{"tool": "send_message", "arguments": {"text": f"hi {i}"}} for i in range(20)]
    text, kb = build_approval_card(_op(actions))
    assert "Paket tasdiq: 20" in text
    assert "20. send_message" in text and "hi 19" in text
    assert kb["inline_keyboard"][0][0]["callback_data"] == "mcp:approve:op_1"
    assert len(text) < 4096


def test_card_redacts_secrets_in_batch():
    text, _ = build_approval_card(_op([{"tool": "send_message", "arguments": {"token": "SECRET123"}}]))
    assert "SECRET123" not in text


def test_plan_rules():
    tools = {t.name: t for t in _Upstream().tools}
    plan = BatchPlan(tools)
    assert plan.queue("telegram.send_message", {"text": "a"}) == {"queued": 0}
    for bad in ("telegram.delete_message", "telegram.get_me", "amo.get_leads", "telegram.nope"):
        with pytest.raises(ValueError):
            plan.queue(bad, {})
    for _ in range(MAX_ACTIONS - 1):
        plan.queue("telegram.send_message", {})
    with pytest.raises(ValueError, match="limit"):
        plan.queue("telegram.send_message", {})


def test_batch_upstream_passthrough_and_revalidation():
    up = _Upstream()
    bu = BatchUpstream(up)
    assert asyncio.run(bu.call_tool("send_message", {"text": "x"})) == {"ok": "send_message"}
    out = asyncio.run(bu.call_tool(BATCH_TOOL, {"actions": [{"tool": "send_message", "arguments": {}}] * 2}))
    assert out["executed"] == 2
    with pytest.raises(ValueError):
        asyncio.run(bu.call_tool(BATCH_TOOL, {"actions": [{"tool": "delete_message", "arguments": {}}]}))
    with pytest.raises(ValueError):
        asyncio.run(bu.call_tool(BATCH_TOOL, {"actions": []}))
