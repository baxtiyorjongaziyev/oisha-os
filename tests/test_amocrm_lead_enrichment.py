import os
import tempfile
from types import SimpleNamespace

import pytest

from src.database import Database
from src.services.core.amocrm_lead_enrichment import (
    AmoCRMLeadEnricher,
    normalize_phone,
)


class FakeAmoCRM:
    def __init__(self):
        self.notes = []
        self.tags = []

    def add_lead_note(self, lead_id, text):
        self.notes.append({"lead_id": lead_id, "text": text})
        return {"id": 10}

    async def add_lead_tag(self, lead_id, tag_name):
        self.tags.append({"lead_id": lead_id, "tag_name": tag_name})
        return True


@pytest.fixture
async def temp_db():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as fh:
        db_path = fh.name

    db = Database(db_path)
    await db.init_db()
    try:
        yield db
    finally:
        await db.close()
        os.unlink(db_path)


@pytest.mark.asyncio
async def test_enrich_lead_uses_db_profile_and_recent_messages(temp_db):
    await temp_db.upsert_user(
        user_id=777,
        first_name="Ali",
        username="ali_brand",
        phone="+998901234567",
        brand_name="Ali Market",
    )
    await temp_db.log_message(777, "Logo va branding kerak, narx qancha?", is_ai=False)
    await temp_db.log_message(777, "Avval brifni aniqlashtirib olamiz.", is_ai=True)

    fake_amo = FakeAmoCRM()
    enricher = AmoCRMLeadEnricher(
        amocrm=fake_amo,
        db=temp_db,
        user_client=None,
        gemini_api_key="",
        refresh_hours=24,
    )
    enricher.genai_client = None

    result = await enricher.enrich_lead(
        lead_id=123,
        lead_data={"id": 123, "name": "Telegram Lead: Ali"},
        phone="90 123 45 67",
    )

    assert result.status == "enriched"
    assert result.telegram_user_id == 777
    assert result.note_added is True
    assert fake_amo.notes[0]["lead_id"] == 123
    assert "Telefon: +998901234567" in fake_amo.notes[0]["text"]
    assert "@ali_brand" in fake_amo.notes[0]["text"]
    assert "Logo va branding kerak" in fake_amo.notes[0]["text"]
    assert {"lead_id": 123, "tag_name": "Oisha analyzed"} in fake_amo.tags
    assert {"lead_id": 123, "tag_name": "Telegram matched"} in fake_amo.tags

    second = await enricher.enrich_lead(
        lead_id=123,
        lead_data={"id": 123, "name": "Telegram Lead: Ali"},
        phone="+998901234567",
    )
    assert second.status == "skipped"
    assert second.reason == "recently_enriched"


@pytest.mark.asyncio
async def test_enrich_lead_can_lookup_profile_through_userbot():
    class FakeUserClient:
        async def is_user_authorized(self):
            return True

        async def __call__(self, request):
            if request.__class__.__name__ == "ImportContactsRequest":
                return SimpleNamespace(
                    users=[
                        SimpleNamespace(
                            id=888,
                            username="telegram_found",
                            first_name="Vali",
                            last_name="Client",
                        )
                    ]
                )
            return SimpleNamespace()

        async def iter_messages(self, user_id, limit):
            yield SimpleNamespace(
                text="Sayt va SMM bo'yicha maslahat kerak",
                out=False,
                date="2026-05-24",
            )

    fake_amo = FakeAmoCRM()
    enricher = AmoCRMLeadEnricher(
        amocrm=fake_amo,
        db=None,
        user_client=FakeUserClient(),
        gemini_api_key="",
    )
    enricher.genai_client = None

    result = await enricher.enrich_lead(
        lead_id=456,
        lead_data={"id": 456, "name": "Website lead"},
        phone="+998 90 111 22 33",
    )

    assert result.status == "enriched"
    assert result.telegram_user_id == 888
    assert "Telegram: @telegram_found | tg://user?id=888" in fake_amo.notes[0]["text"]
    assert "Sayt va SMM" in fake_amo.notes[0]["text"]


@pytest.mark.asyncio
async def test_enrich_lead_skips_when_phone_missing():
    fake_amo = FakeAmoCRM()
    enricher = AmoCRMLeadEnricher(amocrm=fake_amo, gemini_api_key="")
    enricher.genai_client = None

    result = await enricher.enrich_lead(
        lead_id=789,
        lead_data={"id": 789},
        phone="",
    )

    assert result.status == "skipped"
    assert result.reason == "phone_missing"
    assert fake_amo.notes == []


def test_normalize_phone_adds_uzbekistan_prefix_for_local_number():
    assert normalize_phone("90 123-45-67") == "+998901234567"
