"""Regression coverage for PR1190 review findings; all data is synthetic."""
import asyncio
import multiprocessing
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_auto_merge_reconciles_live_state_and_requires_pat():
    workflow = yaml.safe_load((ROOT / ".github/workflows/auto-merge.yml").read_text())
    assert workflow["concurrency"]["cancel-in-progress"] is False
    assert "pull_request.number" in workflow["concurrency"]["group"]
    assert list(workflow["jobs"]) == ["reconcile"]
    step = workflow["jobs"]["reconcile"]["steps"][0]
    script = step["run"]
    assert "gh pr view" in script
    assert "autoMergeRequest" in script
    assert "--match-head-commit" in script
    assert 'test -n "$MERGE_TOKEN"' in script
    assert "|| true" not in script


def test_cancelled_pr_tests_are_not_eligible():
    workflow = yaml.safe_load((ROOT / ".github/workflows/test.yml").read_text())
    condition = workflow["jobs"]["pull-request-tests"]["if"]
    assert "!cancelled()" in condition
    assert "always()" not in condition
    assert "needs.changes.result != 'success'" in condition


def _lock_worker(directory, attempted, entered):
    from src.services.core.crm.tg_amo_bridge.merge_locks import lead_locks

    async def run():
        attempted.set()
        async with lead_locks(11, 22, directory=Path(directory)):
            entered.set()
    asyncio.run(run())


def test_lock_serializes_independent_process_and_releases(tmp_path):
    from src.services.core.crm.tg_amo_bridge.merge_locks import lead_locks

    async def run():
        ctx = multiprocessing.get_context("spawn")
        entered = ctx.Event()
        attempted = ctx.Event()
        process = ctx.Process(target=_lock_worker, args=(str(tmp_path), attempted, entered))
        async with lead_locks(22, 33, directory=tmp_path):
            process.start()
            assert await asyncio.to_thread(attempted.wait, 15)
            assert not await asyncio.to_thread(entered.wait, 0.3)
        assert await asyncio.to_thread(entered.wait, 15)
        await asyncio.to_thread(process.join, 15)
        assert process.exitcode == 0
    asyncio.run(run())


def test_cancelled_waiter_releases_partial_locks(tmp_path):
    from src.services.core.crm.tg_amo_bridge.merge_locks import lead_locks

    async def run():
        async def waiter():
            async with lead_locks(1, 2, directory=tmp_path):
                pytest.fail("contended lock acquired")
        async with lead_locks(2, directory=tmp_path):
            task = asyncio.create_task(waiter())
            await asyncio.sleep(0.1)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            async with asyncio.timeout(1):
                async with lead_locks(1, directory=tmp_path):
                    pass
        # Fixed stripes keep disk and memory bounded, even for many lead IDs.
        for lead_id in range(600):
            async with lead_locks(lead_id, directory=tmp_path):
                pass
        assert len(list(tmp_path.iterdir())) <= 256
    asyncio.run(run())


def test_executor_shared_target_keeps_first_filled_value(tmp_path, monkeypatch):
    from src.services.core.crm.tg_amo_bridge import executor

    monkeypatch.setenv("OISHA_DATA_DIR", str(tmp_path))
    target = {"price": 0}
    patches = []

    async def get_lead(lead_id):
        snapshot = dict(target) if lead_id == 22 else {"price": lead_id}
        await asyncio.sleep(0.01)
        return snapshot

    async def patch_lead(lead_id, payload):
        patches.append(payload)
        target.update(payload)
        return True

    async def apply(crm, store, decision, **kwargs):
        ok, _ = await executor._transfer_lead_fields(crm, decision.source_lead_id, 22)
        return "merged" if ok else "incomplete"

    monkeypatch.setattr(executor, "_apply_merge", apply)
    crm = SimpleNamespace(get_lead=get_lead, patch_lead=patch_lead)
    store = SimpleNamespace(try_claim_merge=AsyncMock(return_value=(True, None)))

    async def run():
        decisions = [SimpleNamespace(action="merge", source_lead_id=i,
                     target_lead_id=22, source_contact_id=i, target_contact_id=22,
                     reason="synthetic") for i in (11, 33)]
        assert await asyncio.gather(*(executor.execute_pair_decision(
            crm, store, decision, phone="synthetic") for decision in decisions)) == ["merged", "merged"]
    asyncio.run(run())
    assert len(patches) == 1
    assert target["price"] in (11, 33)


def test_lock_directory_error_fails_closed(tmp_path):
    from src.services.core.crm.tg_amo_bridge.merge_locks import lead_locks

    occupied = tmp_path / "not-a-directory"
    occupied.write_text("synthetic")

    async def run():
        with pytest.raises(FileExistsError):
            async with lead_locks(1, directory=occupied):
                pytest.fail("lock failure must not permit mutation")
    asyncio.run(run())
