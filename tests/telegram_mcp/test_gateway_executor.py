import sys
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2] / "src"))

from services.core.telegram_mcp.executor import ApprovalExecutor
from services.core.telegram_mcp.gateway import GatewayService
from services.core.telegram_mcp.store import ApprovalStore


@dataclass
class Annotations:
    readOnlyHint: bool = False
    destructiveHint: bool = False


@dataclass
class Tool:
    name: str
    annotations: Annotations


class FakeUpstream:
    def __init__(self):
        self.calls = []
        self.tools = [
            Tool("list_chats", Annotations(readOnlyHint=True)),
            Tool("send_message", Annotations(destructiveHint=True)),
            Tool("delete_messages", Annotations(destructiveHint=True)),
        ]

    async def list_tools(self):
        return self.tools

    async def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        return {"ok": True, "name": name}


class FakeNotifier:
    def __init__(self):
        self.operations = []

    async def notify(self, operation):
        self.operations.append(operation)


class GatewayExecutorTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.store = ApprovalStore(Path(self.tempdir.name) / "approvals.db")
        self.upstream = FakeUpstream()
        self.notifier = FakeNotifier()
        self.gateway = GatewayService(self.upstream, self.store, self.notifier)
        await self.gateway.start()

    async def asyncTearDown(self):
        self.tempdir.cleanup()

    async def test_read_proxies_and_send_waits(self):
        result = await self.gateway.call_tool("list_chats", {})
        self.assertTrue(result["ok"])
        pending = await self.gateway.call_tool(
            "send_message", {"chat_id": "7", "message": "Salom"}
        )
        self.assertEqual(pending["status"], "pending_approval")
        self.assertEqual(self.upstream.calls, [("list_chats", {})])
        self.assertEqual(len(self.notifier.operations), 1)

    async def test_owner_executes_once_and_non_owner_is_denied(self):
        pending = await self.gateway.call_tool(
            "send_message", {"chat_id": "7", "message": "Salom"}
        )
        executor = ApprovalExecutor(self.store, self.upstream, owner_id=123)
        denied = await executor.approve(pending["operation_id"], actor_id=999)
        self.assertEqual(denied.status, "denied")
        first = await executor.approve(pending["operation_id"], actor_id=123)
        second = await executor.approve(pending["operation_id"], actor_id=123)
        self.assertEqual(first.status, "succeeded")
        self.assertEqual(second.status, "not_pending")
        sends = [call for call in self.upstream.calls if call[0] == "send_message"]
        self.assertEqual(len(sends), 1)

    async def test_delete_can_be_cancelled(self):
        pending = await self.gateway.call_tool(
            "delete_messages", {"chat_id": "7", "ids": [1]}
        )
        executor = ApprovalExecutor(self.store, self.upstream, owner_id=123)
        cancelled = await executor.cancel(pending["operation_id"], actor_id=123)
        after = await executor.approve(pending["operation_id"], actor_id=123)
        self.assertEqual(cancelled.status, "cancelled")
        self.assertEqual(after.status, "not_pending")
        self.assertFalse(any(name == "delete_messages" for name, _ in self.upstream.calls))


if __name__ == "__main__":
    unittest.main()
