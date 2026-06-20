import os
import json
import pytest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from src.database import Database
from src.database_pool import SmartRow
from src.services.core.hisobchi_schema import init_hisobchi_tables
from src.services.core.hisobchi_engine import HisobchiEngine
from src.services.core.hisobchi_handlers import (
    parse_transaction_text_with_llm,
    process_finance_voice_message,
)


class DatabaseWrapper:
    def __init__(self, db: Database):
        self.db = db

    async def execute(self, query: str, params: list = None) -> list:
        if params is None:
            params = []
        conn = await self.db.get_connection()
        print("DATABASE CONNECTION TYPE:", type(conn), "DB PATH:", self.db.db_path)
        async with conn.execute(query, params) as cursor:
            description = cursor.description
            columns = [desc[0] for desc in description] if description else []
            rows = await cursor.fetchall()
            return [SmartRow(row, columns) for row in rows]

    async def commit(self) -> None:
        conn = await self.db.get_connection()
        await conn.commit()

    async def get_connection(self):
        return await self.db.get_connection()


@pytest.fixture
async def temp_db(tmp_path):
    db_file = tmp_path / "test_hisobchi.db"
    db = Database(str(db_file))
    await db.init_instance()
    wrapped = DatabaseWrapper(db)
    await init_hisobchi_tables(wrapped)
    yield wrapped
    await db.close()


@pytest.fixture
def mock_voice_processor():
    vp = MagicMock()
    vp.client = MagicMock()
    vp.model_name = "mock-gemini-model"
    vp.transcribe = AsyncMock(return_value="Matn: Bugun taksi uchun shaxsiy 25000 so'm xarajat qildim")
    vp.cleanup = AsyncMock()
    return vp


@pytest.mark.asyncio
async def test_database_schema_and_migration(tmp_path):
    db_file = tmp_path / "test_migration.db"
    db = Database(str(db_file))
    await db.init_instance()
    wrapped = DatabaseWrapper(db)

    # First init (creates tables)
    await init_hisobchi_tables(wrapped)

    # Check if ownership column exists by querying it
    conn = await db.get_connection()
    async with conn.execute("SELECT ownership FROM hisobchi_transactions") as cursor:
        rows = await cursor.fetchall()
        assert len(rows) == 0

    # Second init (should be safe and run alter table successfully/silently)
    await init_hisobchi_tables(wrapped)
    await db.close()


@pytest.mark.asyncio
async def test_engine_save_and_summary_with_ownership(temp_db):
    engine = HisobchiEngine(temp_db)

    # Save business transaction
    tx1_id = await engine.save_transaction(
        source_bot="humo",
        direction="out",
        amount=50000,
        merchant="Korzinka",
        card_suffix="1234",
        tx_time="12:00",
        balance=100000,
        raw_text="Korzinka text",
        ownership="business",
    )

    # Save personal transaction
    tx2_id = await engine.save_transaction(
        source_bot="uzcard",
        direction="out",
        amount=15000,
        merchant="Yandex Taxi",
        card_suffix="5678",
        tx_time="13:00",
        balance=50000,
        raw_text="Yandex text",
        ownership="personal",
    )

    # Save business income
    tx3_id = await engine.save_transaction(
        source_bot="voice",
        direction="in",
        amount=500000,
        merchant="Mijoz",
        card_suffix="",
        tx_time="14:00",
        balance=None,
        raw_text="Mijoz text",
        category="Dizayn",
        ownership="business",
        status="categorized",
    )

    # Update category and change personal transaction category
    await engine.categorize(tx1_id, "Ofis xarajati", "business")
    await engine.categorize(tx2_id, "Taksi", "personal")

    # Fetch summary for current month
    import datetime
    now_str = datetime.datetime.now().strftime("%Y-%m")
    summary = await engine.get_monthly_summary(now_str)

    assert "business" in summary
    assert "personal" in summary

    assert summary["business"]["income"] == 500000
    assert summary["business"]["expense"] == 50000
    assert summary["business"]["net"] == 450000
    assert summary["business"]["categories"] == {"Ofis xarajati": 50000}

    assert summary["personal"]["income"] == 0
    assert summary["personal"]["expense"] == 15000
    assert summary["personal"]["net"] == -15000
    assert summary["personal"]["categories"] == {"Taksi": 15000}

    # Verify build_monthly_report outputs both sections
    report = engine.build_monthly_report(now_str, summary)
    assert "Biznes moliyasi" in report
    assert "Shaxsiy moliya" in report
    assert "50 000 UZS" in report
    assert "15 000 UZS" in report


@pytest.mark.asyncio
async def test_parse_transaction_text_with_llm():
    mock_client = MagicMock()
    mock_response = SimpleNamespace(text='{"is_transaction": true, "amount": 25000, "direction": "out", "merchant": "Taksi", "category": "Taksi", "ownership": "personal", "reason": "taksi xarajati"}')

    with patch("src.services.core.hisobchi_handlers.generate_content_with_fallback", AsyncMock(return_value=(mock_response, "model"))) as mock_fallback:
        result = await parse_transaction_text_with_llm(mock_client, "gemini-1.5-flash", "bugun taksiga 25000 so'm berdim")
        assert result is not None
        assert result["is_transaction"] is True
        assert result["amount"] == 25000
        assert result["ownership"] == "personal"
        mock_fallback.assert_called_once()


@pytest.mark.asyncio
async def test_process_voice_message_standalone_business(temp_db, mock_voice_processor):
    engine = HisobchiEngine(temp_db)
    client = MagicMock()
    client.download_media = AsyncMock()

    mock_parsed = {
        "is_transaction": True,
        "amount": 50000,
        "direction": "out",
        "merchant": "Korzinka",
        "category": "Oziq-ovqat",
        "ownership": "business",
        "reason": "ofis uchun choy",
    }

    event = MagicMock()
    event.id = 999
    event.message = SimpleNamespace(voice=SimpleNamespace())
    event.reply = AsyncMock()

    # Mock the LLM call and settings
    with patch("src.services.core.hisobchi_handlers.parse_transaction_text_with_llm", AsyncMock(return_value=mock_parsed)), \
         patch("src.services.core.hisobchi_handlers._get_finance_config", return_value=(-100123, None, None)):

        processed = await process_finance_voice_message(event, client, engine, mock_voice_processor)
        assert processed is True
        event.reply.assert_awaited_once()
        assert "saqlandi" in event.reply.call_args[0][0].lower()
        assert "50 000" in event.reply.call_args[0][0]

        # Verify saved in DB
        conn = await temp_db.get_connection()
        async with conn.execute("SELECT amount, category, ownership FROM hisobchi_transactions WHERE id = 1") as cursor:
            row = await cursor.fetchone()
            assert row == (50000, "Oziq-ovqat", "business")


@pytest.mark.asyncio
async def test_process_voice_message_reply_categorization(temp_db, mock_voice_processor):
    engine = HisobchiEngine(temp_db)
    client = MagicMock()
    client.download_media = AsyncMock()

    # Save a pending transaction
    tx_id = await engine.save_transaction(
        source_bot="humo",
        direction="out",
        amount=100000,
        merchant="Paynet",
        card_suffix="9999",
        tx_time="10:00",
        balance=None,
        raw_text="Original text",
        finance_msg_id=777,
        finance_chat_id=-100123,
        status="pending",
    )

    mock_parsed = {
        "is_transaction": True,
        "amount": 0,
        "direction": "out",
        "merchant": "Paynet",
        "category": "Kommunal",
        "ownership": "personal",
        "reason": "uy uchun paynet",
    }

    event = MagicMock()
    event.id = 888
    event.message = SimpleNamespace(
        voice=SimpleNamespace(),
        reply_to=SimpleNamespace(reply_to_msg_id=777)
    )
    event.reply = AsyncMock()

    with patch("src.services.core.hisobchi_handlers.parse_transaction_text_with_llm", AsyncMock(return_value=mock_parsed)), \
         patch("src.services.core.hisobchi_handlers._get_finance_config", return_value=(-100123, None, None)):

        processed = await process_finance_voice_message(event, client, engine, mock_voice_processor)
        assert processed is True
        event.reply.assert_awaited_once()
        assert "javob saqlandi" in event.reply.call_args[0][0].lower()

        # Verify transaction was categorized and updated to personal
        conn = await temp_db.get_connection()
        async with conn.execute("SELECT status, category, ownership FROM hisobchi_transactions WHERE id = ?", (tx_id,)) as cursor:
            row = await cursor.fetchone()
            assert row == ("categorized", "Kommunal", "personal")

        # Verify category was learned for Paynet
        known = await engine.get_known_category("Paynet")
        assert known == "Kommunal"
