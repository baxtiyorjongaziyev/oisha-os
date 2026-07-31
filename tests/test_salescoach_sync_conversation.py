from __future__ import annotations

import logging

import httpx
import pytest

from src.services.core.salescoach_sync import SalesCoachSync


class FakeResponse:
    def __init__(self, payload: object, status_code: int = 200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            request = httpx.Request("POST", "https://salescoach.test/v1/negotiations/analyze-conversation")
            response = httpx.Response(self.status_code, request=request)
            raise httpx.HTTPStatusError("request failed", request=request, response=response)

    def json(self) -> object:
        return self._payload


class FakeAsyncClient:
    def __init__(self, payload: object | None = None, error: Exception | None = None):
        self.payload = payload
        self.error = error
        self.is_closed = False
        self.last_path: str | None = None
        self.last_json: dict | None = None
        self.last_timeout: float | None = None

    async def post(self, path: str, *, json: dict, timeout: float | None = None):
        self.last_path = path
        self.last_json = json
        self.last_timeout = timeout
        if self.error:
            raise self.error
        return FakeResponse(self.payload)

    async def aclose(self) -> None:
        self.is_closed = True


MESSAGES = [
    {
        "id": 1001,
        "role": "customer",
        "text": "Narxi qancha?",
        "sentAt": "2026-07-31T10:00:00Z",
    },
    {
        "id": 1002,
        "role": "manager",
        "text": "Avval vazifangizni aniqlab olaylik.",
        "sentAt": "2026-07-31T10:01:00Z",
    },
]


@pytest.mark.asyncio
async def test_analyze_conversation_posts_structured_payload():
    sync = SalesCoachSync()
    sync.enabled = True
    fake = FakeAsyncClient(payload={"overallScore": 78, "confidence": 0.9})
    sync._client = fake

    result = await sync.analyze_conversation(
        lead_id=42,
        manager_id="77",
        crm_status="Birinchi kontakt",
        messages=MESSAGES,
    )

    assert result == {"overallScore": 78, "confidence": 0.9}
    assert fake.last_path == "/v1/negotiations/analyze-conversation"
    assert fake.last_json == {
        "leadId": 42,
        "managerId": "77",
        "crmStatus": "Birinchi kontakt",
        "messages": MESSAGES,
    }
    assert fake.last_timeout == 30.0


@pytest.mark.asyncio
async def test_analyze_conversation_returns_none_when_disabled():
    sync = SalesCoachSync()
    sync.enabled = False
    fake = FakeAsyncClient(payload={"overallScore": 78})
    sync._client = fake

    result = await sync.analyze_conversation(
        lead_id=42,
        manager_id="77",
        messages=MESSAGES,
    )

    assert result is None
    assert fake.last_path is None


@pytest.mark.asyncio
async def test_analyze_conversation_rejects_non_object_response():
    sync = SalesCoachSync()
    sync.enabled = True
    sync._client = FakeAsyncClient(payload=[{"overallScore": 78}])

    result = await sync.analyze_conversation(
        lead_id=42,
        manager_id="77",
        messages=MESSAGES,
    )

    assert result is None


@pytest.mark.asyncio
async def test_analyze_conversation_logs_only_error_type(caplog):
    sync = SalesCoachSync()
    sync.enabled = True
    sync._client = FakeAsyncClient(
        error=httpx.TimeoutException("Narxi qancha? maxfiy suhbat matni")
    )

    with caplog.at_level(logging.WARNING):
        result = await sync.analyze_conversation(
            lead_id=42,
            manager_id="77",
            messages=MESSAGES,
        )

    assert result is None
    assert "TimeoutException" in caplog.text
    assert "Narxi qancha" not in caplog.text
    assert "maxfiy suhbat matni" not in caplog.text
