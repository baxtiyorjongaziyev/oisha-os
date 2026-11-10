"""Pagination and Telegram approval security contract tests (network-free)."""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from scripts.safe_crm_drive_sync import fetch_all_leads
from src.services.core.crm import drive_delete_approvals as approvals


class Response:
    def __init__(self, status, items=None):
        self.status_code = status
        self.items = items

    def json(self):
        return {"_embedded": {"leads": self.items}}


def test_backfill_fetches_every_page_without_silent_truncation():
    amo = Mock()
    amo.base_url = "https://example.amocrm.ru"
    amo._request_with_auth = AsyncMock(side_effect=[
        Response(200, [{"id": 1}, {"id": 2}]),
        Response(200, [{"id": 3}]),
    ])
    async def run():
        return [r async for r in fetch_all_leads(amo, page_size=2, max_pages=4)]
    assert [r["id"] for r in asyncio.run(run())] == [1, 2, 3]
    assert amo._request_with_auth.await_count == 2


def test_backfill_fails_closed_on_api_error():
    amo = Mock()
    amo.base_url = "https://example.amocrm.ru"
    amo._request_with_auth = AsyncMock(return_value=Response(503))
    async def run():
        return [r async for r in fetch_all_leads(amo, page_size=2)]
    with pytest.raises(RuntimeError, match="HTTP 503"):
        asyncio.run(run())


def test_backfill_does_not_call_partial_scan_complete():
    amo = Mock()
    amo.base_url = "https://example.amocrm.ru"
    amo._request_with_auth = AsyncMock(return_value=Response(200, [{"id": 1}]))
    async def run():
        return [r async for r in fetch_all_leads(amo, page_size=1, max_pages=1)]
    with pytest.raises(RuntimeError, match="incomplete scan"):
        asyncio.run(run())


def test_verified_copy_receipt_rejects_missing_original():
    text = (
        "[OISHA_DRIVE_COPY] lead=42 note=9 drive=abcD_123 "
        + "sha256=" + "a" * 64 + " size=1234"
    )
    assert approvals.parse_verified_receipt(42, text, {}) is None
    original = {9: {"note_type": "file", "params": {"file_uuid": "uuid-9"}}}
    record = approvals.parse_verified_receipt(42, text, original)
    assert record is not None
    assert record.lead_id == 42 and record.note_id == 9
    assert record.size == 1234
    assert approvals.parse_verified_receipt(55, text, original) is None


def test_non_owner_cannot_claim_approval(monkeypatch):
    monkeypatch.setattr(approvals.settings, "OWNER_ID", 321)
    with pytest.raises(PermissionError):
        asyncio.run(approvals.claim("request", actor=222, approve=True))


def test_owner_claim_is_one_time_atomic(monkeypatch):
    monkeypatch.setattr(approvals.settings, "OWNER_ID", 321)
    monkeypatch.setattr(approvals, "_schema", AsyncMock())
    db = Mock()
    db.execute = AsyncMock(side_effect=[
        [{"lead_id": 42, "note_id": 9, "drive_id": "abc", "size": 7,
          "sha256": "a" * 64}],
        [],
    ])
    db.commit = AsyncMock()
    monkeypatch.setattr(approvals, "db_pool", db)
    first = asyncio.run(approvals.claim("request", actor=321, approve=True))
    second = asyncio.run(approvals.claim("request", actor=321, approve=True))
    assert first["note_id"] == 9 and second is None
    assert "status = 'pending'" in db.execute.call_args_list[0].args[0]
    assert db.commit.await_count == 2
