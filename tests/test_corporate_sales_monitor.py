"""
Korporativ sotuv monitoringi moduli uchun unit testlar.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import aiosqlite
import pytest

from src.services.corporate_sales.models import (
    ConversationBuffer,
    CorporateSeller,
    MessageSenderType,
    MonitoredChatMessage,
    SellerPerformanceSummary,
)
from src.services.corporate_sales.monitor import CorporateSalesMonitor
from src.services.corporate_sales.repository import CorporateSalesRepository
from src.services.corporate_sales.reporter import CorporateSalesReporter


@pytest.fixture
async def in_memory_db():
    """In-memory SQLite ulanishi fixture."""
    conn = await aiosqlite.connect(":memory:")
    yield conn
    await conn.close()


@pytest.fixture
async def repo(in_memory_db):
    """Tayyor repository fixture."""
    mock_db = MagicMock()
    mock_db.get_connection = AsyncMock(return_value=in_memory_db)
    repository = CorporateSalesRepository(mock_db)
    await repository.init_tables()
    return repository


# ──────────────────────────────────────────────────────────────────
# 1. Models Testlari
# ──────────────────────────────────────────────────────────────────

def test_corporate_seller_model():
    seller = CorporateSeller(
        seller_id=1,
        name="Alisher",
        phone="+998901234567",
        session_string="test_session_123",
    )
    data = seller.to_dict()
    assert data["seller_id"] == 1
    assert data["name"] == "Alisher"
    assert data["phone"] == "+998901234567"
    assert data["is_active"] is True

    from_dict = CorporateSeller.from_row(data)
    assert from_dict.name == "Alisher"

    from_tuple = CorporateSeller.from_row(
        (2, "Sardor", "+998909876543", "sess", 1, "2026-01-01", "2026-01-01")
    )
    assert from_tuple.seller_id == 2
    assert from_tuple.name == "Sardor"


def test_monitored_chat_message():
    msg = MonitoredChatMessage(
        message_id=101,
        sender_type=MessageSenderType.SELLER,
        sender_name="Sardor",
        text="Assalomu alaykum, qanday loyiha rejalashtiryapsiz?",
    )
    line = msg.to_transcript_line()
    assert "[Menejer (Sardor)]:" in line
    assert "qanday loyiha rejalashtiryapsiz?" in line


def test_conversation_buffer_lifecycle():
    buf = ConversationBuffer(
        seller_id=1,
        seller_name="Alisher",
        client_peer_id=555,
        client_name="Oqshom",
    )
    assert not buf.is_substantive()

    # Xabarlar qoʻshish
    buf.add_message(
        MonitoredChatMessage(
            message_id=1,
            sender_type=MessageSenderType.CLIENT,
            sender_name="Mijoz",
            text="Assalomu alaykum, brending kerak",
        )
    )
    buf.add_message(
        MonitoredChatMessage(
            message_id=2,
            sender_type=MessageSenderType.SELLER,
            sender_name="Alisher",
            text="Va alaykum assalom! Qaysi soha boʻyicha?",
        )
    )
    buf.add_message(
        MonitoredChatMessage(
            message_id=3,
            sender_type=MessageSenderType.CLIENT,
            sender_name="Mijoz",
            text="Mebel ishlab chiqarish",
        )
    )

    assert buf.get_message_count() == 3
    assert buf.get_seller_message_count() == 1
    assert buf.get_client_message_count() == 2
    assert buf.is_substantive()

    # Tinch turishini tekshirish
    buf.last_activity_at = datetime.now(timezone.utc) - timedelta(seconds=400)
    assert buf.is_idle(timeout_seconds=300)

    # Transkript va tozalash
    transcript = buf.to_transcript()
    assert "Mebel ishlab chiqarish" in transcript
    buf.clear()
    assert buf.get_message_count() == 0


# ──────────────────────────────────────────────────────────────────
# 2. Repository Testlari
# ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_repository_crud(repo):
    # Upsert seller
    seller = await repo.upsert_seller(
        name="Jasur",
        phone="+998901112233",
        session_string="sess_jasur",
    )
    assert seller is not None
    assert seller.name == "Jasur"

    # Get by phone
    found = await repo.get_seller_by_phone("+998901112233")
    assert found is not None
    assert found.phone == "+998901112233"

    # All active
    all_active = await repo.get_all_active_sellers()
    assert len(all_active) == 1

    # Deactivate
    deact = await repo.deactivate_seller(found.seller_id)
    assert deact is True
    assert len(await repo.get_all_active_sellers()) == 0


@pytest.mark.asyncio
async def test_repository_save_analysis(repo):
    ok = await repo.save_conversation_analysis(
        conversation_id="conv_101",
        manager_id=1,
        manager_name="Jasur",
        overall_score=85,
        deal_outcome="uchrashuv_kelishildi",
        objections=["qimmat"],
        strengths=["Ehtiyoj aniqlandi"],
        weaknesses=["Shoshildi"],
        recommendations=["Portfolio yuborilsin"],
    )
    assert ok is True


# ──────────────────────────────────────────────────────────────────
# 3. Reporter Testlari
# ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_reporter_formatting_and_send():
    mock_bot = AsyncMock()
    mock_amocrm = AsyncMock()

    reporter = CorporateSalesReporter(
        bot_client=mock_bot,
        rop_chat_id=-1001234567,
        amocrm_client=mock_amocrm,
    )

    report_text = reporter.format_rop_report(
        seller_name="Alisher",
        seller_phone="+998901234567",
        client_name="Grand Mebel",
        client_handle="@grandmebel",
        overall_score=85,
        deal_outcome="uchrashuv_belgilandi",
        strengths=["Ehtiyoj toʻliq aniqlandi", "Jonli muloqot"],
        weaknesses=["Patent bazasi tekshiruvi eslatilmadi"],
        objections=["qimmat"],
        recommendations=["Ertaga soat 11:00 da qoʻngʻiroq qilinsin"],
    )

    assert "Alisher" in report_text
    assert "Grand Mebel" in report_text
    assert "85/100" in report_text
    assert "Ehtiyoj toʻliq aniqlandi" in report_text

    sent = await reporter.send_to_rop(report_text)
    assert sent is True
    assert mock_bot.send_message.called

    crm_sync = await reporter.sync_to_amocrm_lead(lead_id=999, report_text=report_text)
    assert crm_sync is True
    assert mock_amocrm.add_lead_note.called


# ──────────────────────────────────────────────────────────────────
# 4. Monitor Testlari
# ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_monitor_message_handling_and_flush(repo):
    mock_reporter = AsyncMock()
    mock_analyzer = AsyncMock()
    mock_analysis = MagicMock()
    mock_analysis.overall_score = 90
    mock_analysis.outcome = "uchrashuv_kelishildi"
    mock_analysis.strengths = ["Namunali"]
    mock_analysis.weaknesses = []
    mock_analysis.objections_detected = []
    mock_analysis.action_items = ["Shartnoma tayyorlansin"]
    mock_analyzer.analyze_conversation_ai = AsyncMock(return_value=mock_analysis)

    monitor = CorporateSalesMonitor(
        repository=repo,
        reporter=mock_reporter,
        quality_analyzer=mock_analyzer,
        idle_timeout_seconds=10,
    )

    seller = CorporateSeller(
        seller_id=1,
        name="Sardor",
        phone="+998901234567",
        session_string="sess_test",
    )

    # 1. Yangi xabarlarni qoʻshish
    await monitor.handle_new_message(
        seller,
        peer_id=777,
        message_id=1,
        text="Assalomu alaykum",
        is_outgoing=False,
        sender_name="Mijoz",
    )
    await monitor.handle_new_message(
        seller,
        peer_id=777,
        message_id=2,
        text="Va alaykum assalom, qanday xizmat kerak?",
        is_outgoing=True,
    )
    await monitor.handle_new_message(
        seller,
        peer_id=777,
        message_id=3,
        text="Brending va patent kerak edi",
        is_outgoing=False,
        sender_name="Mijoz",
    )

    buf = monitor.get_active_buffer(seller, 777)
    assert buf.get_message_count() == 3

    # 2. Tinch turishini simulyatsiya qilish va flush qilish
    buf.last_activity_at = datetime.now(timezone.utc) - timedelta(seconds=20)
    flushed_count = await monitor.check_all_idle_buffers()
    assert flushed_count == 1
    assert mock_analyzer.analyze_conversation_ai.called
    assert mock_reporter.deliver_report.called
