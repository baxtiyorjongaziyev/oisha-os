import aiosqlite
import pytest

from src.agents.feedback_memory import FeedbackMemory
from src.services.core.retry_queue import RetryQueue


class GetConnectionDB:
    def __init__(self, path):
        self.path = path
        self.conn = None

    async def get_connection(self):
        if self.conn is None:
            self.conn = await aiosqlite.connect(self.path)
        return self.conn

    async def close(self):
        if self.conn is not None:
            await self.conn.close()


@pytest.mark.asyncio
async def test_feedback_memory_supports_get_connection(tmp_path):
    db = GetConnectionDB(tmp_path / "memory.db")
    try:
        memory = FeedbackMemory(db)
        await memory.append(123, "user", "Narx qancha?", {"intent": "pricing"})

        history = await memory.get_as_negotiation_history(123)

        assert history == [{"role": "user", "content": "Narx qancha?"}]
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_retry_queue_drain_lock_prevents_duplicate_execution(tmp_path):
    db = GetConnectionDB(tmp_path / "retry.db")
    calls = []

    async def executor(action_name, payload):
        calls.append((action_name, payload))
        return {"success": True}

    try:
        queue = RetryQueue(db, executor_fn=executor)
        await queue.enqueue("send_message", {"lead_id": 1})

        first = await queue.drain_once()
        second = await queue.drain_once()

        assert first == 1
        assert second == 0
        assert calls == [("send_message", {"lead_id": 1})]
        assert (await queue.stats()).get("succeeded") == 1
    finally:
        await db.close()
