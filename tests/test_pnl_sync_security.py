import re
from pathlib import Path

import httpx
import pytest
from pydantic import SecretStr

from src.services.core import (
    airtable_approval_callbacks,
    airtable_config,
    client_success_engine,
)
from src.services.core.airtable_config import (
    AirtableConfigurationError,
    AirtableResponseError,
)
from src.services.core.finance import pnl_sync


AIRTABLE_PAT_LITERAL = re.compile(
    r"\bpat[A-Za-z0-9]{14}\.[A-Za-z0-9]{64}\b"
)


def _mock_airtable(monkeypatch: pytest.MonkeyPatch, handler):
    real_async_client = httpx.AsyncClient
    transport = httpx.MockTransport(handler)

    def factory(*args, **kwargs):
        return real_async_client(
            transport=transport,
            timeout=kwargs.get("timeout"),
        )

    monkeypatch.setattr(pnl_sync.httpx, "AsyncClient", factory)


def test_airtable_source_contains_no_pat_literals():
    matches = []
    for root in (Path("src"), Path("scripts")):
        for path in root.rglob("*.py"):
            text = path.read_text(encoding="utf-8", errors="ignore")
            if AIRTABLE_PAT_LITERAL.search(text):
                matches.append(str(path))

    assert matches == []


def test_airtable_maintenance_scripts_require_secret_only_environment():
    protected = []
    missing_gate = []
    for path in Path("scripts").rglob("*.py"):
        text = path.read_text(encoding="utf-8", errors="ignore")
        if 'Bearer {API_KEY}' not in text:
            continue
        protected.append(str(path))
        if not all(
            marker in text
            for marker in (
                'API_KEY = os.environ.get("AIRTABLE_API_KEY", "").strip()',
                "if not API_KEY:",
                'raise RuntimeError("AIRTABLE_API_KEY is required',
            )
        ):
            missing_gate.append(str(path))

    assert protected
    assert missing_gate == []


@pytest.mark.parametrize("configured", [None, "", "   ", SecretStr("   ")])
def test_airtable_headers_fail_closed_without_secret(monkeypatch, configured):
    monkeypatch.setattr(
        airtable_config.settings,
        "AIRTABLE_API_KEY",
        configured,
        raising=False,
    )

    with pytest.raises(AirtableConfigurationError, match="AIRTABLE_API_KEY"):
        airtable_config.airtable_request_headers()


@pytest.mark.asyncio
async def test_pnl_sync_missing_secret_never_opens_http_client(monkeypatch):
    monkeypatch.setattr(
        airtable_config.settings,
        "AIRTABLE_API_KEY",
        None,
        raising=False,
    )

    def forbidden_client(*args, **kwargs):
        pytest.fail("HTTP client must not be created without Airtable credentials")

    monkeypatch.setattr(pnl_sync.httpx, "AsyncClient", forbidden_client)

    with pytest.raises(AirtableConfigurationError, match="AIRTABLE_API_KEY"):
        await pnl_sync.sync_monthly_pnl()


@pytest.mark.asyncio
async def test_approval_update_missing_secret_fails_without_http(monkeypatch):
    monkeypatch.setattr(
        airtable_config.settings,
        "AIRTABLE_API_KEY",
        None,
        raising=False,
    )

    def forbidden_client(*args, **kwargs):
        pytest.fail("HTTP client must not be created without Airtable credentials")

    monkeypatch.setattr(
        airtable_approval_callbacks.httpx,
        "AsyncClient",
        forbidden_client,
    )

    updated = await airtable_approval_callbacks.update_airtable_transaction_status(
        "rec-test",
        "Tasdiqlangan",
    )

    assert updated is False


@pytest.mark.asyncio
async def test_pnl_sync_read_error_stops_before_any_write(monkeypatch):
    monkeypatch.setattr(
        airtable_config.settings,
        "AIRTABLE_API_KEY",
        SecretStr("unit-test-secret"),
        raising=False,
    )
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(401, json={"error": "unauthorized"})

    _mock_airtable(monkeypatch, handler)

    with pytest.raises(httpx.HTTPStatusError):
        await pnl_sync.sync_monthly_pnl()

    assert [request.method for request in requests] == ["GET"]


@pytest.mark.asyncio
async def test_pnl_sync_later_page_error_stops_before_any_write(monkeypatch):
    monkeypatch.setattr(
        airtable_config.settings,
        "AIRTABLE_API_KEY",
        SecretStr("unit-test-secret"),
        raising=False,
    )
    requests = []
    transaction_pages = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal transaction_pages
        requests.append(request)
        if pnl_sync.PNL_TABLE_ID in request.url.path:
            return httpx.Response(200, json={"records": []})
        if pnl_sync.CAT_TABLE_ID in request.url.path:
            return httpx.Response(200, json={"records": []})
        transaction_pages += 1
        if transaction_pages == 1:
            return httpx.Response(
                200,
                json={"records": [], "offset": "next-page"},
            )
        return httpx.Response(502, json={"error": "upstream unavailable"})

    _mock_airtable(monkeypatch, handler)

    with pytest.raises(httpx.HTTPStatusError):
        await pnl_sync.sync_monthly_pnl()

    assert [request.method for request in requests] == ["GET"] * 4


@pytest.mark.asyncio
async def test_pnl_sync_malformed_success_payload_stops_before_write(monkeypatch):
    monkeypatch.setattr(
        airtable_config.settings,
        "AIRTABLE_API_KEY",
        SecretStr("unit-test-secret"),
        raising=False,
    )
    methods = []

    def handler(request: httpx.Request) -> httpx.Response:
        methods.append(request.method)
        if pnl_sync.PNL_TABLE_ID in request.url.path:
            return httpx.Response(
                200,
                json={
                    "records": [
                        {
                            "id": "rec-pnl",
                            "fields": {"Oy nomi": "2026-08 Avgust"},
                        }
                    ]
                },
            )
        if pnl_sync.CAT_TABLE_ID in request.url.path:
            return httpx.Response(200, json={"records": []})
        return httpx.Response(200, json={})

    _mock_airtable(monkeypatch, handler)

    with pytest.raises(AirtableResponseError, match="records list"):
        await pnl_sync.sync_monthly_pnl()

    assert methods == ["GET", "GET", "GET"]


@pytest.mark.asyncio
async def test_pnl_sync_patch_error_is_not_reported_as_success(monkeypatch):
    monkeypatch.setattr(
        airtable_config.settings,
        "AIRTABLE_API_KEY",
        SecretStr("unit-test-secret"),
        raising=False,
    )
    methods = []

    def handler(request: httpx.Request) -> httpx.Response:
        methods.append(request.method)
        if request.method == "PATCH":
            return httpx.Response(503, json={"error": "unavailable"})
        if PNL_TABLE_ID in request.url.path:
            return httpx.Response(
                200,
                json={
                    "records": [
                        {
                            "id": "rec-pnl",
                            "fields": {"Oy nomi": "2026-08 Avgust"},
                        }
                    ]
                },
            )
        if CAT_TABLE_ID in request.url.path:
            return httpx.Response(200, json={"records": []})
        return httpx.Response(
            200,
            json={
                "records": [
                    {
                        "id": "rec-trx",
                        "fields": {
                            "Sana": "2026-08-28",
                            "Oylik P&L": [],
                            "Turi": "Kirim",
                            "Summa UZS": 100,
                        },
                    }
                ]
            },
        )

    PNL_TABLE_ID = pnl_sync.PNL_TABLE_ID
    CAT_TABLE_ID = pnl_sync.CAT_TABLE_ID
    _mock_airtable(monkeypatch, handler)

    with pytest.raises(httpx.HTTPStatusError):
        await pnl_sync.sync_monthly_pnl()

    assert methods == ["GET", "GET", "GET", "PATCH"]


@pytest.mark.asyncio
async def test_pnl_sync_valid_secret_preserves_successful_empty_sync(monkeypatch):
    monkeypatch.setattr(
        airtable_config.settings,
        "AIRTABLE_API_KEY",
        SecretStr("unit-test-secret"),
        raising=False,
    )
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"records": []})

    _mock_airtable(monkeypatch, handler)

    result = await pnl_sync.sync_monthly_pnl()

    assert result == {
        "status": "ok",
        "months_updated": 0,
        "transactions_linked": 0,
    }
    assert [request.method for request in requests] == ["GET", "GET", "GET"]
    assert all(
        request.headers["Authorization"] == "Bearer unit-test-secret"
        for request in requests
    )


@pytest.mark.asyncio
async def test_weekly_budget_report_airtable_error_is_not_zero_report(monkeypatch):
    monkeypatch.setattr(
        airtable_config.settings,
        "AIRTABLE_API_KEY",
        SecretStr("unit-test-secret"),
        raising=False,
    )
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(503, json={"error": "unavailable"})

    _mock_airtable(monkeypatch, handler)

    with pytest.raises(httpx.HTTPStatusError):
        await client_success_engine.generate_weekly_budget_report()

    assert [request.method for request in requests] == ["GET"]


@pytest.mark.asyncio
async def test_weekly_budget_report_valid_empty_data_remains_supported(monkeypatch):
    monkeypatch.setattr(
        airtable_config.settings,
        "AIRTABLE_API_KEY",
        SecretStr("unit-test-secret"),
        raising=False,
    )
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"records": []})

    _mock_airtable(monkeypatch, handler)

    report = await client_success_engine.generate_weekly_budget_report()

    assert isinstance(report, str)
    assert [request.method for request in requests] == ["GET", "GET", "GET"]
