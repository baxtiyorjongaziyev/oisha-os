"""
Tests for Customer 360 Ecosystem and Obsidian Synchronization.
"""
import os
import tempfile
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from src.services.customer_360.models import CallInteraction, Customer360Profile
from src.services.customer_360.collector import Customer360Collector
from src.services.customer_360.obsidian_syncer import Customer360ObsidianSyncer
from src.services.customer_360.query_engine import Customer360QueryEngine


@pytest.fixture
def sample_profile() -> Customer360Profile:
    call = CallInteraction(
        call_id="call_12345",
        timestamp="2026-09-04 14:30",
        duration_seconds=240,
        caller_phone="+998901234567",
        manager_name="Shahnoza",
        category="Mijoz",
        summary="Mijoz brending va qadoq dizayni bo'yicha narxlarni so'radi.",
        client_mood="Ijobiy / Qiziqish yuqori",
        client_talk_pct=65,
        manager_talk_pct=35,
        seller_score=8,
        client_score=9,
        agreed_datetime="2026-09-05 11:00",
        conversion_advice="Mijozga 3 xil tarifli KP yuborish va 11:00 da qo'ng'iroq qilish",
        transcript="Assalomu alaykum, bizga brending va qadoq dizayni kerak edi...",
    )
    return Customer360Profile(
        name="Kamila Pardalari",
        phone="+998901234567",
        telegram_username="kamila_pardalari",
        instagram_handle="kamila_curtains",
        amocrm_lead_id=12345678,
        amocrm_lead_name="Kamila Pardalari Brending",
        amocrm_pipeline="Sotuv Voronkasi",
        amocrm_status="Muzokara",
        amocrm_budget=25_000_000,
        responsible_manager="Shahnoza",
        tags=["Branding", "Patent"],
        airtable_project_name="Kamila Pardalari Identity",
        airtable_phase="Logo Sprint 2",
        airtable_paid=1200.0,
        airtable_debt=300.0,
        airtable_deadline="2026-09-20",
        calls=[call],
        telegram_messages=["Bizga qadoq dizayni ham kerak bo'ladi."],
    )


def test_markdown_formatting(sample_profile: Customer360Profile):
    syncer = Customer360ObsidianSyncer(vault_paths=[])
    md = syncer.format_markdown(sample_profile)

    assert "title: \"Kamila Pardalari\"" in md
    assert "type: customer-360" in md
    assert "+998901234567" in md
    assert "@kamila_pardalari" in md
    assert "25 000 000 so'm" in md
    assert "Kamila Pardalari Identity" in md
    assert "$1,200" in md
    assert "Sotuvchi: 8/10" in md
    assert "Mijoz 65% / Sotuvchi 35%" in md
    assert "Mijoz brending va qadoq dizayni bo'yicha narxlarni so'radi." in md
    assert "2026-09-05 11:00" in md


@pytest.mark.asyncio
async def test_obsidian_syncer_file_write(sample_profile: Customer360Profile):
    with tempfile.TemporaryDirectory() as tmpdir:
        syncer = Customer360ObsidianSyncer(vault_paths=[tmpdir])
        filepath = await syncer.sync_profile(sample_profile)

        assert os.path.exists(filepath)
        assert ("20-CLIENTS" in filepath or "70-Mijozlar" in filepath)
        assert "Kamila Pardalari" in filepath

        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        assert "Kamila Pardalari" in content
        assert "25 000 000 so'm" in content


@pytest.mark.asyncio
async def test_collector_enrichment():
    mock_amocrm = MagicMock()
    mock_amocrm.get_lead.return_value = {
        "id": 9999,
        "name": "Ledir Brand",
        "price": 15000000,
        "tags": [{"name": "Naming"}],
        "responsible_user_id": 42,
    }
    mock_airtable = MagicMock()
    mock_airtable.get_projects.return_value = [
        {
            "fields": {
                "Project Name": "Ledir Brand Concept",
                "Status": "Naming approved",
                "Paid": 800,
                "Debt": 200,
            }
        }
    ]

    collector = Customer360Collector(amocrm=mock_amocrm, airtable=mock_airtable)
    call_event = {
        "call_id": "c_99",
        "duration_seconds": 120,
        "caller_phone": "+998931112233",
        "manager_name": "Inomjon",
        "category": "Mijoz",
        "summary": "Naming bo'yicha 5 ta variant taqdim etildi.",
        "client_mood": "Mamnun",
        "client_talk_pct": 50,
        "manager_talk_pct": 50,
        "seller_score": 9,
    }

    profile = await collector.collect_profile(
        identifier="Ledir Brand",
        lead_id=9999,
        phone="+998931112233",
        call_event=call_event,
    )

    assert profile.name == "Ledir Brand"
    assert profile.amocrm_budget == 15000000
    assert profile.airtable_project_name == "Ledir Brand Concept"
    assert profile.airtable_paid == 800
    assert len(profile.calls) == 1
    assert profile.calls[0].seller_score == 9


@pytest.mark.asyncio
async def test_query_engine_reads_card():
    with tempfile.TemporaryDirectory() as tmpdir:
        folder = os.path.join(tmpdir, "70-Mijozlar")
        os.makedirs(folder, exist_ok=True)
        card_file = os.path.join(folder, "Kamila Pardalari.md")
        with open(card_file, "w", encoding="utf-8") as f:
            f.write("# Kamila Pardalari\n- Telefon: +998901234567\n- To'langan: $1200")

        engine = Customer360QueryEngine(vault_paths=[tmpdir], gemini_api_key=None)
        with patch("src.agents.ai_router.route", new_callable=AsyncMock) as mock_route:
            mock_route.return_value = {
                "success": True,
                "text": "Kamila Pardalari: Telefon +998901234567, To'langan summa $1200.",
            }
            answer = await engine.answer_query("Kamila Pardalari haqida ma'lumot ber")

        assert "+998901234567" in answer
        assert "$1200" in answer

