from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from src.services.core.meeting_scheduler import (
    ContextMessage,
    MeetingCandidate,
    TelegramMeetingScheduler,
    extract_meeting_candidate,
)


TZ = ZoneInfo("Asia/Tashkent")


class _FakeDB:
    def __init__(self):
        self.state = {}
        self.users = []

    async def get_state(self, key, default=""):
        return self.state.get(key, default)

    async def set_state(self, key, value):
        self.state[key] = value

    async def upsert_user(self, user_id, first_name, **kwargs):
        self.users.append({"user_id": user_id, "first_name": first_name, **kwargs})


class _FakeAmo:
    def __init__(self):
        self.ensure_calls = []
        self.standalone_calls = []

    async def ensure_lead(self, name, phone, note=None):
        self.ensure_calls.append({"name": name, "phone": phone, "note": note})
        return 111

    async def create_standalone_lead(self, **kwargs):
        self.standalone_calls.append(kwargs)
        return 222


class _FakeLeadDetector:
    def __init__(self, payload):
        self.payload = payload

    async def extract_lead_info(self, _text, _profile):
        return self.payload


class _Peer:
    id = 9001
    username = "ozodbek"
    phone = ""
    first_name = "Ozodbek"
    last_name = ""
    bot = False


class _FakeCalendar:
    def __init__(self):
        self.events = []

    def create_event(self, **kwargs):
        self.events.append(kwargs)
        return True


class _Msg:
    def __init__(self, text, out, date):
        self.text = text
        self.message = text
        self.out = out
        self.date = date
        self.media = None


class _Dialog:
    id = 9001
    is_user = True
    entity = _Peer()


class _FakeClient:
    def __init__(self, messages):
        self.messages = messages

    async def iter_dialogs(self, limit=80):
        yield _Dialog()

    async def get_messages(self, chat_id, limit=12):
        return self.messages[:limit]


def test_extracts_calendar_event_from_telegram_context():
    reference = datetime(2026, 5, 13, 20, 36, tzinfo=TZ)
    messages = [
        ContextMessage(
            text="Ofisimiz U Enter Innovatsion markazda",
            is_outgoing=True,
            created_at=datetime(2026, 5, 13, 20, 24, tzinfo=TZ),
        ),
        ContextMessage(
            text="[ Геопозиция ]\nhttps://maps.google.com/maps?q=41.305762,69.281445&ll=41.305762,69.281445&z=16",
            is_outgoing=True,
            created_at=datetime(2026, 5, 13, 20, 24, tzinfo=TZ),
        ),
        ContextMessage(
            text="Ertaga suhbatga soat nechchiga kelolasiz?",
            is_outgoing=True,
            created_at=datetime(2026, 5, 13, 20, 24, tzinfo=TZ),
        ),
        ContextMessage(
            text="13 00",
            is_outgoing=False,
            created_at=datetime(2026, 5, 13, 20, 35, tzinfo=TZ),
        ),
        ContextMessage(
            text="ok 14.05.2026 13:00 ga yozib qo'ydim",
            is_outgoing=True,
            created_at=reference,
        ),
        ContextMessage(
            text="Hop bo'ladi",
            is_outgoing=False,
            created_at=reference,
        ),
    ]

    candidate = extract_meeting_candidate(messages, reference, "Axmedov Ozodbek")

    assert candidate is not None
    assert candidate.summary == "Suhbat: Axmedov Ozodbek"
    assert candidate.start_time.isoformat() == "2026-05-14T13:00:00+05:00"
    assert candidate.end_time.isoformat() == "2026-05-14T14:00:00+05:00"
    assert "U Enter" in candidate.location
    assert "41.305762,69.281445" in candidate.location
    assert candidate.confidence >= 0.9


def test_does_not_schedule_without_meeting_intent():
    reference = datetime(2026, 5, 13, 20, 36, tzinfo=TZ)
    messages = [
        ContextMessage(text="Ertaga 13 00", is_outgoing=False, created_at=reference),
        ContextMessage(text="Hop bo'ladi", is_outgoing=True, created_at=reference),
    ]

    assert extract_meeting_candidate(messages, reference, "Client") is None


def test_does_not_confuse_date_fragment_with_time():
    reference = datetime(2026, 5, 13, 20, 36, tzinfo=TZ)
    messages = [
        ContextMessage(
            text="Ertaga suhbatga soat nechchiga kelolasiz?",
            is_outgoing=True,
            created_at=reference,
        ),
        ContextMessage(
            text="ok 14.05.2026 13:00 ga yozib qo'ydim",
            is_outgoing=True,
            created_at=reference,
        ),
        ContextMessage(text="Hop bo'ladi", is_outgoing=False, created_at=reference),
    ]

    candidate = extract_meeting_candidate(messages, reference, "Client")

    assert candidate is not None
    assert candidate.start_time.hour == 13
    assert candidate.start_time.minute == 0


@pytest.mark.asyncio
async def test_calendar_meeting_syncs_to_amocrm_when_context_is_lead():
    db = _FakeDB()
    amo = _FakeAmo()
    detector = _FakeLeadDetector(
        {
            "is_lead": True,
            "phone": "+998901112233",
            "intent_category": "HOT_LEAD",
            "needs": "Logo va branding konsultatsiyasi",
        }
    )
    scheduler = TelegramMeetingScheduler(
        db=db,
        gcalendar=None,
        amocrm=amo,
        lead_detector=detector,
    )
    candidate = MeetingCandidate(
        summary="Suhbat: Ozodbek",
        start_time=datetime(2026, 5, 14, 13, 0, tzinfo=TZ),
        end_time=datetime(2026, 5, 14, 14, 0, tzinfo=TZ),
        description="",
        location="U Enter",
    )

    lead_id = await scheduler._sync_crm_lead_if_needed(
        _Peer(),
        "Ozodbek",
        [
            ContextMessage(
                text="Logo va brending bo'yicha konsultatsiyaga kelaman",
                is_outgoing=False,
                created_at=datetime(2026, 5, 13, 20, 35, tzinfo=TZ),
            )
        ],
        candidate,
    )

    assert lead_id == 111
    assert amo.ensure_calls[0]["phone"] == "+998901112233"
    assert "Uchrashuv vaqti: 14.05.2026 13:00" in amo.ensure_calls[0]["note"]
    assert db.state["crm:lead:9001"] == "111"


@pytest.mark.asyncio
async def test_calendar_meeting_does_not_sync_to_amocrm_when_not_lead():
    amo = _FakeAmo()
    scheduler = TelegramMeetingScheduler(
        db=_FakeDB(),
        gcalendar=None,
        amocrm=amo,
        lead_detector=_FakeLeadDetector({"is_lead": False}),
    )
    candidate = MeetingCandidate(
        summary="Suhbat: Ozodbek",
        start_time=datetime(2026, 5, 14, 13, 0, tzinfo=TZ),
        end_time=datetime(2026, 5, 14, 14, 0, tzinfo=TZ),
        description="",
    )

    lead_id = await scheduler._sync_crm_lead_if_needed(
        _Peer(),
        "Ozodbek",
        [ContextMessage(text="Shaxsiy uchrashuv", is_outgoing=False)],
        candidate,
    )

    assert lead_id is None
    assert amo.ensure_calls == []
    assert amo.standalone_calls == []


@pytest.mark.asyncio
async def test_scan_recent_dialogs_finds_meeting_and_syncs_lead():
    db = _FakeDB()
    amo = _FakeAmo()
    calendar = _FakeCalendar()
    detector = _FakeLeadDetector(
        {
            "is_lead": True,
            "phone": "+998901112233",
            "intent_category": "HOT_LEAD",
            "needs": "Branding konsultatsiyasi",
        }
    )
    scheduler = TelegramMeetingScheduler(
        db=db,
        gcalendar=calendar,
        amocrm=amo,
        lead_detector=detector,
    )
    now = datetime(2026, 5, 13, 20, 36, tzinfo=TZ)
    client = _FakeClient(
        [
            _Msg("Hop bo'ladi", out=False, date=now),
            _Msg("ok 14.05.2026 13:00 ga yozib qo'ydim", out=True, date=now),
            _Msg("13 00", out=False, date=datetime(2026, 5, 13, 20, 35, tzinfo=TZ)),
            _Msg(
                "Ertaga branding bo'yicha suhbatga soat nechchiga kelolasiz?",
                out=True,
                date=datetime(2026, 5, 13, 20, 24, tzinfo=TZ),
            ),
        ]
    )

    result = await scheduler.scan_recent_dialogs(
        client,
        dialog_limit=10,
        message_limit=10,
        max_age_hours=72,
    )

    assert result["scanned"] == 1
    assert result["created"] == 1
    assert calendar.events[0]["start_time"] == "2026-05-14T13:00:00+05:00"
    assert amo.ensure_calls[0]["phone"] == "+998901112233"
    assert db.users[0]["meeting_status"] == "scheduled"
