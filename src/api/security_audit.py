"""Sanitized security audit events for authentication and authorization decisions."""
from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from typing import Iterable
from urllib.parse import urlsplit

from src.api.rbac import Permission, Principal

logger = logging.getLogger("OishaSecurityAudit")


def hash_resource_id(value: object) -> str:
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()


def _safe_route(value: str) -> str:
    parsed = urlsplit(str(value or ""))
    return parsed.path or "/"


def _permission_values(values: Iterable[Permission | str]) -> tuple[str, ...]:
    return tuple(item.value if isinstance(item, Permission) else str(item) for item in values)


@dataclass(frozen=True, slots=True)
class SecurityAuditEvent:
    event_type: str
    subject: str
    role: str
    auth_type: str
    route: str
    method: str
    outcome: str
    permissions: tuple[str, ...]
    resource_type: str | None = None
    resource_id_hash: str | None = None

    @classmethod
    def denied(
        cls,
        *,
        principal: Principal,
        route: str,
        method: str,
        permissions: Iterable[Permission | str],
        resource_type: str | None = None,
        resource_id: object | None = None,
    ) -> "SecurityAuditEvent":
        return cls(
            event_type="authorization_denied",
            subject=principal.subject,
            role=principal.role.value,
            auth_type=principal.auth_type,
            route=_safe_route(route),
            method=str(method or "").upper(),
            outcome="denied",
            permissions=_permission_values(permissions),
            resource_type=str(resource_type) if resource_type else None,
            resource_id_hash=(
                hash_resource_id(resource_id) if resource_id is not None else None
            ),
        )

    @classmethod
    def privileged_write(
        cls,
        *,
        principal: Principal,
        route: str,
        method: str,
        permissions: Iterable[Permission | str],
        outcome: str,
        resource_type: str | None = None,
        resource_id: object | None = None,
    ) -> "SecurityAuditEvent":
        return cls(
            event_type="privileged_write",
            subject=principal.subject,
            role=principal.role.value,
            auth_type=principal.auth_type,
            route=_safe_route(route),
            method=str(method or "").upper(),
            outcome=str(outcome),
            permissions=_permission_values(permissions),
            resource_type=str(resource_type) if resource_type else None,
            resource_id_hash=(
                hash_resource_id(resource_id) if resource_id is not None else None
            ),
        )

    def as_dict(self) -> dict[str, object]:
        return {
            "event_type": self.event_type,
            "subject": self.subject,
            "role": self.role,
            "auth_type": self.auth_type,
            "route": self.route,
            "method": self.method,
            "outcome": self.outcome,
            "permissions": list(self.permissions),
            "resource_type": self.resource_type,
            "resource_id_hash": self.resource_id_hash,
        }


def emit_security_audit(event: SecurityAuditEvent) -> None:
    """Emit a structured event containing only the fixed sanitized schema."""
    logger.info(
        "security_audit %s",
        json.dumps(event.as_dict(), ensure_ascii=True, sort_keys=True),
    )
