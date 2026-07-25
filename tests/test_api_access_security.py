import time

import jwt
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from starlette.requests import Request
from starlette.responses import Response

from src.api import auth_service
from src.api.routes.telegram_mcp import _require_internal_secret
from src.api.security import ApiAccessMiddleware, authorize_request_values


def test_api_access_fails_closed_without_any_credential():
    result = authorize_request_values(
        authorization="",
        api_secret="",
        proxy_user="",
        client_host="203.0.113.10",
        session_token="",
        jwt_secret="",
    )

    assert result is None


def test_external_client_cannot_spoof_proxy_user_header():
    result = authorize_request_values(
        authorization="",
        api_secret="",
        proxy_user="admin",
        client_host="203.0.113.10",
        session_token="",
        jwt_secret="",
    )

    assert result is None


def test_loopback_nginx_proxy_identity_is_accepted():
    result = authorize_request_values(
        authorization="",
        api_secret="",
        proxy_user="admin",
        client_host="127.0.0.1",
        session_token="",
        jwt_secret="",
    )

    assert result == {"auth_type": "trusted_proxy", "role": "admin", "subject": "admin"}


def test_exact_bearer_secret_is_accepted():
    result = authorize_request_values(
        authorization="Bearer correct-secret",
        api_secret="correct-secret",
        proxy_user="",
        client_host="203.0.113.10",
        session_token="",
        jwt_secret="",
    )

    assert result == {"auth_type": "bearer", "role": "owner", "subject": "api-secret"}


def test_wrong_bearer_secret_is_rejected():
    result = authorize_request_values(
        authorization="Bearer wrong-secret",
        api_secret="correct-secret",
        proxy_user="",
        client_host="203.0.113.10",
        session_token="",
        jwt_secret="",
    )

    assert result is None


def test_owner_session_is_accepted_but_client_session_is_rejected():
    secret = "dedicated-jwt-secret"
    owner_token = jwt.encode(
        {"sub": "1", "role": "owner", "exp": int(time.time()) + 60},
        secret,
        algorithm="HS256",
    )
    client_token = jwt.encode(
        {"sub": "2", "role": "client", "exp": int(time.time()) + 60},
        secret,
        algorithm="HS256",
    )

    owner = authorize_request_values(
        authorization="",
        api_secret="",
        proxy_user="",
        client_host="203.0.113.10",
        session_token=owner_token,
        jwt_secret=secret,
    )
    client = authorize_request_values(
        authorization="",
        api_secret="",
        proxy_user="",
        client_host="203.0.113.10",
        session_token=client_token,
        jwt_secret=secret,
    )

    assert owner == {"auth_type": "session", "role": "owner", "subject": "1"}
    assert client is None


def test_session_is_rejected_when_session_secret_is_missing():
    token = jwt.encode(
        {"sub": "1", "role": "owner", "exp": int(time.time()) + 60},
        "bot-token-must-not-be-a-fallback",
        algorithm="HS256",
    )

    result = authorize_request_values(
        authorization="",
        api_secret="",
        proxy_user="",
        client_host="203.0.113.10",
        session_token=token,
        jwt_secret="",
    )

    assert result is None


def _middleware_test_client(monkeypatch):
    monkeypatch.setenv("OISHA_API_SECRET", "correct-secret")
    monkeypatch.delenv("JWT_SECRET", raising=False)
    app = FastAPI()
    app.add_middleware(ApiAccessMiddleware)

    @app.get("/api/private")
    async def private_route():
        return {"ok": True}

    @app.get("/healthz")
    async def health_route():
        return {"status": "ok"}

    @app.get("/api/auth/telegram/callback")
    async def callback_route():
        response = Response(status_code=302)
        response.set_cookie("oisha_token", "signed-session", httponly=True)
        return response

    return TestClient(app)


def test_private_api_is_blocked_without_auth(monkeypatch):
    client = _middleware_test_client(monkeypatch)

    response = client.get("/api/private")

    assert response.status_code == 401


def test_private_api_accepts_exact_bearer_secret(monkeypatch):
    client = _middleware_test_client(monkeypatch)

    response = client.get(
        "/api/private", headers={"Authorization": "Bearer correct-secret"}
    )

    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_health_and_oauth_callback_remain_public(monkeypatch):
    client = _middleware_test_client(monkeypatch)

    assert client.get("/healthz").status_code == 200
    assert client.get("/api/auth/telegram/callback").status_code == 302


def test_session_cookie_is_forced_secure(monkeypatch):
    client = _middleware_test_client(monkeypatch)

    response = client.get("/api/auth/telegram/callback")
    cookie = response.headers["set-cookie"].lower()

    assert "secure" in cookie
    assert "httponly" in cookie


def test_telegram_profile_claims_are_escaped_before_html_rendering():
    token = auth_service.issue_session_jwt(
        user_id=1,
        username='bad"><script>alert(1)</script>',
        first_name='<img src=x onerror=alert(1)>',
        role='admin";alert(1);//',
        secret="dedicated-secret",
    )

    payload = auth_service.decode_session_jwt(token, "dedicated-secret")

    assert payload is not None
    assert "<" not in payload["first_name"]
    assert "<" not in payload["username"]
    assert payload["role"] == "client"


def test_internal_mcp_denies_access_when_secret_is_unconfigured(monkeypatch):
    monkeypatch.delenv("OISHA_API_SECRET", raising=False)
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/internal/mcp/dialogs",
            "headers": [],
            "client": ("127.0.0.1", 12345),
        }
    )

    with pytest.raises(HTTPException) as exc_info:
        _require_internal_secret(request)

    assert exc_info.value.status_code == 503


def test_config_session_secret_never_falls_back_to_bot_token(monkeypatch):
    from src import config

    monkeypatch.delenv("JWT_SECRET", raising=False)
    monkeypatch.delenv("OISHA_API_SECRET", raising=False)
    monkeypatch.setenv("BOT_TOKEN", "telegram-bot-secret")

    with pytest.raises(RuntimeError):
        _ = config.JWT_SECRET


def test_config_can_use_api_secret_for_session_until_dedicated_key_exists(monkeypatch):
    from src import config

    monkeypatch.delenv("JWT_SECRET", raising=False)
    monkeypatch.setenv("OISHA_API_SECRET", "separate-api-secret")

    assert config.JWT_SECRET == "separate-api-secret"
