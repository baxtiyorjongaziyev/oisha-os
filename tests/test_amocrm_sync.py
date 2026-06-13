import json
import asyncio
import threading
from unittest.mock import AsyncMock

import pytest

from src.services.core.amocrm_sync import AmoCRMSync


class _Response:
    def __init__(self, status_code: int, payload: dict | None = None):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = json.dumps(self._payload)

    def json(self):
        return self._payload


@pytest.mark.asyncio
async def test_check_connection_uses_env_token(monkeypatch):
    monkeypatch.setenv(
        "AMOCRM_TOKEN_JSON",
        json.dumps({"access_token": "valid-access-token", "refresh_token": "refresh-token"}),
    )

    seen_headers = {}

    def fake_get(url, headers=None, timeout=None):
        seen_headers.update(headers or {})
        assert url == "https://jonbrandingagency.amocrm.ru/api/v4/account"
        assert timeout == 15
        return _Response(200, {"id": 1})

    monkeypatch.setattr("requests.get", fake_get)

    amocrm = AmoCRMSync("jonbrandingagency", "client-id", "client-secret", "https://example.test/cb")

    assert await amocrm.check_connection() is True
    assert seen_headers["Authorization"] == "Bearer valid-access-token"
    assert amocrm.last_error is None


@pytest.mark.asyncio
async def test_check_connection_refreshes_expired_token(monkeypatch):
    monkeypatch.setenv(
        "AMOCRM_TOKEN_JSON",
        json.dumps({"access_token": "expired-token", "refresh_token": "refresh-token"}),
    )

    calls = {"account": 0}

    def fake_get(url, headers=None, timeout=None):
        calls["account"] += 1
        return _Response(401 if calls["account"] == 1 else 200, {"id": 1})

    monkeypatch.setattr("requests.get", fake_get)
    monkeypatch.setattr(AmoCRMSync, "refresh_token", lambda self: setattr(self, "access_token", "new-token") or True)

    amocrm = AmoCRMSync("jonbrandingagency", "client-id", "client-secret", "https://example.test/cb")

    assert await amocrm.check_connection() is True
    assert calls["account"] == 2
    assert amocrm.last_error is None


@pytest.mark.asyncio
async def test_invalid_oauth_refresh_blocks_repeated_crm_calls(monkeypatch):
    monkeypatch.setenv(
        "AMOCRM_TOKEN_JSON",
        json.dumps({"access_token": "expired-token", "refresh_token": "bad-refresh-token"}),
    )

    calls = {"post": 0, "get": 0}

    def fake_post(url, json=None, data=None, timeout=None):
        calls["post"] += 1
        return _Response(400, {"detail": "invalid oauth parameters"})

    def fake_get(url, headers=None, timeout=None):
        calls["get"] += 1
        return _Response(401, {"detail": "unauthorized"})

    monkeypatch.setattr("requests.post", fake_post)
    monkeypatch.setattr("requests.get", fake_get)

    amocrm = AmoCRMSync("jonbrandingagency", "client-id", "client-secret", "https://example.test/cb")

    assert amocrm.refresh_token() is False
    assert amocrm.is_auth_blocked() is True
    assert calls["post"] == 2  # JSON attempt + form fallback before circuit opens.

    assert amocrm.refresh_token() is False
    assert await amocrm.check_connection() is False
    assert calls["post"] == 2
    assert calls["get"] == 0


@pytest.mark.asyncio
async def test_get_leads_detailed_does_not_block_event_loop(monkeypatch):
    monkeypatch.setenv(
        "AMOCRM_TOKEN_JSON",
        json.dumps({"access_token": "valid-access-token", "refresh_token": "refresh-token"}),
    )
    release = threading.Event()
    observed = {"released_while_request_waited": False}

    def fake_get(url, headers=None, params=None, timeout=None):
        observed["released_while_request_waited"] = release.wait(0.5)
        return _Response(200, {"_embedded": {"leads": []}})

    async def release_request():
        await asyncio.sleep(0.01)
        release.set()

    monkeypatch.setattr("requests.get", fake_get)
    amocrm = AmoCRMSync("jonbrandingagency", "client-id", "client-secret", "https://example.test/cb")

    release_task = asyncio.create_task(release_request())
    assert await amocrm.get_leads_detailed(limit=30) == []
    await release_task
    assert observed["released_while_request_waited"] is True


@pytest.mark.asyncio
async def test_get_lead_does_not_block_event_loop(monkeypatch):
    monkeypatch.setenv(
        "AMOCRM_TOKEN_JSON",
        json.dumps({"access_token": "valid-access-token", "refresh_token": "refresh-token"}),
    )
    release = threading.Event()
    observed = {"released_while_request_waited": False}

    def fake_get(url, headers=None, timeout=None):
        observed["released_while_request_waited"] = release.wait(0.5)
        return _Response(200, {"id": 46088992, "status_id": 80178230})

    async def release_request():
        await asyncio.sleep(0.01)
        release.set()

    monkeypatch.setattr("requests.get", fake_get)
    amocrm = AmoCRMSync("jonbrandingagency", "client-id", "client-secret", "https://example.test/cb")

    release_task = asyncio.create_task(release_request())
    lead = await amocrm.get_lead(46088992)
    await release_task

    assert lead == {"id": 46088992, "status_id": 80178230}
    assert observed["released_while_request_waited"] is True


@pytest.mark.asyncio
async def test_primary_contact_phone_hydrates_shallow_embedded_contact(monkeypatch):
    monkeypatch.setenv(
        "AMOCRM_TOKEN_JSON",
        json.dumps({"access_token": "valid-access-token", "refresh_token": "refresh-token"}),
    )

    def fake_get(url, headers=None, params=None, timeout=None):
        assert url.endswith("/api/v4/contacts/321")
        assert params == {"with": "leads"}
        return _Response(
            200,
            {
                "id": 321,
                "custom_fields_values": [
                    {
                        "field_code": "PHONE",
                        "values": [{"value": "+998901234567"}],
                    }
                ],
            },
        )

    monkeypatch.setattr("requests.get", fake_get)
    amocrm = AmoCRMSync("jonbrandingagency", "client-id", "client-secret", "https://example.test/cb")

    phone = await amocrm.get_primary_contact_phone(
        {"_embedded": {"contacts": [{"id": 321}]}}
    )

    assert phone == "+998901234567"


@pytest.mark.asyncio
@pytest.mark.parametrize("closed_status_id", [142, 143])
async def test_create_task_blocks_closed_leads(monkeypatch, closed_status_id):
    monkeypatch.setenv(
        "AMOCRM_TOKEN_JSON",
        json.dumps({"access_token": "valid-access-token", "refresh_token": "refresh-token"}),
    )
    amocrm = AmoCRMSync("jonbrandingagency", "client-id", "client-secret", "https://example.test/cb")
    amocrm.get_lead = AsyncMock(
        return_value={"id": 46088992, "status_id": closed_status_id}
    )
    amocrm._request_with_auth = AsyncMock(
        return_value=_Response(201, {"_embedded": {"tasks": [{"id": 77}]}})
    )

    result = await amocrm.create_task(
        element_id=46088992,
        text="Oisha-OS Keyingi Qadam",
        complete_till=1781370000,
    )

    assert result is False
    assert amocrm.last_error == "lead_closed_for_tasks"
    amocrm._request_with_auth.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_task_blocks_when_lead_state_cannot_be_verified(monkeypatch):
    monkeypatch.setenv(
        "AMOCRM_TOKEN_JSON",
        json.dumps({"access_token": "valid-access-token", "refresh_token": "refresh-token"}),
    )
    amocrm = AmoCRMSync("jonbrandingagency", "client-id", "client-secret", "https://example.test/cb")
    amocrm.get_lead = AsyncMock(return_value=None)
    amocrm._request_with_auth = AsyncMock(
        return_value=_Response(201, {"_embedded": {"tasks": [{"id": 77}]}})
    )

    result = await amocrm.create_task(
        element_id=46088992,
        text="Oisha-OS Keyingi Qadam",
        complete_till=1781370000,
    )

    assert result is False
    assert amocrm.last_error == "lead_state_unavailable_for_tasks"
    amocrm._request_with_auth.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_task_blocks_when_lead_status_is_missing(monkeypatch):
    monkeypatch.setenv(
        "AMOCRM_TOKEN_JSON",
        json.dumps({"access_token": "valid-access-token", "refresh_token": "refresh-token"}),
    )
    amocrm = AmoCRMSync("jonbrandingagency", "client-id", "client-secret", "https://example.test/cb")
    amocrm.get_lead = AsyncMock(return_value={"id": 46088992})
    amocrm._request_with_auth = AsyncMock(
        return_value=_Response(201, {"_embedded": {"tasks": [{"id": 77}]}})
    )

    result = await amocrm.create_task(
        element_id=46088992,
        text="Oisha-OS Keyingi Qadam",
        complete_till=1781370000,
    )

    assert result is False
    assert amocrm.last_error == "lead_state_unavailable_for_tasks"
    amocrm._request_with_auth.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_task_allows_verified_active_lead(monkeypatch):
    monkeypatch.setenv(
        "AMOCRM_TOKEN_JSON",
        json.dumps({"access_token": "valid-access-token", "refresh_token": "refresh-token"}),
    )
    amocrm = AmoCRMSync("jonbrandingagency", "client-id", "client-secret", "https://example.test/cb")
    amocrm.get_lead = AsyncMock(
        return_value={"id": 46088992, "status_id": 80178230}
    )
    amocrm._request_with_auth = AsyncMock(
        return_value=_Response(201, {"_embedded": {"tasks": [{"id": 77}]}})
    )

    result = await amocrm.create_task(
        element_id=46088992,
        text="Faol mijoz bilan bog'lanish",
        complete_till=1781370000,
    )

    assert result == {"_embedded": {"tasks": [{"id": 77}]}}
    assert amocrm.last_error is None
    amocrm._request_with_auth.assert_awaited_once()
