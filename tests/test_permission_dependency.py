import secrets
import time

import jwt
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.rbac import Permission, require_permissions
from src.api.security import ApiAccessMiddleware


SECRET = secrets.token_hex(32)


def _cookie(role: str, subject: str = "user-1") -> dict[str, str]:
    return {
        "oisha_token": jwt.encode(
            {"sub": subject, "role": role, "exp": int(time.time()) + 60},
            SECRET,
            algorithm="HS256",
        )
    }


def _client(monkeypatch) -> TestClient:
    monkeypatch.setenv("JWT_SECRET", SECRET)
    monkeypatch.delenv("OISHA_API_SECRET", raising=False)
    app = FastAPI()
    app.add_middleware(ApiAccessMiddleware)

    @app.get(
        "/api/private-finance",
        dependencies=[require_permissions(Permission.FINANCE_READ)],
    )
    async def finance():
        return {"ok": True}

    return TestClient(app)


def test_missing_auth_is_401(monkeypatch):
    assert _client(monkeypatch).get("/api/private-finance").status_code == 401


def test_authenticated_but_forbidden_is_403(monkeypatch):
    response = _client(monkeypatch).get(
        "/api/private-finance",
        cookies=_cookie("seller"),
    )
    assert response.status_code == 403
    assert response.json() == {"detail": "Forbidden"}


def test_owner_and_admin_are_allowed(monkeypatch):
    client = _client(monkeypatch)
    assert client.get("/api/private-finance", cookies=_cookie("owner")).status_code == 200
    assert client.get("/api/private-finance", cookies=_cookie("admin")).status_code == 200
