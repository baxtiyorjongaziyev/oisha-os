import pytest

from src.database import Database
from src.services.erp.action_queue import ActionQueue
from src.services.erp.action_runner import ActionRunner
from src.services.erp.models import ERPAction, ERPWorkflow, VerificationResult
from src.services.erp.repository import ERPRepository
from src.services.erp.retry_policy import RetryPolicy


class PermanentAPIError(RuntimeError):
    status_code = 400


@pytest.fixture
async def runtime(tmp_path):
    db = Database(str(tmp_path / "runner.db"))
    await db.init_instance()
    repo = ERPRepository(db)
    await repo.initialize()
    await repo.create_workflow(
        ERPWorkflow(
            workflow_id="wf-runner",
            workflow_type="sales",
            entity_type="amocrm_lead",
            entity_id="2001",
            correlation_id="corr-runner",
        )
    )
    queue = ActionQueue(repo)
    yield repo, queue
    await db.close()


def action(action_id: str, action_type: str = "amocrm.create_task") -> ERPAction:
    return ERPAction(
        action_id=action_id,
        workflow_id="wf-runner",
        action_type=action_type,
        target="amocrm",
        payload={"lead_id": 2001},
        risk_level="low",
        idempotency_key=f"{action_type}:{action_id}",
        expected_result={"lead_id": 2001, "task_exists": True},
    )


@pytest.mark.asyncio
async def test_timeout_uses_exponential_retry(runtime):
    repo, queue = runtime
    await queue.enqueue(action("act-timeout"))

    async def timeout_executor(_action):
        raise TimeoutError("AmoCRM timeout")

    runner = ActionRunner(
        queue,
        executors={"amocrm.create_task": timeout_executor},
        verifiers={},
        retry_policy=RetryPolicy(delays_seconds=(30, 120, 600)),
    )

    result = await runner.run_once("worker-a")
    stored = await repo.get_action("act-timeout")

    assert result.status == "retrying"
    assert result.retry_after_seconds == 30
    assert stored["status"] == "retrying"
    assert stored["attempt_count"] == 1


@pytest.mark.asyncio
async def test_permanent_4xx_moves_action_to_dead_letter(runtime):
    repo, queue = runtime
    await queue.enqueue(action("act-400"))

    async def permanent_executor(_action):
        raise PermanentAPIError("invalid request")

    runner = ActionRunner(
        queue,
        executors={"amocrm.create_task": permanent_executor},
        verifiers={},
    )

    result = await runner.run_once("worker-a")
    stored = await repo.get_action("act-400")

    assert result.status == "dead_letter"
    assert stored["status"] == "failed"
    assert await repo.count_rows("erp_dead_letters") == 1


@pytest.mark.asyncio
async def test_action_cannot_complete_without_live_verifier(runtime):
    repo, queue = runtime
    await queue.enqueue(action("act-no-verifier"))

    async def executor(_action):
        return {"success": True, "task_id": 88}

    runner = ActionRunner(
        queue,
        executors={"amocrm.create_task": executor},
        verifiers={},
    )

    result = await runner.run_once("worker-a")
    stored = await repo.get_action("act-no-verifier")

    assert result.status == "retrying"
    assert result.reason == "verifier_missing"
    assert stored["status"] == "retrying"


@pytest.mark.asyncio
async def test_verified_action_is_completed(runtime):
    repo, queue = runtime
    await queue.enqueue(action("act-verified"))

    async def executor(_action):
        return {"success": True, "task_id": 88}

    async def verifier(stored_action, _execution):
        return VerificationResult(
            success=True,
            source="amocrm",
            expected=stored_action["expected_result"],
            actual={"lead_id": 2001, "task_exists": True, "task_id": 88},
            reason="live_readback_confirmed",
        )

    runner = ActionRunner(
        queue,
        executors={"amocrm.create_task": executor},
        verifiers={"amocrm.create_task": verifier},
    )

    result = await runner.run_once("worker-a")
    stored = await repo.get_action("act-verified")

    assert result.status == "completed"
    assert stored["status"] == "completed"
    assert await repo.count_rows("erp_verifications") == 1
