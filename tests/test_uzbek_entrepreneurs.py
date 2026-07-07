"""Tests for Uzbek Entrepreneurs system."""
from __future__ import annotations

import pytest
from types import SimpleNamespace

from src.database import Database
from src.services.core.uzbek_entrepreneurs_schema import (
    init_uzbek_entrepreneurs_tables,
)
from src.services.core.finance.hisobchi_schema import ensure_hisobchi_db
from src.services.core.uzbek_entrepreneurs_scraper import (
    UzbekEntrepreneurScraper,
    ScrapedEntrepreneur,
)
from src.services.core.uzbek_voice_agent import (
    UzbekVoiceAgent,
    VapiCallConfig,
)


@pytest.fixture
async def temp_db(tmp_path):
    """Create temporary database for testing."""
    db = Database(str(tmp_path / "uzbek_test.db"))
    await db.init_instance()
    await init_uzbek_entrepreneurs_tables(db)
    yield db
    await db.close()


@pytest.mark.asyncio
async def test_uzbek_tables_initialized(temp_db) -> None:
    """Test that Uzbek Entrepreneurs tables are created."""
    rows = await temp_db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'uzbek%' OR name LIKE 'entrepreneur%'"
    )
    table_names = [row["name"] for row in rows]

    expected_tables = [
        "uzbek_entrepreneurs",
        "entrepreneur_call_logs",
        "entrepreneur_scraping_queue",
        "entrepreneur_call_queue",
        "call_operators",
    ]

    for table in expected_tables:
        assert table in table_names, f"Table {table} not found"


@pytest.mark.asyncio
async def test_save_entrepreneur(temp_db) -> None:
    """Test saving an entrepreneur to database."""
    scraper = UzbekEntrepreneurScraper(temp_db)

    entrepreneur = ScrapedEntrepreneur(
        full_name="Aziz Karimov",
        first_name="Aziz",
        last_name="Karimov",
        phone="+998901234567",
        email="aziz@example.com",
        company="Tech Solutions",
        industry="Technology",
        country="US",
        city="New York",
        linkedin_url="https://linkedin.com/in/aziz-karimov",
        instagram_url=None,
        telegram_username="aziz_karimov",
        facebook_url=None,
        scraping_source="linkedin",
        source_url="https://linkedin.com/in/aziz-karimov",
        lead_score=85,
    )

    entrepreneur_id = await scraper.save_entrepreneur(entrepreneur)

    assert entrepreneur_id is not None
    assert entrepreneur_id > 0

    # Verify saved data
    rows = await temp_db.execute(
        "SELECT * FROM uzbek_entrepreneurs WHERE id = ?",
        [entrepreneur_id],
    )

    assert len(rows) == 1
    assert rows[0]["full_name"] == "Aziz Karimov"
    assert rows[0]["phone"] == "+998901234567"
    assert rows[0]["lead_score"] == 85


@pytest.mark.asyncio
async def test_uzbek_name_detection() -> None:
    """Test Uzbek name detection."""
    scraper = UzbekEntrepreneurScraper()

    # Should match
    assert scraper.is_uzbek_name("Aziz Karimov")
    assert scraper.is_uzbek_name("Baxtiyor Toshmatov")
    assert scraper.is_uzbek_name("Jamshid Rasulov")

    # Should not match
    assert not scraper.is_uzbek_name("John Smith")
    assert not scraper.is_uzbek_name("Maria Garcia")


@pytest.mark.asyncio
async def test_uzbek_keyword_detection() -> None:
    """Test Uzbek keyword detection."""
    scraper = UzbekEntrepreneurScraper()

    # Should match
    assert scraper.has_uzbek_connection("Born in Tashkent, Uzbekistan")
    assert scraper.has_uzbek_connection("Uzbek diaspora in USA")
    assert scraper.has_uzbek_connection("Samarkand native")

    # Should not match
    assert not scraper.has_uzbek_connection("Born in California")
    assert not scraper.has_uzbek_connection("New York based")


@pytest.mark.asyncio
async def test_lead_score_calculation() -> None:
    """Test lead score calculation."""
    scraper = UzbekEntrepreneurScraper()

    # High score - all data present
    score1 = scraper.calculate_lead_score(
        has_phone=True, has_email=True, has_company=True, is_ceo_level=True
    )
    assert score1 == 100

    # Medium score - some data
    score2 = scraper.calculate_lead_score(
        has_phone=True, has_email=False, has_company=True, is_ceo_level=False
    )
    assert score2 == 45

    # Low score - minimal data
    score3 = scraper.calculate_lead_score(
        has_phone=False, has_email=False, has_company=False, is_ceo_level=False
    )
    assert score3 == 30


@pytest.mark.asyncio
async def test_duplicate_prevention(temp_db) -> None:
    """Test that duplicate entrepreneurs are prevented."""
    scraper = UzbekEntrepreneurScraper(temp_db)

    entrepreneur = ScrapedEntrepreneur(
        full_name="Test User",
        first_name="Test",
        last_name="User",
        phone="+998901234567",
        email=None,
        company=None,
        industry=None,
        country="US",
        city=None,
        linkedin_url="https://linkedin.com/in/test-user",
        instagram_url=None,
        telegram_username=None,
        facebook_url=None,
        scraping_source="linkedin",
        source_url="https://linkedin.com/in/test-user",
        lead_score=50,
    )

    # First save should succeed
    id1 = await scraper.save_entrepreneur(entrepreneur)
    assert id1 is not None

    # Second save with same LinkedIn URL should fail
    id2 = await scraper.save_entrepreneur(entrepreneur)
    assert id2 is None

    # Verify only one record exists
    rows = await temp_db.execute("SELECT COUNT(*) as cnt FROM uzbek_entrepreneurs")
    assert rows[0]["cnt"] == 1


@pytest.mark.asyncio
async def test_scraping_queue_logging(temp_db) -> None:
    """Test scraping queue logging."""
    scraper = UzbekEntrepreneurScraper(temp_db)

    queue_id = await scraper.log_scraping_queue(
        source="linkedin",
        search_query="uzbek entrepreneur",
        target_country="US",
        status="processing",
    )

    assert queue_id is not None
    assert queue_id > 0

    # Verify queue record
    rows = await temp_db.execute(
        "SELECT * FROM entrepreneur_scraping_queue WHERE id = ?",
        [queue_id],
    )

    assert len(rows) == 1
    assert rows[0]["source"] == "linkedin"
    assert rows[0]["search_query"] == "uzbek entrepreneur"
    assert rows[0]["status"] == "processing"


@pytest.mark.asyncio
async def test_voice_agent_config() -> None:
    """Test Vapi configuration."""
    config = VapiCallConfig(
        api_key="test_key",
        phone_number_id="test_phone_id",
        assistant_id="test_assistant_id",
        voice_url="https://example.com/voice.mp3",
    )

    assert config.api_key == "test_key"
    assert config.phone_number_id == "test_phone_id"
    assert config.assistant_id == "test_assistant_id"
    assert config.voice_url == "https://example.com/voice.mp3"


@pytest.mark.asyncio
async def test_database_adapter_preserves_mapping(temp_db) -> None:
    """Test that database adapter preserves Turso mapping."""
    from src.services.core.uzbek_entrepreneurs_schema import ensure_hisobchi_db

    _db = ensure_hisobchi_db(temp_db)

    # This should work with both direct Database and Turso connection
    rows = await _db.execute("SELECT 1 AS test")
    assert rows[0]["test"] == 1


def test_uzbek_phone_normalization() -> None:
    """Test phone number normalization."""
    from src.services.core.uzbek_voice_agent import UzbekVoiceAgent

    agent = UzbekVoiceAgent(
        VapiCallConfig(
            api_key="test",
            phone_number_id="test",
            assistant_id="test",
            voice_url="test",
        )
    )

    # Test card suffix normalization
    assert agent._normalize_card_suffix("1234") == "1234"
    assert agent._normalize_card_suffix("+998901234567") == "4567"
    assert agent._normalize_card_suffix("ABC1234DEF") == "1234"
