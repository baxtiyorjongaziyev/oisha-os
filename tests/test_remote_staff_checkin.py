from __future__ import annotations

from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch

import pytest

from src.schedulers.remote_staff_checkin_scheduler import (
    build_checkin_message,
    format_duration,
    format_phone,
    get_target_destination,
    is_work_hour,
    send_remote_checkin,
)

TASHKENT = timezone(timedelta(hours=5))


def test_format_phone():
    assert format_phone("972624100") == "+998 (97) 262-41-00"
    assert format_phone("+998911881199") == "+998 (91) 188-11-99"
    assert format_phone("invalid") == "invalid"


def test_format_duration():
    assert format_duration(0) == "0 soniya"
    assert format_duration(45) == "45 soniya"
    assert format_duration(150) == "2 daqiqa 30 soniya"
    assert format_duration(3600) == "1 soat 0 daqiqa"


def test_is_work_hour():
    tue_work = datetime(2026, 10, 27, 11, 30, tzinfo=TASHKENT)
    assert is_work_hour(tue_work) is True

    tue_early = datetime(2026, 10, 27, 8, 30, tzinfo=TASHKENT)
    assert is_work_hour(tue_early) is False

    tue_late = datetime(2026, 10, 27, 21, 0, tzinfo=TASHKENT)
    assert is_work_hour(tue_late) is False

    sun = datetime(2026, 10, 25, 14, 0, tzinfo=TASHKENT)
    assert is_work_hour(sun) is False


def test_build_checkin_message_no_calls():
    now = datetime(2026, 10, 27, 11, 0, tzinfo=TASHKENT)
    msg = build_checkin_message("Rayxon", "@RayxonJonbranding", now, activity=None)
    assert "@RayxonJonbranding" in msg
    assert "Assalomu alaykum Rayxon" in msg
    assert "⚡ Soatlik Check-in:" not in msg  # No robotic header
    assert "yangi qo'ng'iroq ko'rinmadi" in msg


def test_build_checkin_message_with_short_answered_calls():
    now = datetime(2026, 10, 27, 11, 0, tzinfo=TASHKENT)
    activity = {
        "total": 7,
        "answered": 2,
        "missed": 5,
        "solid": 0,
        "total_talk_sec": 55,
        "answered_clients": [
            {"number": "900054551", "name": "", "duration": 30},
            {"number": "+998995331998", "name": "", "duration": 25},
        ],
    }
    msg = build_checkin_message("Rayxon", "@RayxonJonbranding", now, activity=activity)
    assert "7 ta raqam tergansiz" in msg
    assert "2 tasi ko'tarilibdi" in msg
    assert "+998 (90) 005-45-51" in msg
    assert "suhbatlar juda qisqa bo'libdi" in msg
    assert "⚡" not in msg
    assert "1️⃣" not in msg


def test_build_checkin_message_with_solid_calls():
    now = datetime(2026, 10, 27, 11, 0, tzinfo=TASHKENT)
    activity = {
        "total": 8,
        "answered": 3,
        "missed": 5,
        "solid": 1,
        "total_talk_sec": 320,
        "answered_clients": [
            {"number": "+998901234567", "name": "Akbar aka", "duration": 240},
        ],
    }
    msg = build_checkin_message("Rayxon", "@RayxonJonbranding", now, activity=activity)
    assert "sifatli gaplashibsiz" in msg
    assert "Akbar aka" in msg
    assert "⚡" not in msg


def test_build_checkin_message_all_missed():
    now = datetime(2026, 10, 27, 11, 0, tzinfo=TASHKENT)
    activity = {
        "total": 5,
        "answered": 0,
        "missed": 5,
        "solid": 0,
        "total_talk_sec": 0,
        "answered_clients": [],
    }
    msg = build_checkin_message("Rayxon", "@RayxonJonbranding", now, activity=activity)
    assert "5 ta raqam terilganini ko'rdim" in msg
    assert "hech biri ko'tarmabdi" in msg


def test_target_destination_defaults(monkeypatch):
    monkeypatch.delenv("REMOTE_CHECKIN_GROUP_ID", raising=False)
    monkeypatch.delenv("REMOTE_CHECKIN_TOPIC_ID", raising=False)
    chat_id, topic_id = get_target_destination()
    assert chat_id == -1003854308552
    assert topic_id == 115


def test_target_destination_override(monkeypatch):
    monkeypatch.setenv("REMOTE_CHECKIN_GROUP_ID", "-100999999999")
    monkeypatch.setenv("REMOTE_CHECKIN_TOPIC_ID", "42")
    chat_id, topic_id = get_target_destination()
    assert chat_id == -100999999999
    assert topic_id == 42


@pytest.mark.asyncio
async def test_send_remote_checkin_work_hours():
    now = datetime(2026, 10, 27, 11, 0, tzinfo=TASHKENT)
    bot = AsyncMock()
    bot.send_message = AsyncMock()

    with patch("src.schedulers.remote_staff_checkin_scheduler.fetch_recent_calls_for_rep", return_value={"total": 3, "answered": 1, "missed": 2, "solid": 0, "total_talk_sec": 40, "answered_clients": []}), \
         patch("src.schedulers.remote_staff_checkin_scheduler.can_dispatch_checkin", return_value=(True, "ok")), \
         patch("src.schedulers.remote_staff_checkin_scheduler.save_checkin_dispatch"):
        success = await send_remote_checkin(
            bot,
            now_fn=lambda: now,
            seller_name="Rayxon",
            tg_handle="@RayxonJonbranding",
        )

    assert success is True
    bot.send_message.assert_called_once()
    args, kwargs = bot.send_message.call_args
    assert args[0] == -1003854308552
    assert "@RayxonJonbranding" in args[1]
    assert kwargs.get("message_thread_id") == 115
    assert kwargs.get("parse_mode") == "HTML"
