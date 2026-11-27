"""Tests for conversation-driven automation proposals in OishaSelfDiagnosis."""
from __future__ import annotations

import pytest

from src.services.core.diagnosis import CATEGORY_FEATURE, OishaSelfDiagnosis


class _FakeDB:
    def __init__(
        self,
        missing_phone_count: int,
        messages: list[str],
        tasks: list[str] | None = None,
    ):
        self._missing = missing_phone_count
        self._messages = messages
        self._tasks = tasks or []

    async def execute(self, sql: str, params=None):
        if "tg_amo_chat_links" in sql:
            return [(self._missing,)]
        if "FROM messages" in sql:
            return [(m,) for m in self._messages]
        if "FROM tasks" in sql:
            return [(t,) for t in self._tasks]
        return []


@pytest.mark.asyncio
async def test_diagnose_conversation_insights_detects_missing_phones_and_resumes():
    db = _FakeDB(
        missing_phone_count=4,
        messages=[
            "Rezyumemga havola https://hh.uz/resume/3e5aa645ff115bbc590039ed1f346856623370",
            "Mana mening rezyumem https://hh.uz/resume/abc123def456",
            "Email: client@example.com",
            "Mening pochtam sales@company.uz",
        ],
    )
    diag = OishaSelfDiagnosis(db=db)
    proposals = await diag.diagnose_conversation_insights()
    ids = {p.id for p in proposals}

    assert "conv_missing_phone_links" in ids
    assert "conv_pattern_resume_link" in ids
    assert "conv_pattern_email_address" in ids
    assert all(p.category == CATEGORY_FEATURE for p in proposals)


@pytest.mark.asyncio
async def test_diagnose_conversation_insights_skips_below_threshold():
    db = _FakeDB(missing_phone_count=1, messages=["Salom, narxlar qancha?"])
    diag = OishaSelfDiagnosis(db=db)
    proposals = await diag.diagnose_conversation_insights()
    assert proposals == []


@pytest.mark.asyncio
async def test_diagnose_conversation_insights_detects_repetitive_tasks_and_messages():
    db = _FakeDB(
        missing_phone_count=0,
        messages=[
            "Kompaniya va ish haqida toliq malumot bera olasizmi?",
            "Kompaniya va ish haqida toliq malumot bera olasizmi?",
            "Kompaniya va ish haqida toliq malumot bera olasizmi?",
        ],
        tasks=[
            "Mijoz telefon raqamini amoCRM ga kiritish +998901112233",
            "Mijoz telefon raqamini amoCRM ga kiritish +998904445566",
            "Mijoz telefon raqamini amoCRM ga kiritish +998907778899",
        ],
    )
    diag = OishaSelfDiagnosis(db=db)
    proposals = await diag.diagnose_conversation_insights()
    ids = {p.id for p in proposals}

    assert any(pid.startswith("rep_task_") for pid in ids)
    assert any(pid.startswith("rep_msg_") for pid in ids)
