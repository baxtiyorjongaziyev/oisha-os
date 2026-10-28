from __future__ import annotations

from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch

import pytest

from src.schedulers.remote_staff_checkin_scheduler import (
    _analysis_summary,
    build_checkin_message,
    fetch_call_summaries,
    format_duration,
    format_phone,
    get_reps,
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
    assert "Assalomu alaykum, Rayxon" in msg
    assert "⚡ Soatlik Check-in:" not in msg  # No robotic header
    assert "qo'ng'iroq ko'rinmadi" in msg


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
    assert "7 ta raqam terdingiz" in msg
    assert "2 tasi ko'tardi" in msg
    assert "+998 (90) 005-45-51" in msg
    assert "reply qilib yozing" in msg
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
    assert "yaxshi gaplashibsiz" in msg
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
    assert "5 ta raqam terdingiz" in msg
    assert "hech kim ko'tarmadi" in msg


def test_target_destination_defaults(monkeypatch):
    monkeypatch.delenv("REMOTE_CHECKIN_GROUP_ID", raising=False)
    monkeypatch.delenv("REMOTE_CHECKIN_TOPIC_ID", raising=False)
    chat_id, topic_id = get_target_destination()
    assert chat_id == -1003854308552
    assert topic_id == 2976


def test_target_destination_override(monkeypatch):
    monkeypatch.setenv("REMOTE_CHECKIN_GROUP_ID", "-100999999999")
    monkeypatch.setenv("REMOTE_CHECKIN_TOPIC_ID", "42")
    chat_id, topic_id = get_target_destination()
    assert chat_id == -100999999999
    assert topic_id == 42


@pytest.mark.asyncio
async def test_send_remote_checkin_work_hours(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # dedup state (data/checkin_state.json) testlar orasida qolmasin
    (tmp_path / "data").mkdir()
    now = datetime(2026, 10, 27, 11, 0, tzinfo=TASHKENT)
    bot = AsyncMock()
    bot.send_message = AsyncMock()

    with patch("src.schedulers.remote_staff_checkin_scheduler.fetch_recent_calls_for_rep", return_value={"total": 3, "answered": 1, "missed": 2, "solid": 0, "total_talk_sec": 40, "answered_clients": []}):
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
    assert kwargs.get("message_thread_id") == 2976
    assert kwargs.get("parse_mode") == "HTML"


def test_default_reps_have_own_topics(monkeypatch):
    monkeypatch.delenv("REMOTE_CHECKIN_REPS", raising=False)
    topics = {r["key"]: r["topic"] for r in get_reps()}
    assert topics == {"rayxon": 2976, "mumtozmaxal": 120, "shahnoza": 122}


def test_analysis_summary_takes_first_content_line():
    note = "[AI_CALL_ANALYSIS] Oisha AI 360° tahlil natijasi\n\nMijoz logo narxini so'radi, ertaga javob beradi.\n\nSifat bahosi: 7"
    assert _analysis_summary(note) == "Mijoz logo narxini so'radi, ertaga javob beradi."


@pytest.mark.asyncio
async def test_fetch_call_summaries_reads_amocrm_analysis():
    amocrm = AsyncMock()
    amocrm.search_leads = AsyncMock(return_value=[{"id": 7}])
    amocrm.get_lead_notes = AsyncMock(return_value=[
        {"params": {"text": "oddiy izoh"}},
        {"params": {"text": "[AI_CALL_ANALYSIS] sarlavha\n\nTo'lovni juma kuni qiladi."}},
    ])
    clients = [{"number": "+998 90 123-45-67", "name": "", "duration": 200}]
    assert await fetch_call_summaries(clients, amocrm=amocrm) == ["To'lovni juma kuni qiladi."]
    amocrm.search_leads.assert_awaited_once_with("998901234567", limit=1)


@pytest.mark.asyncio
async def test_send_checkin_other_rep_goes_to_own_topic_and_state(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data").mkdir()
    monkeypatch.delenv("REMOTE_CHECKIN_TOPIC_ID", raising=False)
    now = datetime(2026, 10, 27, 12, 0, tzinfo=TASHKENT)
    bot = AsyncMock()
    activity = {"total": 2, "answered": 0, "missed": 2, "solid": 0, "total_talk_sec": 0, "answered_clients": []}

    with patch("src.schedulers.remote_staff_checkin_scheduler.fetch_recent_calls_for_rep", return_value=activity):
        rayxon_ok = await send_remote_checkin(bot, now_fn=lambda: now)
        shahnoza_ok = await send_remote_checkin(
            bot, now_fn=lambda: now, seller_name="Shahnoza", tg_handle="",
            rep_emails=["shahnoza@jonbranding.uz"], rep_key="shahnoza", topic_id=122,
        )

    # Rayxon yuborgani Shahnozani shu soatda bloklamaydi (alohida holat).
    assert rayxon_ok is True and shahnoza_ok is True
    topics = [c.kwargs.get("message_thread_id") for c in bot.send_message.call_args_list]
    assert topics == [2976, 122]
    shahnoza_text = bot.send_message.call_args_list[1].args[1]
    assert shahnoza_text.startswith("Assalomu alaykum, Shahnoza!") or "Shahnoza" in shahnoza_text
    assert "()" not in shahnoza_text
    assert (tmp_path / "data" / "checkin_state_shahnoza.json").exists()
