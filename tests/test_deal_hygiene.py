import pytest

from src.services.core.deal_hygiene import (
    AmoCRMDealHygieneAgent,
    extract_usernames,
    normalize_phone,
)


class _FakeCursor:
    description = [
        ("user_id",),
        ("first_name",),
        ("last_name",),
        ("username",),
        ("phone",),
        ("intent",),
        ("role",),
        ("detailed_role",),
    ]

    def __init__(self, rows):
        self._rows = rows

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return None

    async def fetchall(self):
        return self._rows


class _FakeConn:
    def __init__(self, rows):
        self._rows = rows

    def execute(self, *_args, **_kwargs):
        return _FakeCursor(self._rows)


class _FakeDB:
    def __init__(self):
        self.analyses = {}
        self.profile_rows = []

    async def get_connection(self):
        return _FakeConn(self.profile_rows)

    async def get_latest_call_analysis(self, lead_id):
        return self.analyses.get(lead_id)


class _FakeAmo:
    subdomain = "jonbrandingagency"

    def __init__(self):
        self.leads = []
        self.notes = {}
        self.contacts = {}
        self.tags = []
        self.added_notes = []
        self.tasks = []

    async def get_leads_detailed(self, limit=100):
        return self.leads[:limit]

    async def get_lead_notes(self, lead_id):
        return self.notes.get(lead_id, [])

    def get_contact_details(self, contact_id):
        return self.contacts.get(contact_id)

    async def add_lead_tag(self, lead_id, tag_name):
        self.tags.append((lead_id, tag_name))
        return True

    def add_lead_note(self, lead_id, text):
        self.added_notes.append((lead_id, text))
        return {"_embedded": {"notes": [{"id": 1}]}}

    async def create_task(self, element_id, text, complete_till, responsible_user_id=None):
        self.tasks.append((element_id, text, complete_till, responsible_user_id))
        return {"_embedded": {"tasks": [{"id": 77}]}}


def test_phone_and_username_normalization():
    assert normalize_phone("+998 90 820 33 33") == "908203333"
    assert normalize_phone("90 820-33-33") == "908203333"
    assert extract_usernames("Telegram: @Abdujalil_3333") == {"abdujalil_3333"}


@pytest.mark.asyncio
async def test_hygiene_finds_metasell_noise_and_duplicate_probability():
    amo = _FakeAmo()
    db = _FakeDB()
    db.profile_rows = [
        (9001, "Abdujalil", "Rasulov", "Abdujalil_3333", "+998908203333", "", "", ""),
    ]
    db.analyses[101] = {
        "outcome": "lost",
        "client_interest_level": 10,
        "summary": "Mijoz qiziqmagan, qayta aloqa kerak emas.",
    }
    amo.leads = [
        {
            "id": 101,
            "name": "SABAB MEBEL",
            "status_id": 123,
            "pipeline_id": 1,
            "responsible_user_id": 5,
            "updated_at": 10,
            "_embedded": {"contacts": [{"id": 501}]},
        },
        {
            "id": 102,
            "name": "Telegram Lead @Abdujalil_3333",
            "status_id": 123,
            "pipeline_id": 1,
            "responsible_user_id": 5,
            "updated_at": 11,
            "_embedded": {"contacts": [{"id": 502}]},
        },
    ]
    contact_fields = [
        {
            "field_code": "PHONE",
            "values": [{"value": "+998 90 820 33 33"}],
        },
        {
            "field_name": "Telegram",
            "values": [{"value": "@Abdujalil_3333"}],
        },
    ]
    amo.contacts = {
        501: {"id": 501, "name": "Abdujalil", "custom_fields_values": contact_fields},
        502: {"id": 502, "name": "Abdujalil", "custom_fields_values": contact_fields},
    }
    amo.notes = {
        101: [{"note_type": "common", "params": {"text": "MetaSell: qiziqmagan"}}],
        102: [{"note_type": "common", "params": {"text": "Telegramdan yozgan"}}],
    }

    report = await AmoCRMDealHygieneAgent(amo, db).audit(limit=10)

    assert report["unnecessary_count"] == 1
    assert report["unnecessary_deals"][0]["lead_id"] == 101
    assert report["unnecessary_deals"][0]["category"] == "low_quality_lost"
    assert report["duplicate_group_count"] == 1
    duplicate = report["duplicate_suspects"][0]
    assert set(duplicate["lead_ids"]) == {101, 102}
    assert duplicate["probability"] >= 0.9
    assert "abdujalil_3333" in duplicate["telegram_usernames"]


@pytest.mark.asyncio
async def test_apply_report_only_adds_safe_annotations():
    amo = _FakeAmo()
    agent = AmoCRMDealHygieneAgent(amo, _FakeDB())
    report = {
        "unnecessary_deals": [
            {
                "lead_id": 101,
                "category": "spam",
                "confidence": 0.91,
                "reason": "Noto'g'ri raqam",
                "evidence": ["crm_notes: Noto'g'ri raqam"],
                "tag": "OISHA_SPAM_OR_WRONG",
            }
        ],
        "duplicate_suspects": [
            {
                "lead_ids": [101, 102],
                "probability": 0.96,
                "phones": ["908203333"],
                "telegram_usernames": ["abdujalil_3333"],
                "evidence": ["phone mos tushdi"],
            }
        ],
    }

    result = await agent.apply_report(report, create_tasks=True)

    assert result["failed"] == 0
    assert (101, "OISHA_SPAM_OR_WRONG") in amo.tags
    assert (101, "OISHA_DUPLICATE_SUSPECT") in amo.tags
    assert (102, "OISHA_DUPLICATE_SUSPECT") in amo.tags
    assert len(amo.tasks) == 2
