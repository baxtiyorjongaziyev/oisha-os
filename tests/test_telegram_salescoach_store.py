from __future__ import annotations

import sqlite3

import pytest

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


@pytest.fixture
async def store():
    db = FakeDatabase()
    instance = TelegramSalesCoachStore(db)
    await instance.initialize()
    yield instance
    db.connection.close()


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
    first = ConversationAnalysisRecord(
        conversation_hash="conv-hash",
        telegram_user_hash="user-hash",
        lead_id=42,
        manager_id="77",
        fingerprint="fp-001",
        overall_score=64,
        confidence=0.9,
        source_message_ids=[1001, 1002],
        rollout_mode="shadow",
        analysis={"clientIntent": "warm"},
    )
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
