import time

import jwt
from fastapi import FastAPI
from fastapi.testclient import TestClient

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


def test_session_is_rejected_when_dedicated_jwt_secret_is_missing():
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
        return {"callback": True}

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
    assert client.get("/api/auth/telegram/callback").status_code == 200
