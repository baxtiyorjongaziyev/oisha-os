"""In-memory one-time approval tickets for privileged writes.

Oisha's Oracle deployment runs one API process. Tickets deliberately keep the
write payload private in process memory while exposing only a SHA-256 payload
hash in the public ticket object and audit events.
"""
from __future__ import annotations

import hashlib
import json
import secrets
import threading
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping

from src.api.rbac import Permission


class ApprovalConflict(RuntimeError):
    """Ticket is expired, replayed, rejected, missing, or in the wrong state."""


@dataclass(frozen=True, slots=True)
class ApprovalTicket:
    id: str
    requester_subject: str
    permission: str
    action: str
    payload_hash: str
    created_at: datetime
    expires_at: datetime
    status: str
    owner_subject: str | None = None


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _payload_hash(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        dict(payload),
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class WriteApprovalStore:
    def __init__(self, *, ttl_seconds: int = 600):
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive")
        self.ttl_seconds = int(ttl_seconds)
        self._tickets: dict[str, ApprovalTicket] = {}
        self._payloads: dict[str, dict[str, Any]] = {}
        self._lock = threading.RLock()

    def request(
        self,
        *,
        requester_subject: str,
        permission: Permission | str,
        action: str,
        payload: Mapping[str, Any],
        now: datetime | None = None,
    ) -> ApprovalTicket:
        subject = str(requester_subject or "").strip()
        action_name = str(action or "").strip()
        if not subject or not action_name:
            raise ValueError("requester_subject and action are required")
        current = now or _utc_now()
        ticket_id = secrets.token_urlsafe(24)
        permission_value = (
            permission.value if isinstance(permission, Permission) else str(permission)
        )
        ticket = ApprovalTicket(
            id=ticket_id,
            requester_subject=subject,
            permission=permission_value,
            action=action_name,
            payload_hash=_payload_hash(payload),
            created_at=current,
            expires_at=current + timedelta(seconds=self.ttl_seconds),
            status="pending",
        )
        with self._lock:
            self._tickets[ticket_id] = ticket
            self._payloads[ticket_id] = dict(payload)
        return ticket

    def _active(self, ticket_id: str, now: datetime) -> ApprovalTicket:
        ticket = self._tickets.get(str(ticket_id))
        if ticket is None:
            raise ApprovalConflict("approval ticket not found")
        if now >= ticket.expires_at:
            expired = replace(ticket, status="expired")
            self._tickets[ticket.id] = expired
            self._payloads.pop(ticket.id, None)
            raise ApprovalConflict("approval ticket expired")
        return ticket

    def approve(
        self,
        ticket_id: str,
        *,
        owner_subject: str,
        now: datetime | None = None,
    ) -> ApprovalTicket:
        current = now or _utc_now()
        with self._lock:
            ticket = self._active(ticket_id, current)
            if ticket.status != "pending":
                raise ApprovalConflict("approval ticket is not pending")
            updated = replace(
                ticket,
                status="approved",
                owner_subject=str(owner_subject or "").strip() or None,
            )
            self._tickets[ticket.id] = updated
            return updated

    def reject(
        self,
        ticket_id: str,
        *,
        owner_subject: str,
        now: datetime | None = None,
    ) -> ApprovalTicket:
        current = now or _utc_now()
        with self._lock:
            ticket = self._active(ticket_id, current)
            if ticket.status != "pending":
                raise ApprovalConflict("approval ticket is not pending")
            updated = replace(
                ticket,
                status="rejected",
                owner_subject=str(owner_subject or "").strip() or None,
            )
            self._tickets[ticket.id] = updated
            self._payloads.pop(ticket.id, None)
            return updated

    def consume(
        self,
        ticket_id: str,
        *,
        owner_subject: str,
        now: datetime | None = None,
    ) -> tuple[ApprovalTicket, dict[str, Any]]:
        current = now or _utc_now()
        with self._lock:
            ticket = self._active(ticket_id, current)
            if ticket.status != "approved":
                raise ApprovalConflict("approval ticket is not approved")
            payload = self._payloads.pop(ticket.id, None)
            if payload is None:
                raise ApprovalConflict("approval payload is unavailable")
            consumed = replace(
                ticket,
                status="consumed",
                owner_subject=str(owner_subject or "").strip()
                or ticket.owner_subject,
            )
            self._tickets[ticket.id] = consumed
            return consumed, payload

    def get(self, ticket_id: str) -> ApprovalTicket | None:
        with self._lock:
            return self._tickets.get(str(ticket_id))


write_approval_store = WriteApprovalStore(ttl_seconds=600)
