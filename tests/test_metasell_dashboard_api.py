"""Tests for Oisha-OS Cockpit Aggregator API."""
import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from src.api.routes.metasell_dashboard import router


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(router, prefix="/api/dashboard")
    return TestClient(app)


def test_executive_dashboard_payload(client):
    response = client.get("/api/dashboard/metasell-executive")
    assert response.status_code == 200
    data = response.json()

    assert "hero" in data
    assert "speed_to_lead" in data
    assert "stuck_deals" in data
    assert "ad_attribution" in data
    assert "attention" in data
    assert "team_leaderboard" in data

    # Check Hero structure
    hero = data["hero"]
    assert "sales_won_amount" in hero
    assert "conversion_rate_pct" in hero
    assert "top_loss_reason" in hero

    # Check Speed to Lead structure
    stl = data["speed_to_lead"]
    assert "buckets" in stl
    assert "within_30m" in stl["buckets"]
    assert "sla_rate_pct" in stl

    # Check Stuck Deals structure
    stuck = data["stuck_deals"]
    assert "total_stuck_deals" in stuck
    assert "total_stuck_value" in stuck


def test_metasell_console_html(client):
    response = client.get("/api/dashboard/metasell-console")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Oisha-OS" in response.text
    assert "Jon Branding" in response.text
    assert "AI Simulyator" in response.text

    # Also test /oisha-console alias
    res_oisha = client.get("/api/dashboard/oisha-console")
    assert res_oisha.status_code == 200


def test_simulator_endpoints(client):
    # Test GET scenarios
    res_scenarios = client.get("/api/dashboard/simulator/scenarios")
    assert res_scenarios.status_code == 200
    scenarios = res_scenarios.json()
    assert len(scenarios) >= 5

    # Test POST turn
    payload = {
        "scenario_id": "first_30_seconds",
        "manager_message": "Assalomu alaykum, kechagi arizangiz boʻyicha qachon qulay vaqtda gaplashsak boʻladi?",
    }
    res_turn = client.post("/api/dashboard/simulator/turn", json=payload)
    assert res_turn.status_code == 200
    turn_data = res_turn.json()
    assert "client_response" in turn_data
    assert "coaching_tip" in turn_data


def test_simulator_voice_turn(client):
    # Test POST voice-turn
    payload = {
        "scenario_id": "first_30_seconds",
        "manager_text": "Salom Kamola opa, loyiha tafsilotlarini 1 daqiqada aytib bersam maylimi?",
    }
    res_voice = client.post("/api/dashboard/simulator/voice-turn", json=payload)
    assert res_voice.status_code == 200
    voice_data = res_voice.json()
    assert "manager_transcript" in voice_data
    assert "client_response_text" in voice_data
    assert "client_audio_base64" in voice_data
    assert voice_data["client_name"] == "Kamola"
    assert voice_data["audio_mime"] == "audio/wav"


def test_webrtc_session_and_sms_endpoints(client):
    # Test GET WebRTC session
    res_webrtc = client.get("/api/dashboard/telephony/webrtc-session?manager_id=mgr_aziz&extension=101")
    assert res_webrtc.status_code == 200
    webrtc_data = res_webrtc.json()
    assert webrtc_data["manager_id"] == "mgr_aziz"
    assert webrtc_data["extension"] == "101"
    assert "wss://" in webrtc_data["websocket_url"]

    # Test POST SMS dispatch
    sms_payload = {
        "phone": "+998901234567",
        "message": "Assalomu alaykum, sizning soʻrovingiz qabul qilindi.",
    }
    res_sms = client.post("/api/dashboard/sms/dispatch", json=sms_payload)
    assert res_sms.status_code == 200
    sms_data = res_sms.json()
    assert sms_data["provider"] in ["oisha_gsm", "eskiz"]
    assert sms_data["status"] in ["delivered", "sent"]


def test_quiz_endpoints(client):
    # Test GET questions
    res_q = client.get("/api/dashboard/quiz/questions")
    assert res_q.status_code == 200
    questions = res_q.json()
    assert len(questions) >= 6

    # Test POST submit
    first_q = questions[0]
    sub_payload = {
        "user_id": "manager_777",
        "answers": {first_q["question_id"]: first_q["correct_option"]},
    }
    res_sub = client.post("/api/dashboard/quiz/submit", json=sub_payload)
    assert res_sub.status_code == 200
    res_data = res_sub.json()
    assert "score_pct" in res_data
    assert "feedback" in res_data
