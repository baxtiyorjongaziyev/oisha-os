from __future__ import annotations

import sqlite3

import pytest
import pytest_asyncio

from src.services.core.telegram_salescoach_store import (
    ConversationAnalysisRecord,
    TaskWriteAudit,
    TelegramSalesCoachStore,
)


class FakeDatabase:
    def __init__(self):
        self.connection = sqlite3.connect(":memory:")
        self.connection.row_factory = sqlite3.Row

    async def get_connection(self):
        return self.connection


@pytest_asyncio.fixture
async def store():
    db = FakeDatabase()
    instance = TelegramSalesCoachStore(db)
    await instance.initialize()
    yield instance
    db.connection.close()


def pending_record() -> ConversationAnalysisRecord:
    return ConversationAnalysisRecord(
        conversation_hash="conv-hash",
        telegram_user_hash="user-hash",
        lead_id=42,
        manager_id="77",
        fingerprint="fp-001",
        overall_score=64,
        confidence=0.9,
        source_message_ids=[1001, 1002],
        rollout_mode="approval",
        analysis={
            "clientIntent": "warm",
            "recommendedTasks": [
                {
                    "type": "follow_up",
                    "reason": "Keyingi qadam kerak",
                    "evidenceMessageIds": [1001],
                }
            ],
        },
        status="pending",
    )


@pytest.mark.asyncio
async def test_initialize_creates_privacy_safe_tables():
    db = FakeDatabase()
    store = TelegramSalesCoachStore(db)

    await store.initialize()

    tables = {
        row[0]
        for row in db.connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    }
    assert "conversation_analyses" in tables
    assert "salescoach_task_audit" in tables
    assert "salescoach_analysis_retry_queue" in tables

    columns = {
        row[1]
        for row in db.connection.execute(
            "PRAGMA table_info(conversation_analyses)"
        ).fetchall()
    }
    assert "transcript" not in columns
    assert "message_text" not in columns
    assert "analysis_json" in columns
    db.connection.close()


@pytest.mark.asyncio
async def test_save_analysis_is_idempotent_by_fingerprint(store):
    first = pending_record()
    second = ConversationAnalysisRecord(
        conversation_hash="conv-hash",
        telegram_user_hash="user-hash",
        lead_id=42,
        manager_id="77",
        fingerprint="fp-001",
        overall_score=72,
        confidence=0.95,
        source_message_ids=[1001, 1002, 1003],
        rollout_mode="approval",
        analysis={"clientIntent": "hot"},
    )

    first_id = await store.save_analysis(first)
    second_id = await store.save_analysis(second)
    rows = await store.list_recent()

    assert first_id == second_id
    assert len(rows) == 1
    assert rows[0]["overall_score"] == 72
    assert rows[0]["analysis"]["clientIntent"] == "hot"
    assert await store.fingerprint_exists("fp-001") is True


@pytest.mark.asyncio
async def test_get_analysis_and_update_status(store):
    analysis_id = await store.save_analysis(pending_record())

    record = await store.get_analysis(analysis_id)
    updated = await store.update_analysis_status(analysis_id, "approved")
    refreshed = await store.get_analysis(analysis_id)

    assert record is not None
    assert record["id"] == analysis_id
    assert record["status"] == "pending"
    assert record["analysis"]["clientIntent"] == "warm"
    assert updated is True
    assert refreshed is not None
    assert refreshed["status"] == "approved"


@pytest.mark.asyncio
async def test_update_status_rejects_unknown_value(store):
    analysis_id = await store.save_analysis(pending_record())

    with pytest.raises(ValueError, match="invalid_conversation_analysis_status"):
        await store.update_analysis_status(analysis_id, "deleted")


@pytest.mark.asyncio
async def test_task_audit_prevents_duplicate_idempotency_keys(store):
    audit = TaskWriteAudit(
        idempotency_key="task-key-1",
        lead_id=42,
        task_type="follow_up",
        conversation_fingerprint="fp-001",
        amocrm_task_id="9001",
        verification_status="verified",
    )

    await store.record_task_write(audit)
    await store.record_task_write(audit)

    assert await store.task_key_exists("task-key-1") is True
    conn = await store.db.get_connection()
    count = conn.execute(
        "SELECT COUNT(*) FROM salescoach_task_audit WHERE idempotency_key = ?",
        ("task-key-1",),
    ).fetchone()[0]
    assert count == 1


@pytest.mark.asyncio
async def test_privacy_filter_is_recursive(store):
    record = pending_record()
    nested = ConversationAnalysisRecord(
        **{
            **record.__dict__,
            "analysis": {
                "transcript": "secret",
                "recommendedTasks": [
                    {"type": "follow_up", "messages": ["secret"], "reason": "ok"}
                ],
            },
        }
    )
    analysis_id = await store.save_analysis(nested)
    saved = await store.get_analysis(analysis_id)

    assert saved is not None
    assert "transcript" not in saved["analysis"]
    assert "messages" not in saved["analysis"]["recommendedTasks"][0]
    assert saved["analysis"]["recommendedTasks"][0]["reason"] == "ok"


@pytest.mark.asyncio
async def test_task_claim_is_atomic(store):
    audit = TaskWriteAudit(
        idempotency_key="atomic-key",
        lead_id=42,
        task_type="follow_up",
        conversation_fingerprint="fp-001",
    )

    first = await store.claim_task_write(audit)
    second = await store.claim_task_write(audit)

    assert first is True
    assert second is False


@pytest.mark.asyncio
async def test_analysis_failure_queue_keeps_only_hashes(store):
    await store.record_analysis_failure(
        fingerprint="fp-retry",
        lead_id=42,
        telegram_user_hash="user-hash",
        failure_code="analysis_unavailable",
    )
    conn = await store.db.get_connection()
    row = conn.execute(
        "SELECT fingerprint, telegram_user_hash, attempts FROM salescoach_analysis_retry_queue"
    ).fetchone()

    assert tuple(row) == ("fp-retry", "user-hash", 5)
    await store.clear_analysis_failure("fp-retry")
    assert conn.execute(
        "SELECT COUNT(*) FROM salescoach_analysis_retry_queue"
    ).fetchone()[0] == 0
