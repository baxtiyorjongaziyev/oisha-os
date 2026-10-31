"""Unit tests for Sales Staff Copilot and Hourly Check-in Scheduler."""
from __future__ import annotations

import os
import sqlite3
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from src.services.core.sales_staff_copilot import (
    DEFAULT_RULE_BASED_ADVICE,
    format_copilot_reply,
    generate_copilot_advice,
    handle_sales_staff_interaction,
    is_checkin_interaction,
    save_checkin_report,
)
from src.schedulers.remote_staff_checkin_scheduler import (
    build_checkin_message,
    format_duration,
    is_work_hour,
)


def test_is_checkin_interaction_by_reply():
    assert is_checkin_interaction(
        "Alisher aka bilan gaplashdim",
        reply_to_text="⚡ Soatlik Check-in: @RayxonJonbranding (soat 11:00)",
    ) is True

    assert is_checkin_interaction(
        "Hamma ishlar yaxshi",
        reply_to_text="Assalomu alaykum! Check-in vaqti",
    ) is True


def test_is_checkin_interaction_by_username_and_keywords():
    assert is_checkin_interaction(
        "Mijoz narx qimmat deyapti, nima deb javob beray?",
        username="RayxonJonbranding",
    ) is True

    assert is_checkin_interaction(
        "Yangi lidlar bo'yicha taklif yubordim",
        username="@rayxona",
    ) is True

    # Irrelevant chat from other user
    assert is_checkin_interaction(
        "Bugun havo yaxshi",
        username="random_user",
    ) is False


def test_format_copilot_reply():
    formatted = format_copilot_reply("Mijozga shunday deng: narx sifatga mos.", rep_name="Rayxon")
    assert "Sotuv Copilot (Oisha)" in formatted
    assert "Mijozga shunday deng" in formatted


def test_save_checkin_report(tmp_path):
    test_db = tmp_path / "test_bot.db"
    conn = sqlite3.connect(test_db)
    conn.execute(
        """
        CREATE TABLE team_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            report_date TEXT,
            report_type TEXT,
            content TEXT,
            status TEXT,
            created_at TEXT
        )
        """
    )
    conn.close()

    ok = save_checkin_report(
        rep_name="Rayxon",
        rep_username="@RayxonJonbranding",
        report_text="3 ta mijozga qo'ng'iroq qildim",
        advice_text="Yaxshi natija, davom eting!",
        db_path=str(test_db),
    )
    assert ok is True

    conn = sqlite3.connect(test_db)
    row = conn.execute("SELECT user_id, report_type, content FROM team_reports").fetchone()
    conn.close()

    assert row[0] == "@RayxonJonbranding"
    assert row[1] == "hourly_checkin"
    assert "3 ta mijozga qo'ng'iroq qildim" in row[2]
    assert "Yaxshi natija" in row[2]


@pytest.mark.asyncio
async def test_generate_copilot_advice_hermes():
    with patch("src.services.core.ai.hermes_provider.get_hermes_provider") as mock_get_hermes:
        mock_hermes = MagicMock()
        mock_hermes.is_available.return_value = True
        mock_hermes.generate_response = AsyncMock(
            return_value="Rayxon, mijozga bunday tushuntiring: biz brending orqali savdoni oshiramiz."
        )
        mock_get_hermes.return_value = mock_hermes

        advice = await generate_copilot_advice("Rayxon", "Mijoz narx qimmat deyapti")
        assert "biz brending orqali" in advice


@pytest.mark.asyncio
async def test_generate_copilot_advice_fallback():
    with patch("src.services.core.ai.hermes_provider.get_hermes_provider") as mock_get_hermes, \
         patch("src.services.utils.free_ai_router.FreeAIProviderRouter") as mock_router_cls:
        
        mock_hermes = MagicMock()
        mock_hermes.is_available.return_value = False
        mock_get_hermes.return_value = mock_hermes

        mock_router = MagicMock()
        mock_router.get_text = AsyncMock(return_value=None)
        mock_router_cls.return_value = mock_router

        advice = await generate_copilot_advice("Rayxon", "Reja bo'yicha ketyapman")
        assert advice == DEFAULT_RULE_BASED_ADVICE


@pytest.mark.asyncio
async def test_handle_sales_staff_interaction_e2e(tmp_path):
    test_db = tmp_path / "test_bot.db"
    conn = sqlite3.connect(test_db)
    conn.execute(
        """
        CREATE TABLE team_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            report_date TEXT,
            report_type TEXT,
            content TEXT,
            status TEXT,
            created_at TEXT
        )
        """
    )
    conn.close()

    with patch("src.services.core.sales_staff_copilot.generate_copilot_advice", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = "Har bir mijozga individual yondashing."

        reply = await handle_sales_staff_interaction(
            rep_name="Rayxon",
            rep_username="@RayxonJonbranding",
            message_text="Hozir 2 ta yangi lidga xabar yozyapman",
            db_path=str(test_db),
        )

        assert "Sotuv Copilot (Oisha)" in reply
        assert "Har bir mijozga individual yondashing" in reply


def test_build_checkin_message():
    dt = datetime(2026, 10, 27, 11, 0)
    calls_info = {"total": 5, "answered": 3, "solid": 0, "total_talk_sec": 450}

    msg = build_checkin_message("Rayxon", "@RayxonJonbranding", dt, calls_info)
    assert "@RayxonJonbranding" in msg
    assert "Rayxon" in msg
    assert "5 ta raqam" in msg
    assert "3 tasi ko'tarilibdi" in msg
    assert "qanday yordam kerak" in msg


def test_is_work_hour():
    mon_11am = datetime(2026, 10, 26, 11, 0)  # Monday
    mon_8am = datetime(2026, 10, 26, 8, 0)
    mon_9pm = datetime(2026, 10, 26, 21, 0)
    sun_11am = datetime(2026, 10, 25, 11, 0)  # Sunday

    assert is_work_hour(mon_11am) is True
    assert is_work_hour(mon_8am) is False
    assert is_work_hour(mon_9pm) is False
    assert is_work_hour(sun_11am) is False


def test_format_duration():
    assert format_duration(45) == "45 soniya"
    assert format_duration(90) == "1 daqiqa 30 soniya"
    assert format_duration(3660) == "1 soat 1 daqiqa"


@pytest.mark.asyncio
async def test_bind_and_welcome_staff(tmp_path):
    from src.services.core.sales_staff_copilot import (
        bind_and_welcome_staff,
        get_known_staff_user_id,
        auto_resolve_staff_id,
        build_staff_intro_message,
    )

    test_bot_db = tmp_path / "bot.db"
    test_dialer_db = tmp_path / "dialer.db"

    conn = sqlite3.connect(test_bot_db)
    conn.execute(
        """
        CREATE TABLE users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            role TEXT,
            position TEXT,
            created_at TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE kv_settings (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at DATETIME
        )
        """
    )
    conn.close()

    conn_d = sqlite3.connect(test_dialer_db)
    conn_d.execute(
        """
        CREATE TABLE crm_seller_accounts (
            slug TEXT PRIMARY KEY,
            name TEXT,
            tg TEXT
        )
        """
    )
    conn_d.execute("INSERT INTO crm_seller_accounts VALUES ('rayxona', 'Rayxona', '')")
    conn_d.close()

    # First bind: must return True and welcome message
    is_new, intro = bind_and_welcome_staff(
        user_id=888777666,
        username="RayxonJonbranding",
        first_name="Rayxon",
        db_path=str(test_bot_db),
        dialer_db_path=str(test_dialer_db),
    )
    assert is_new is True
    assert "Tanishganimdan juda xursandman" in intro
    assert "888777666" in intro

    # Second bind with same ID: must return False (already introduced)
    is_new_again, intro_again = bind_and_welcome_staff(
        user_id=888777666,
        username="RayxonJonbranding",
        first_name="Rayxon",
        db_path=str(test_bot_db),
        dialer_db_path=str(test_dialer_db),
    )
    assert is_new_again is False
    assert intro_again == ""

    # Check known staff user_id
    known = get_known_staff_user_id("RayxonJonbranding", db_path=str(test_bot_db))
    assert known == 888777666

    # Test proactive resolution with mock Telethon client
    mock_client = MagicMock()
    mock_entity = MagicMock()
    mock_entity.id = 999111222
    mock_entity.first_name = "Rayxon"
    mock_client.get_entity = AsyncMock(return_value=mock_entity)

    # Empty new db for resolution test
    fresh_bot_db = tmp_path / "fresh_bot.db"
    conn_f = sqlite3.connect(fresh_bot_db)
    conn_f.execute("CREATE TABLE users (user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT, role TEXT, position TEXT, created_at TEXT)")
    conn_f.execute("CREATE TABLE kv_settings (key TEXT PRIMARY KEY, value TEXT, updated_at DATETIME)")
    conn_f.close()

    resolved_id = await auto_resolve_staff_id(client=mock_client, username="RayxonJonbranding", db_path=str(fresh_bot_db))
    assert resolved_id == 999111222


def test_can_dispatch_checkin_deduplication(tmp_path):
    from src.schedulers.remote_staff_checkin_scheduler import (
        can_dispatch_checkin,
        save_checkin_dispatch,
        get_checkin_state,
    )

    test_bot_db = tmp_path / "dedup_bot.db"
    conn = sqlite3.connect(test_bot_db)
    conn.execute(
        """
        CREATE TABLE kv_settings (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at DATETIME
        )
        """
    )
    conn.close()

    test_state_file = str(tmp_path / "checkin_state.json")
    now = datetime(2026, 10, 27, 11, 16)
    msg_text = "Oxirgi bir soatda 7 ta raqam tergansiz..."

    # 1. First dispatch: should be allowed
    can_send, reason = can_dispatch_checkin(now, msg_text, db_path=str(test_bot_db), state_file=test_state_file)
    assert can_send is True
    assert reason == "ok"

    # Simulate dispatch record saved
    import hashlib
    text_hash = hashlib.sha256(msg_text.strip().encode("utf-8")).hexdigest()
    save_checkin_dispatch("2026-10-27-11", int(now.timestamp()), text_hash, db_path=str(test_bot_db), state_file=test_state_file)

    # 2. Second dispatch 1 minute later (at 11:17): MUST BE BLOCKED!
    now_next_min = datetime(2026, 10, 27, 11, 17)
    can_send_dup, reason_dup = can_dispatch_checkin(now_next_min, msg_text, db_path=str(test_bot_db), state_file=test_state_file)
    assert can_send_dup is False
    assert "already_sent_this_hour" in reason_dup

    # 3. Third dispatch in next hour (12:05) with identical text: MUST BE BLOCKED by duplicate content check!
    # ("bitta narsani ketma ket ikki marta yubormasin")
    now_next_hour = datetime(2026, 10, 27, 12, 5)
    can_send_same_text, reason_same = can_dispatch_checkin(now_next_hour, msg_text, db_path=str(test_bot_db), state_file=test_state_file)
    assert can_send_same_text is False
    assert reason_same == "duplicate_identical_content"

    # 4. Third dispatch in next hour (12:05) with FRESH new text: ALLOWED!
    fresh_msg = "Yangi soat: 10 ta raqam tergansiz..."
    can_send_fresh, reason_fresh = can_dispatch_checkin(now_next_hour, fresh_msg, db_path=str(test_bot_db), state_file=test_state_file)
    assert can_send_fresh is True
    assert reason_fresh == "ok"

    # 5. Forced dispatch always allowed
    can_send_forced, reason_forced = can_dispatch_checkin(now_next_min, msg_text, force=True, db_path=str(test_bot_db), state_file=test_state_file)
    assert can_send_forced is True
    assert reason_forced == "forced"


@pytest.mark.asyncio
async def test_generate_copilot_advice_free_router_generate_text():
    from src.services.utils.free_ai_router import ProviderResult

    with patch("src.services.core.ai.hermes_provider.get_hermes_provider") as mock_get_hermes, \
         patch("src.services.utils.free_ai_router.FreeAIProviderRouter") as mock_router_cls:
        mock_hermes = MagicMock()
        mock_hermes.is_available.return_value = False
        mock_get_hermes.return_value = mock_hermes

        mock_router = MagicMock()
        mock_router.generate_text = AsyncMock(
            return_value=ProviderResult(
                text="Mumtozmaxal, mijozga ROI hisob-kitobini ko'rsating va uchrashuv belgilang.",
                provider="gemini",
                model="gemini-2.5-flash",
            )
        )
        mock_router_cls.return_value = mock_router

        advice = await generate_copilot_advice("Mumtozmaxal", "Mijoz o'ylab ko'raman dedi")
        assert "ROI hisob-kitobini" in advice


def test_dynamic_staff_checkin_and_bind(tmp_path):
    from src.services.core.sales_staff_copilot import bind_and_welcome_staff, get_known_staff_user_id

    test_bot_db = tmp_path / "bot_dyn.db"
    test_dialer_db = tmp_path / "dialer_dyn.db"

    conn = sqlite3.connect(test_bot_db)
    conn.execute("CREATE TABLE users (user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT, role TEXT, position TEXT, created_at TEXT)")
    conn.execute("CREATE TABLE kv_settings (key TEXT PRIMARY KEY, value TEXT, updated_at DATETIME)")
    conn.close()

    conn_d = sqlite3.connect(test_dialer_db)
    conn_d.execute("CREATE TABLE crm_seller_accounts (slug TEXT PRIMARY KEY, name TEXT, tg TEXT)")
    conn_d.execute("INSERT INTO crm_seller_accounts VALUES ('mumtozmaxal', 'Mumtozmaxal', '@Mumtoz_Jon')")
    conn_d.close()

    is_new, intro = bind_and_welcome_staff(
        user_id=555444333,
        username="Mumtoz_Jon",
        first_name="Mumtozmaxal",
        db_path=str(test_bot_db),
        dialer_db_path=str(test_dialer_db),
    )
    assert is_new is True
    assert "Mumtozmaxal" in intro
    assert get_known_staff_user_id("Mumtoz_Jon", db_path=str(test_bot_db)) == 555444333
