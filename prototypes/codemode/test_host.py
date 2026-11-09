import asyncio
from types import SimpleNamespace as NS

import pytest

from batch import BATCH_TOOL, BatchUpstream
from host import CodeModeHost
from src.services.core.telegram_mcp.gateway import GatewayService


def tool(name, ro, props=None):
    return NS(name=name, description="", outputSchema=None,
              annotations={"readOnlyHint": True} if ro else {},
              inputSchema={"type": "object", "properties": props or {}})


class Upstream:
    def __init__(self):
        self.calls = []
        self.tools = [tool("get_history", True, {"chat_id": {"type": "integer"}}),
                      tool("send_message", False, {"text": {"type": "string"}}),
                      tool("delete_message", False)]

    async def list_tools(self):
        return self.tools

    async def call_tool(self, name, args):
        self.calls.append((name, args))
        return {"ok": name}


class Store:
    def __init__(self):
        self.created = []

    async def initialize(self):
        pass

    async def create(self, tool_name, arguments, requester, ttl, risk="mutation"):
        self.created.append((tool_name, arguments, risk))
        return NS(id="op_1")

    async def finish_notification_failure(self, *a):
        pass


class Notifier:
    def __init__(self):
        self.n = 0

    async def notify(self, op):
        self.n += 1


class Amo:
    async def get_leads(self, **kw):
        return [{"id": 1, "kw": kw}]

    async def update_lead(self, **kw):
        raise AssertionError("never exposed")


def make(batch=False, amo=True):
    up, st, nt = Upstream(), Store(), Notifier()
    svc = GatewayService(up, st, nt)
    return up, st, nt, CodeModeHost(svc, Amo() if amo else None, allow_mutation_batch=batch,
                        sandbox="node", dev_unsafe_node=True)


def run(host, script):
    return asyncio.run(host.run(script, timeout=20))


def test_describe_lists_reads_only():
    _, _, _, h = make()
    d = asyncio.run(h.describe())
    assert "get_history" in d and "get_leads" in d
    assert "send_message" not in d and "update_lead" not in d


def test_telegram_and_amo_in_one_script():
    up, _, _, h = make()
    out = run(h, "const l = await amo.get_leads({limit: 9999}); "
                 "const m = await telegram.get_history({chat_id: l[0].id}); return {l, m};")
    assert out["result"]["l"][0]["kw"]["limit"] == 250
    assert up.calls == [("get_history", {"chat_id": 1})]


def test_amo_mutation_and_raw_params_refused():
    _, _, _, h = make()
    with pytest.raises(RuntimeError, match="mutation not allowed"):
        run(h, "return await amo.update_lead({lead_id: 1});")
    out = run(h, "try { await amo.get_leads({'filter[x]': 1}); return 'open'; } catch (e) { return 'refused'; }")
    assert out["result"] == "refused"


def test_batch_one_approval_for_many_mutations():
    up, st, nt, h = make(batch=True)
    out = run(h, "for (let i=0;i<5;i++) await telegram.send_message({text:'hi'+i}); return 'queued';")
    assert out["approval"] == {"status": "pending_approval", "operation_id": "op_1", "actions": 5}
    assert len(st.created) == 1 and nt.n == 1 and up.calls == []
    assert st.created[0][0] == BATCH_TOOL and len(st.created[0][1]["actions"]) == 5


def test_batch_refuses_destructive_and_overflow():
    _, st, _, h = make(batch=True)
    out = run(h, "try { await telegram.delete_message({}); return 'x'; } catch (e) { return e.message; }")
    assert "destructive" in out["result"] and st.created == []
    out = run(h, "let n=0; try { for (let i=0;i<25;i++){ await telegram.send_message({text:'a'}); n++; } } catch(e){} return n;")
    assert out["result"] == 20


def test_batch_upstream_executes_after_approval_and_revalidates():
    up = Upstream()
    bu = BatchUpstream(up)
    acts = [{"tool": "send_message", "arguments": {"text": "a"}}] * 2
    r = asyncio.run(bu.call_tool(BATCH_TOOL, {"actions": acts}))
    assert r["executed"] == 2 and len(up.calls) == 2
    with pytest.raises(ValueError):
        asyncio.run(bu.call_tool(BATCH_TOOL, {"actions": [{"tool": "delete_message", "arguments": {}}]}))
