"""Email + parol bilan kirish: faqat owner yaratgan hisoblar, urinishlar cheklanadi."""
import pytest
from fastapi.testclient import TestClient

from src.api import web_auth_store as store
from src.services.api_server.core import app

JWT = "test-dedicated-jwt-secret-at-least-32-bytes-long!"
GOOD = "correct-horse-battery"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "_DB_PATH", tmp_path / "web_auth.db")
    monkeypatch.setenv("JWT_SECRET", JWT)
    store._failures.clear()
    store.set_user_password("boss@example.com", GOOD, role="owner", name="Boss")
    return TestClient(app, follow_redirects=False)


def _login(client, email="boss@example.com", password=GOOD, **extra):
    return client.post("/api/auth/email/login", data={"email": email, "password": password, **extra})


def test_login_page_has_email_form(client):
    res = client.get("/api/auth/telegram/login")
    assert res.status_code == 200
    assert 'action="/api/auth/email/login"' in res.text


def test_correct_password_sets_session_cookie(client):
    res = _login(client)
    assert res.status_code == 303
    assert "oisha_token=" in res.headers.get("set-cookie", "")
    assert "httponly" in res.headers["set-cookie"].lower()


def test_email_is_case_insensitive(client):
    assert _login(client, email="  BOSS@Example.com ").status_code == 303


def test_wrong_password_and_unknown_user_look_identical(client):
    wrong = _login(client, password="wrong-password-123")
    unknown = _login(client, email="nobody@example.com")
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()
    assert "set-cookie" not in wrong.headers


def test_login_never_creates_accounts(client):
    _login(client, email="new@example.com", password="some-long-password-1")
    assert store.authenticate_email("new@example.com", "some-long-password-1") is None


def test_short_password_rejected_on_create(client):
    with pytest.raises(ValueError):
        store.set_user_password("short@example.com", "x" * (store.MIN_PASSWORD_LENGTH - 1))


def test_throttle_after_five_failures_then_blocks_correct_password(client):
    for _ in range(5):
        assert _login(client, password="bad-password-000").status_code == 401
    assert _login(client, password="bad-password-000").status_code == 429
    assert _login(client).status_code == 429


def test_success_clears_failure_counter(client):
    for _ in range(4):
        _login(client, password="bad-password-000")
    assert _login(client).status_code == 303
    assert _login(client, password="bad-password-000").status_code == 401


def test_next_redirect_is_whitelisted(client):
    ok = _login(client, next="/api/marketing/capi/console")
    assert ok.headers["location"] == "/api/marketing/capi/console"
    evil = _login(client, next="https://evil.example")
    assert evil.headers["location"] == "/"


def test_set_user_password_updates_existing(client):
    result = store.set_user_password("boss@example.com", "another-long-password", role="owner")
    assert result["created"] is False
    assert _login(client).status_code == 401
    assert _login(client, password="another-long-password").status_code == 303
