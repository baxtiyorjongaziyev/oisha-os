from datetime import timedelta

import pytest

from src.database import Database
from src.services.core.agent_loop import MinimalAgentLoop
from src.services.erp.action_queue import ActionQueue
from src.services.erp.models import ERPAction, ERPWorkflow
from src.services.erp.repository import ERPRepository
from src.time_utils import get_local_now


@pytest.fixture
async def queue(tmp_path):
    db = Database(str(tmp_path / "queue.db"))
    await db.init_instance()
    repo = ERPRepository(db)
    await repo.initialize()
    await repo.create_workflow(
        ERPWorkflow(
            workflow_id="wf-queue",
            workflow_type="sales",
            entity_type="amocrm_lead",
            entity_id="1001",
            correlation_id="corr-queue",
        )
    )
    action_queue = ActionQueue(repo)
    yield action_queue
    await db.close()


def make_action(action_id: str, idempotency_key: str) -> ERPAction:
    return ERPAction(
        action_id=action_id,
        workflow_id="wf-queue",
        action_type="telegram.send_message",
        target="telegram",
        payload={"chat_id": 777, "text": "Assalomu alaykum"},
        risk_level="low",
        idempotency_key=idempotency_key,
        expected_result={"chat_id": 777, "message_exists": True},
    )


@pytest.mark.asyncio
async def test_duplicate_telegram_action_is_not_enqueued_twice(queue):
    assert await queue.enqueue(make_action("act-1", "telegram:777:message:55")) is True
    assert await queue.enqueue(make_action("act-2", "telegram:777:message:55")) is False

    assert await queue.repo.count_rows("erp_actions") == 1


@pytest.mark.asyncio
async def test_expired_lease_is_recovered_after_worker_crash(queue):
    await queue.enqueue(make_action("act-crash", "telegram:777:crash"))
    first = await queue.claim_next("worker-a", lease_seconds=60)

    assert first is not None
    assert first.action["action_id"] == "act-crash"
    assert first.attempt_number == 1

    conn = await queue.repo.db.get_connection()
    await conn.execute(
        "UPDATE erp_actions SET lease_expires_at = ? WHERE action_id = ?",
        ((get_local_now() - timedelta(seconds=1)).isoformat(), "act-crash"),
    )
    await conn.commit()

    second = await queue.claim_next("worker-b", lease_seconds=60)

    assert second is not None
    assert second.action["action_id"] == "act-crash"
    assert second.attempt_number == 2


@pytest.mark.asyncio
async def test_dead_letter_persists_action_and_reason(queue):
    await queue.enqueue(make_action("act-dead", "telegram:777:dead"))
    item = await queue.claim_next("worker-a")

    await queue.dead_letter(item, "permanent_400")

    action = await queue.repo.get_action("act-dead")
    assert action["status"] == "failed"
    assert await queue.repo.count_rows("erp_dead_letters") == 1


@pytest.mark.asyncio
async def test_minimal_agent_loop_enqueues_into_durable_queue(queue):
    loop = MinimalAgentLoop(queue.repo.db, action_queue=queue)

    assert await loop.enqueue_action(
        make_action("act-loop", "telegram:777:loop")
    ) is True

    stored = await queue.repo.get_action("act-loop")
    assert stored["status"] == "pending"
