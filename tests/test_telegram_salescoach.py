from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.services.core.telegram_salescoach import (
    CrmMatch,
    TelegramConversationMessage,
    TelegramSalesCoach,
    conversation_fingerprint,
)


BASE_TIME = datetime(2026, 7, 31, 10, 0, tzinfo=timezone.utc)


def make_messages(count: int = 4, *, last_text: str | None = None):
    messages = [
        TelegramConversationMessage(
            id=1000 + index,
            role="customer" if index % 2 == 0 else "manager",
            text=f"Xabar {index}",
            sent_at=BASE_TIME + timedelta(minutes=index),
        )
        for index in range(count)
    ]
    if last_text is not None:
        last = messages[-1]
        messages[-1] = TelegramConversationMessage(
            id=last.id,
            role=last.role,
            text=last_text,
            sent_at=last.sent_at,
        )
    return messages


def valid_analysis(*, confidence: float = 0.91):
    return {
        "overallScore": 74,
        "confidence": confidence,
        "clientIntent": "warm",
        "dealRisk": "medium",
        "recommendedTasks": [
            {
                "type": "follow_up",
                "reason": "Keyingi qadam kerak",
                "evidenceMessageIds": [1001],
            }
        ],
        "evidenceMessageIds": [1000, 1001],
    }


@pytest.fixture
def dependencies():
    store = SimpleNamespace(
        fingerprint_exists=AsyncMock(return_value=False),
        save_analysis=AsyncMock(return_value=12),
    )
    sync = SimpleNamespace(analyze_conversation=AsyncMock(return_value=valid_analysis()))
    matcher = SimpleNamespace(
        match=AsyncMock(
            return_value=CrmMatch(
                lead_id=42,
                contact_id=84,
                responsible_user_id=777,
                confidence=0.93,
                crm_status="Birinchi kontakt",
            )
        )
    )
    writer = SimpleNamespace(apply_analysis=AsyncMock(return_value=[]))
    loader = AsyncMock(return_value=make_messages())
    message_loader = SimpleNamespace(load=loader)
    personal_checker = AsyncMock(return_value=False)
    approval_notifier = SimpleNamespace(send=AsyncMock())
    coach = TelegramSalesCoach(
        store=store,
        salescoach_sync=sync,
        crm_matcher=matcher,
        task_writer=writer,
        message_loader=message_loader,
        personal_sender_checker=personal_checker,
        internal_user_ids={900},
        approval_notifier=approval_notifier,
        enabled=True,
        mode="shadow",
        idle_seconds=600,
    )
    return coach, store, sync, matcher, writer, loader, personal_checker, approval_notifier


def test_fingerprint_is_stable_and_text_sensitive():
    first = conversation_fingerprint(42, make_messages())
    second = conversation_fingerprint(42, make_messages())
    changed = conversation_fingerprint(42, make_messages(last_text="Yangi xabar"))

    assert first == second
    assert first != changed
    assert "Xabar" not in first


@pytest.mark.asyncio
async def test_personal_folder_sender_is_never_scheduled(dependencies):
    coach, _, sync, _, _, _, personal_checker, _ = dependencies
    personal_checker.return_value = True
    event = SimpleNamespace(is_private=True, out=False, chat_id=555)
    sender = SimpleNamespace(id=555, bot=False)
    client = SimpleNamespace(get_me=AsyncMock(return_value=SimpleNamespace(id=1)))

    await coach.handle_private_event(event, sender=sender, client=client)

    assert coach.pending_user_ids == set()
    sync.analyze_conversation.assert_not_awaited()


@pytest.mark.asyncio
async def test_bot_and_internal_team_are_never_scheduled(dependencies):
    coach, _, sync, _, _, _, _, _ = dependencies
    event = SimpleNamespace(is_private=True, out=False, chat_id=555)
    client = SimpleNamespace(get_me=AsyncMock(return_value=SimpleNamespace(id=1)))

    await coach.handle_private_event(
        event,
        sender=SimpleNamespace(id=555, bot=True),
        client=client,
    )
    await coach.handle_private_event(
        SimpleNamespace(is_private=True, out=False, chat_id=900),
        sender=SimpleNamespace(id=900, bot=False),
        client=client,
    )

    assert coach.pending_user_ids == set()
    sync.analyze_conversation.assert_not_awaited()


@pytest.mark.asyncio
async def test_unmatched_crm_dialog_is_not_sent_to_salescoach(dependencies):
    coach, _, sync, matcher, _, _, _, _ = dependencies
    matcher.match.return_value = None

    result = await coach.analyze_dialog_now(555)

    assert result is None
    sync.analyze_conversation.assert_not_awaited()


@pytest.mark.asyncio
async def test_batch_is_limited_to_last_50_messages(dependencies):
    coach, _, sync, _, _, loader, _, _ = dependencies
    loader.return_value = make_messages(80)

    await coach.analyze_dialog_now(555)

    payload = sync.analyze_conversation.await_args.kwargs
    assert len(payload["messages"]) == 50
    assert payload["messages"][0]["id"] == 1030


@pytest.mark.asyncio
async def test_shadow_mode_never_calls_task_writer(dependencies):
    coach, store, _, _, writer, _, _, _ = dependencies
    coach.mode = "shadow"

    result = await coach.analyze_dialog_now(555)

    assert result["analysis_id"] == 12
    store.save_analysis.assert_awaited_once()
    writer.apply_analysis.assert_not_awaited()


@pytest.mark.asyncio
async def test_low_confidence_analysis_never_auto_writes(dependencies):
    coach, _, sync, _, writer, _, _, _ = dependencies
    coach.mode = "auto"
    sync.analyze_conversation.return_value = valid_analysis(confidence=0.60)

    await coach.analyze_dialog_now(555)

    writer.apply_analysis.assert_not_awaited()


@pytest.mark.asyncio
async def test_approval_mode_notifies_without_writing(dependencies):
    coach, _, _, _, writer, _, _, notifier = dependencies
    coach.mode = "approval"

    await coach.analyze_dialog_now(555)

    notifier.send.assert_awaited_once()
    writer.apply_analysis.assert_not_awaited()
