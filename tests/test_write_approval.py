from datetime import datetime, timedelta, timezone

import pytest

from src.api.rbac import Permission
from src.api.write_approval import ApprovalConflict, WriteApprovalStore


NOW = datetime(2026, 7, 27, 10, 0, tzinfo=timezone.utc)


def test_admin_request_is_pending_and_owner_consumes_once():
    store = WriteApprovalStore(ttl_seconds=600)
    ticket = store.request(
        requester_subject="admin-1",
        permission=Permission.MCP_WRITE,
        action="telegram.send",
        payload={"chat_id": "synthetic", "text": "hello"},
        now=NOW,
    )

    assert ticket.status == "pending"
    assert ticket.expires_at == NOW + timedelta(minutes=10)
    assert ticket.payload_hash
    assert "hello" not in repr(ticket)

    approved = store.approve(ticket.id, owner_subject="owner-1", now=NOW)
    assert approved.status == "approved"

    consumed, payload = store.consume(ticket.id, owner_subject="owner-1", now=NOW)
    assert consumed.status == "consumed"
    assert payload == {"chat_id": "synthetic", "text": "hello"}

    with pytest.raises(ApprovalConflict):
        store.consume(ticket.id, owner_subject="owner-1", now=NOW)


def test_expired_ticket_cannot_be_approved_or_consumed():
    store = WriteApprovalStore(ttl_seconds=600)
    ticket = store.request(
        requester_subject="admin-1",
        permission=Permission.TELEGRAM_SEND,
        action="telegram.send",
        payload={"chat_id": "synthetic", "text": "hello"},
        now=NOW,
    )

    after_expiry = NOW + timedelta(minutes=11)
    with pytest.raises(ApprovalConflict):
        store.approve(ticket.id, owner_subject="owner-1", now=after_expiry)
    with pytest.raises(ApprovalConflict):
        store.consume(ticket.id, owner_subject="owner-1", now=after_expiry)


def test_rejected_ticket_cannot_be_consumed():
    store = WriteApprovalStore(ttl_seconds=600)
    ticket = store.request(
        requester_subject="admin-1",
        permission=Permission.MCP_WRITE,
        action="telegram.send",
        payload={"chat_id": "synthetic", "text": "hello"},
        now=NOW,
    )
    rejected = store.reject(ticket.id, owner_subject="owner-1", now=NOW)
    assert rejected.status == "rejected"

    with pytest.raises(ApprovalConflict):
        store.consume(ticket.id, owner_subject="owner-1", now=NOW)
