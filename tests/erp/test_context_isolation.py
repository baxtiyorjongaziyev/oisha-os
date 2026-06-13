from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
from zoneinfo import ZoneInfo

import pytest

from src.services.core.meeting_scheduler import (
    ContextMessage,
    MeetingCandidate,
    TelegramMeetingScheduler,
)
from src.services.core.telegram_task_creator import TelegramTaskCreator
from src.services.erp.context_guard import evaluate_context_access
from src.services.erp.identity_resolver import IdentityProfile


TZ = ZoneInfo("Asia/Tashkent")


def test_saidazimxoja_deal_cannot_receive_farrux_group_context():
    decision = evaluate_context_access(
        reference_identity=IdentityProfile(
            telegram_user_id=777,
            name="Saidazimxoja aka",
        ),
        context_identity=IdentityProfile(
            telegram_user_id=888,
            name="Farrux aka",
        ),
        context_kind="group",
        membership_verified=True,
        classification="client",
    )

    assert decision.allowed is False
    assert decision.reason == "identity_conflict"


def test_group_context_requires_verified_membership():
    decision = evaluate_context_access(
        reference_identity=IdentityProfile(telegram_user_id=777),
        context_identity=IdentityProfile(telegram_user_id=777),
        context_kind="group",
        membership_verified=False,
        classification="client",
    )

    assert decision.allowed is False
    assert decision.reason == "group_membership_unverified"


@pytest.mark.parametrize("classification", ["personal", "family", "team", "Hamkor/Jamoa"])
def test_personal_family_and_team_contexts_are_not_clients(classification):
    decision = evaluate_context_access(
        reference_identity=IdentityProfile(phone="+998901234567"),
        context_identity=IdentityProfile(phone="+998901234567"),
        context_kind="private",
        classification=classification,
    )

    assert decision.allowed is False
    assert decision.reason == "non_customer_context"


class _FakeDB:
    async def get_state(self, _key, default=""):
        return default


class _FakeAmo:
    def __init__(self):
        self.ensure_lead = AsyncMock(return_value=111)
        self.create_standalone_lead = AsyncMock(return_value=222)


class _NameOnlyPeer:
    id = 9001
    username = ""
    phone = ""
    first_name = "Saidazimxoja"


class _NameOnlyLeadDetector:
    async def extract_lead_info(self, _text, _profile):
        return {
            "is_lead": True,
            "intent_category": "HOT_LEAD",
            "needs": "Branding konsultatsiyasi",
            "confidence_score": 0.95,
        }


@pytest.mark.asyncio
async def test_name_only_meeting_does_not_create_amocrm_lead():
    amo = _FakeAmo()
    scheduler = TelegramMeetingScheduler(
        db=_FakeDB(),
        gcalendar=None,
        amocrm=amo,
        lead_detector=_NameOnlyLeadDetector(),
    )
    candidate = MeetingCandidate(
        summary="Suhbat: Saidazimxoja",
        start_time=datetime(2026, 6, 14, 13, 0, tzinfo=TZ),
        end_time=datetime(2026, 6, 14, 14, 0, tzinfo=TZ),
        description="",
    )

    result = await scheduler._sync_crm_lead_if_needed(
        _NameOnlyPeer(),
        "Saidazimxoja",
        [ContextMessage(text="Branding bo'yicha uchrashamiz", is_outgoing=False)],
        candidate,
    )

    assert result is None
    amo.ensure_lead.assert_not_awaited()
    amo.create_standalone_lead.assert_not_awaited()


@pytest.mark.asyncio
async def test_personal_chat_cannot_create_amocrm_task():
    amo = MagicMock()
    amo.create_task = AsyncMock(return_value=True)
    userbot = MagicMock()
    userbot.get_input_entity = AsyncMock(return_value="peer")
    message = MagicMock()
    message.out = False
    message.from_id = MagicMock(user_id=777)
    message.voice = None
    message.audio = None
    message.message = "Ertaga oilaviy uchrashuvni eslatib yuboring"
    userbot.get_messages = AsyncMock(return_value=[message])
    creator = TelegramTaskCreator(
        amocrm=amo,
        db=MagicMock(),
        user_client=userbot,
    )

    result = await creator.create_amocrm_tasks_from_chat(
        "@qarindosh",
        123,
        classification="family",
    )

    assert result == []
    amo.create_task.assert_not_awaited()
