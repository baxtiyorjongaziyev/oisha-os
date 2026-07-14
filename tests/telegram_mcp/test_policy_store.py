import asyncio
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2] / "src"))

from services.core.telegram_mcp.policy import classify_tool
from services.core.telegram_mcp.store import ApprovalStore, payload_digest


class PolicyTests(unittest.TestCase):
    def test_read_needs_annotation_and_allowlist(self):
        self.assertTrue(
            classify_tool("list_chats", {"readOnlyHint": True}).automatic
        )
        self.assertFalse(
            classify_tool("unknown_tool", {"readOnlyHint": True}).automatic
        )
        self.assertFalse(classify_tool("list_chats", None).automatic)

    def test_mutations_require_approval(self):
        for name in ("send_message", "edit_message", "delete_messages", "ban_user"):
            with self.subTest(name=name):
                self.assertFalse(classify_tool(name, {"readOnlyHint": False}).automatic)
        self.assertEqual(classify_tool("delete_messages", {}).risk, "destructive")


class StoreTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.store = ApprovalStore(Path(self.tempdir.name) / "approvals.db")
        await self.store.initialize()

    async def asyncTearDown(self):
        self.tempdir.cleanup()

    async def test_claim_is_owner_only_and_single_use(self):
        op = await self.store.create(
            "send_message",
            {"chat_id": "7", "message": "Salom"},
            "chatgpt",
            900,
        )
        self.assertIsNone(await self.store.claim(op.id, 999, 123))
        first, second = await asyncio.gather(
            self.store.claim(op.id, 123, 123),
            self.store.claim(op.id, 123, 123),
        )
        self.assertEqual(sum(item is not None for item in (first, second)), 1)

    async def test_cancel_prevents_claim(self):
        op = await self.store.create("delete_messages", {"ids": [1]}, "chatgpt", 900)
        self.assertTrue(await self.store.cancel(op.id, 123, 123))
        self.assertIsNone(await self.store.claim(op.id, 123, 123))

    async def test_payload_digest_is_order_independent(self):
        self.assertEqual(
            payload_digest("tool", {"b": 2, "a": 1}),
            payload_digest("tool", {"a": 1, "b": 2}),
        )


if __name__ == "__main__":
    unittest.main()
