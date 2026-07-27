import sys
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from scripts.run_telegram_mcp_agent import _require_loopback_url
from services.core.telegram_mcp.gateway import (
    DEFAULT_AGENT_IDS,
    GatewayService,
    parse_allowed_agent_ids,
    require_allowed_agent_id,
)
from services.core.telegram_mcp.store import ApprovalStore


class AgentIdentityTests(unittest.TestCase):
    def test_default_agents_are_explicit(self):
        self.assertEqual(
            DEFAULT_AGENT_IDS,
            frozenset({"antigravity", "claude", "codex"}),
        )

    def test_future_agent_requires_allowlist_entry(self):
        allowed = parse_allowed_agent_ids("codex,claude,antigravity,gemini")
        self.assertEqual(require_allowed_agent_id("Gemini", allowed), "gemini")
        with self.assertRaises(PermissionError):
            require_allowed_agent_id("unknown", allowed)

    def test_invalid_agent_ids_fail_closed(self):
        with self.assertRaises(ValueError):
            parse_allowed_agent_ids("codex,bad agent")
        with self.assertRaises(ValueError):
            require_allowed_agent_id("../codex", DEFAULT_AGENT_IDS)

    def test_upstream_cannot_point_to_public_host(self):
        self.assertEqual(
            _require_loopback_url("http://127.0.0.1:8765/mcp"),
            "http://127.0.0.1:8765/mcp",
        )
        with self.assertRaises(RuntimeError):
            _require_loopback_url("https://example.com/mcp")


@dataclass
class Tool:
    name: str = "send_message"
    annotations: object = None


class FakeUpstream:
    async def list_tools(self):
        return [Tool()]

    async def call_tool(self, name, arguments):
        return {"ok": True}


class FakeNotifier:
    async def notify(self, operation):
        return None


class RequesterBindingTests(unittest.IsolatedAsyncioTestCase):
    async def test_gateway_persists_fixed_agent_identity(self):
        with tempfile.TemporaryDirectory() as tempdir:
            store = ApprovalStore(Path(tempdir) / "approvals.db")
            service = GatewayService(FakeUpstream(), store, FakeNotifier())
            await service.start()
            pending = await service.call_tool(
                "send_message",
                {"chat_id": "7", "message": "Salom"},
                requester="claude",
            )
            operation = await store.get(pending["operation_id"])
        self.assertIsNotNone(operation)
        self.assertEqual(operation.requester, "claude")

if __name__ == "__main__":
    unittest.main()
