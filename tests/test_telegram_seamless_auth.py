"""Tests for seamless Telegram web authentication (Deep Link + OTP fallback)."""
from unittest.mock import AsyncMock, MagicMock
import pytest
from fastapi.testclient import TestClient

from src.api.web_auth_store import create_tg_login_state, issue_tg_otp_code, poll_tg_login_state
from src.services.api_server.core import app
from src.services.core.dispatcher.handlers_web_auth import (
    _UNAUTHORIZED_MSG,
    _APPROVED_MSG,
    _STATE_EXPIRED_MSG,
    handle_start_weblogin,
    handle_login_otp,
)


@pytest.fixture
def client():
    return TestClient(app)


def test_telegram_login_page_renders_deep_link(client):
    res = client.get("/api/auth/telegram/login")
    assert res.status_code == 200
    assert "text/html" in res.headers.get("content-type", "")
    assert "start=login_" in res.text
    assert "/api/auth/telegram/poll?state=" in res.text
    assert "/api/auth/telegram/otp" in res.text


def test_telegram_poll_pending_and_expired(client):
    # Pending state
    state = create_tg_login_state(next_url="/api/marketing/capi/console", ttl=60)
    res = client.get(f"/api/auth/telegram/poll?state={state}")
    assert res.status_code == 200
    assert res.json().get("status") == "pending"

    # Non-existent or expired state
    res_expired = client.get("/api/auth/telegram/poll?state=non_existent_token_xyz")
    assert res_expired.status_code == 200
    assert res_expired.json().get("status") == "expired"


def test_telegram_poll_approved_sets_cookie(client, monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "test-dedicated-jwt-secret-at-least-32-bytes-long!")
    state = create_tg_login_state(next_url="/api/marketing/capi/console", ttl=60)

    # Approve state
    from src.api.web_auth_store import approve_tg_login_state
    approve_tg_login_state(state, user_id=1234567, username="baxtiyor", first_name="Baxtiyor", role="owner")

    res = client.get(f"/api/auth/telegram/poll?state={state}")
    assert res.status_code == 200
    data = res.json()
    assert data.get("status") == "approved"
    assert data.get("redirect_url") == "/api/marketing/capi/console"
    assert "oisha_token=" in res.headers.get("set-cookie", "")


def test_telegram_otp_login_flow(client, monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "test-dedicated-jwt-secret-at-least-32-bytes-long!")

    # 1. Issue OTP code
    code = issue_tg_otp_code(user_id=1234567, username="baxtiyor", first_name="Baxtiyor", role="owner", next_url="/capi")
    assert len(code) == 6

    # 2. Invalid code rejects
    res_bad = client.post("/api/auth/telegram/otp", data={"otp": "000000"}, follow_redirects=False)
    assert res_bad.status_code == 401

    # 3. Valid code logs in and redirects
    res = client.post("/api/auth/telegram/otp", data={"otp": code, "next": "/capi"}, follow_redirects=False)
    assert res.status_code == 303
    assert res.headers.get("location") == "/capi"
    assert "oisha_token=" in res.headers.get("set-cookie", "")

    # 4. OTP is one-time use; second attempt fails
    res_reuse = client.post("/api/auth/telegram/otp", data={"otp": code}, follow_redirects=False)
    assert res_reuse.status_code == 401


@pytest.mark.asyncio
async def test_bot_start_weblogin_unauthorized(monkeypatch):
    monkeypatch.setattr("src.settings.settings.OWNER_ID", 999999)
    monkeypatch.setattr("src.settings.settings.WHITELIST_IDS", [888888])

    msg = MagicMock()
    msg.from_user.id = 111111  # Not owner, not whitelist
    msg.from_user.username = "intruder"
    msg.from_user.first_name = "Intruder"
    msg.answer = AsyncMock()

    await handle_start_weblogin(msg, state_token="some_state")
    msg.answer.assert_called_once_with(_UNAUTHORIZED_MSG)


@pytest.mark.asyncio
async def test_bot_start_weblogin_authorized_owner(monkeypatch):
    monkeypatch.setattr("src.settings.settings.OWNER_ID", 555555)

    state = create_tg_login_state(next_url="/", ttl=60)

    msg = MagicMock()
    msg.from_user.id = 555555
    msg.from_user.username = "owner_baxtiyor"
    msg.from_user.first_name = "Baxtiyor"
    msg.answer = AsyncMock()

    await handle_start_weblogin(msg, state_token=f"login_{state}")
    msg.answer.assert_called_once_with(_APPROVED_MSG)

    # State in DB is now approved
    state_data = poll_tg_login_state(state)
    assert state_data is not None
    assert state_data.get("role") == "owner"


@pytest.mark.asyncio
async def test_bot_login_otp_authorized_whitelist(monkeypatch):
    monkeypatch.setattr("src.settings.settings.OWNER_ID", 111111)
    monkeypatch.setattr("src.settings.settings.WHITELIST_IDS", [222222])

    msg = MagicMock()
    msg.from_user.id = 222222  # in whitelist
    msg.from_user.username = "team_lead"
    msg.from_user.first_name = "Lead"
    msg.answer = AsyncMock()

    await handle_login_otp(msg)
    assert msg.answer.call_count == 1
    call_args = msg.answer.call_args[0][0]
    assert "Oisha-OS tizimiga bir martalik kirish kodingiz" in call_args
    assert "<code>" in call_args
