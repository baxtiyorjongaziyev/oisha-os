"""Unit tests for Oisha-OS Cockpit Full Capabilities.

Guards:
- LiveDataBridge DB connectivity and fallback data models.
- Telegram Bot WebApp menu buttons and set_chat_menu_button helper.
- Executive command center analytical dashboard calculation.
- AI Sales Simulator text dialogue and neural voice generation (TTS/STT).
- Native in-house WebRTC softphone and GSM SMS gateway dispatch.
- Utel and OnlinePBX incoming call webhook adapters.
"""
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.handlers.metasell_menu import (
    build_metasell_menu_keyboard,
    build_telethon_cockpit_buttons,
    configure_telegram_menu_button,
)
from src.services.api_server.core import app
from src.services.command_center.live_db_bridge import LiveDataBridge

client = TestClient(app)


@pytest.mark.asyncio
async def test_live_db_bridge_fallback_and_records():
    """Verify LiveDataBridge falls back gracefully to baseline sets when DB is empty."""
    bridge = LiveDataBridge(db_connection=None)

    deals = await bridge.fetch_active_deal_records()
    assert len(deals) >= 2
    assert any(d.deal_id == "deal_live_1" for d in deals)
    assert deals[0].entered_stage_at.tzinfo is not None

    interactions = await bridge.fetch_recent_lead_interactions()
    assert len(interactions) >= 3
    assert any(i.channel == "telegram" for i in interactions)

    campaigns, leads = await bridge.fetch_ad_attribution_data()
    assert len(campaigns) >= 1
    assert len(leads) >= 4
    assert campaigns[0].spend > 0


@pytest.mark.asyncio
async def test_telegram_menu_button_configuration():
    """Test configure_telegram_menu_button dispatches correct Telegram API payload."""
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_response = MagicMock(status_code=200)
        mock_response.json.return_value = {"ok": True, "result": True}
        mock_post.return_value = mock_response

        ok = await configure_telegram_menu_button(
            bot_token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
            webapp_url="https://oisha.jonbranding.uz",
        )
        assert ok is True
        mock_post.assert_called_once()
        _args, kwargs = mock_post.call_args
        payload = kwargs.get("json", {})
        assert payload.get("menu_button", {}).get("type") == "web_app"
        assert "metasell-console" in payload.get("menu_button", {}).get("web_app", {}).get("url")


def test_telethon_and_webapp_keyboards():
    """Verify Telethon buttons and Telegram InlineKeyboardMarkup generation."""
    telethon_btns = build_telethon_cockpit_buttons("https://oisha.jonbranding.uz")
    assert len(telethon_btns) == 2
    assert "Mini App" in telethon_btns[0][0].text

    markup = build_metasell_menu_keyboard(is_owner=True)
    assert len(markup.inline_keyboard) >= 3
    first_btn = markup.inline_keyboard[0][0]
    assert first_btn.web_app is not None
    assert "metasell-console" in first_btn.web_app.url


def test_api_html_console_endpoints():
    """Verify cockpit HTML endpoints render without authentication blocks."""
    resp1 = client.get("/metasell-console")
    assert resp1.status_code == 200
    assert "Oisha" in resp1.text

    resp2 = client.get("/cockpit")
    assert resp2.status_code == 200

    resp3 = client.get("/oisha-console")
    assert resp3.status_code == 200


def test_api_metasell_executive_dashboard():
    """Verify live executive analytics payload returns complete metric dimensions."""
    resp = client.get("/api/dashboard/metasell-executive")
    assert resp.status_code == 200
    data = resp.json()

    assert "hero" in data
    assert "speed_to_lead" in data
    assert "stuck_deals" in data
    assert "ad_attribution" in data
    assert data["speed_to_lead"]["sla_rate_pct"] >= 0.0
    assert data["stuck_deals"]["total_stuck_deals"] >= 0


def test_api_sales_simulator_text_and_voice():
    """Verify sales simulator scenarios, text turns, and voice synthesis endpoints."""
    # List scenarios
    scenarios_resp = client.get("/api/dashboard/simulator/scenarios")
    assert scenarios_resp.status_code == 200
    scenarios = scenarios_resp.json()
    assert len(scenarios) >= 1
    sc_id = scenarios[0]["scenario_id"]

    # Text turn
    turn_resp = client.post(
        "/api/dashboard/simulator/turn",
        json={
            "scenario_id": sc_id,
            "manager_message": "Assalomu alaykum! Biznesingizga qanday natija kerak?",
            "history": [],
        },
    )
    assert turn_resp.status_code == 200
    turn_data = turn_resp.json()
    assert "client_response" in turn_data
    assert "coaching_tip" in turn_data

    # Voice turn
    voice_resp = client.post(
        "/api/dashboard/simulator/voice-turn",
        json={
            "scenario_id": sc_id,
            "manager_text": "Narx boʻyicha kelisha olamizmi?",
            "history": [],
        },
    )
    assert voice_resp.status_code == 200
    voice_data = voice_resp.json()
    assert voice_data.get("client_audio_base64") is not None
    assert voice_data.get("audio_mime") == "audio/wav"
    assert "client_response_text" in voice_data


def test_api_telephony_webhooks_and_gateways():
    """Verify Utel, OnlinePBX, Native WebRTC softphone and GSM SMS endpoints."""
    # WebRTC credentials
    rtc_resp = client.get("/api/dashboard/telephony/webrtc-session?manager_id=mgr_aziz&extension=101")
    assert rtc_resp.status_code == 200
    assert "websocket_url" in rtc_resp.json()
    assert "session_token" in rtc_resp.json()

    # SMS dispatch
    sms_resp = client.post(
        "/api/dashboard/sms/dispatch",
        json={"phone": "+998901234567", "message": "Hurmatli mijoz, buyurtmangiz qabul qilindi."},
    )
    assert sms_resp.status_code == 200
    assert sms_resp.json()["status"] in ("sent", "delivered")

    # Utel webhook
    utel_resp = client.post(
        "/telephony/webhook/utel",
        json={"call_id": "utel_call_99", "event": "call_answer", "caller": "+998901112233"},
    )
    assert utel_resp.status_code == 200
    assert utel_resp.json()["call_id"] == "utel_call_99"

    # OnlinePBX webhook
    opbx_resp = client.post(
        "/telephony/webhook/onlinepbx",
        json={"uuid": "opbx_call_88", "event": "HANGUP", "caller_id": "+998904445566"},
    )
    assert opbx_resp.status_code == 200
    assert opbx_resp.json()["call_id"] == "opbx_call_88"


def test_api_quiz_and_morning_tasks():
    """Verify knowledge quiz grading and morning task triage endpoints."""
    # Quiz questions
    quiz_q = client.get("/api/dashboard/quiz/questions")
    assert quiz_q.status_code == 200
    questions = quiz_q.json()
    assert len(questions) >= 1

    # Quiz submit
    first_q = questions[0]["question_id"]
    submit_resp = client.post(
        "/api/dashboard/quiz/submit",
        json={"user_id": "usr_test", "answers": {first_q: "A"}},
    )
    assert submit_resp.status_code == 200
    assert "score_pct" in submit_resp.json()

    # Morning tasks
    tasks_resp = client.get("/api/dashboard/morning-tasks")
    assert tasks_resp.status_code == 200
    assert "today_count" in tasks_resp.json()
    assert "overdue_count" in tasks_resp.json()
