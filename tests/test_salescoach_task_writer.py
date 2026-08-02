from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock
from zoneinfo import ZoneInfo

import pytest

from src.services.core.crm.salescoach_task_writer import SalesCoachTaskWriter


TZ = ZoneInfo("Asia/Tashkent")
NOW = datetime(2026, 7, 31, 12, 0, tzinfo=TZ)
EXPECTED_DEADLINE = int((NOW + timedelta(minutes=30)).timestamp())


def analysis(*, task_type: str = "reply_customer") -> dict:
    return {
        "overallScore": 64,
        "clientIntent": "warm",
        "dealRisk": "medium",
        "objections": ["price"],
        "nextBestAction": "Mijozga javob berish",
        "confidence": 0.91,
        "evidenceMessageIds": [1001, 1002],
        "recommendedTasks": [
            {
                "type": task_type,
                "reason": "Mijoz savoli javobsiz qolgan",
                "evidenceMessageIds": [1001],
            }
        ],
    }


@pytest.fixture
def dependencies():
    amo = SimpleNamespace(
        get_lead=AsyncMock(return_value={"id": 42, "responsible_user_id": 777}),
        list_open_tasks=AsyncMock(return_value=[]),
        create_note=AsyncMock(return_value={"id": 8001}),
        list_notes=AsyncMock(
            return_value=[
                {
                    "id": 8001,
                    "note_type": "common",
                    "params": {"text": "[OISHA_SALESCOACH] Fingerprint: fp-001"},
                }
            ]
        ),
        create_task=AsyncMock(return_value={"id": 9001}),
        get_task=AsyncMock(
            return_value={
                "id": 9001,
                "entity_id": 42,
                "responsible_user_id": 777,
                "text": "Mijozga javob bering",
                "complete_till": EXPECTED_DEADLINE,
            }
        ),
    )
    store = SimpleNamespace(
        task_key_exists=AsyncMock(return_value=False),
        record_task_write=AsyncMock(),
    )
    notifier = SimpleNamespace(notify_write_failure=AsyncMock())
    writer = SalesCoachTaskWriter(
        amocrm=amo,
        store=store,
        admin_notifier=notifier,
        now_provider=lambda: NOW,
    )
    return writer, amo, store, notifier


@pytest.mark.asyncio
async def test_task_uses_current_lead_responsible_user(dependencies):
    writer, amo, _, _ = dependencies

    result = await writer.apply_analysis(
        analysis_id=12,
        lead_id=42,
        responsible_user_id=13021974,
        conversation_fingerprint="fp-001",
        analysis=analysis(),
        mode="auto",
    )

    payload = amo.create_task.await_args.args[0]
    assert payload["responsible_user_id"] == 777
    assert payload["entity_id"] == 42
    assert payload["complete_till"] == EXPECTED_DEADLINE
    assert result[0].verified is True


@pytest.mark.asyncio
async def test_existing_open_same_type_task_blocks_duplicate(dependencies):
    writer, amo, _, _ = dependencies
    amo.list_open_tasks.return_value = [
        {"id": 1, "text": "Mijozga javob bering", "is_completed": False}
    ]

    result = await writer.apply_analysis(
        analysis_id=12,
        lead_id=42,
        responsible_user_id=777,
        conversation_fingerprint="fp-001",
        analysis=analysis(),
        mode="auto",
    )

    amo.create_task.assert_not_awaited()
    assert result[0].skipped is True
    assert result[0].failure_code == "open_task_exists"


@pytest.mark.asyncio
async def test_local_idempotency_key_blocks_retry_duplicate(dependencies):
    writer, amo, store, _ = dependencies
    store.task_key_exists.return_value = True

    result = await writer.apply_analysis(
        analysis_id=12,
        lead_id=42,
        responsible_user_id=777,
        conversation_fingerprint="fp-001",
        analysis=analysis(),
        mode="auto",
    )

    amo.create_task.assert_not_awaited()
    assert result[0].skipped is True
    assert result[0].failure_code == "idempotency_key_exists"


@pytest.mark.asyncio
async def test_mismatched_responsible_user_is_not_success(dependencies):
    writer, amo, store, notifier = dependencies
    amo.get_task.return_value = {
        "id": 9001,
        "entity_id": 42,
        "responsible_user_id": 13021974,
        "text": "Mijozga javob bering",
        "complete_till": EXPECTED_DEADLINE,
    }

    result = await writer.apply_analysis(
        analysis_id=12,
        lead_id=42,
        responsible_user_id=777,
        conversation_fingerprint="fp-001",
        analysis=analysis(),
        mode="auto",
    )

    assert result[0].verified is False
    assert result[0].failure_code == "responsible_user_mismatch"
    notifier.notify_write_failure.assert_awaited_once()
    audit = store.record_task_write.await_args.args[0]
    assert audit.verification_status == "failed"


@pytest.mark.asyncio
async def test_unknown_recommendation_is_never_written(dependencies):
    writer, amo, _, _ = dependencies

    result = await writer.apply_analysis(
        analysis_id=12,
        lead_id=42,
        responsible_user_id=777,
        conversation_fingerprint="fp-001",
        analysis=analysis(task_type="delete_lead"),
        mode="auto",
    )

    amo.create_task.assert_not_awaited()
    assert result == []


@pytest.mark.asyncio
async def test_approval_requires_actor_before_any_crm_write(dependencies):
    writer, amo, _, _ = dependencies

    result = await writer.apply_analysis(
        analysis_id=12,
        lead_id=42,
        responsible_user_id=777,
        conversation_fingerprint="fp-001",
        analysis=analysis(),
        mode="approval",
    )

    amo.get_lead.assert_not_awaited()
    amo.create_note.assert_not_awaited()
    amo.create_task.assert_not_awaited()
    assert result[0].failure_code == "approval_actor_required"


@pytest.mark.asyncio
async def test_quiet_hours_defer_all_crm_mutations(dependencies):
    writer, amo, _, _ = dependencies
    writer.now_provider = lambda: NOW.replace(hour=23)

    result = await writer.apply_analysis(
        analysis_id=12,
        lead_id=42,
        responsible_user_id=777,
        conversation_fingerprint="fp-001",
        analysis=analysis(),
        mode="auto",
    )

    amo.get_lead.assert_not_awaited()
    amo.create_note.assert_not_awaited()
    amo.create_task.assert_not_awaited()
    assert result[0].failure_code == "quiet_hours_deferred"
