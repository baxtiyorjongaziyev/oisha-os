"""Typed, fail-closed authorization policy for Oisha API surfaces."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Iterable, Mapping, Sequence

from fastapi import Depends, HTTPException
from starlette.requests import HTTPConnection


class Role(StrEnum):
    OWNER = "owner"
    ADMIN = "admin"
    SELLER = "seller"
    VIEWER = "viewer"
    SERVICE = "service"


class Permission(StrEnum):
    DASHBOARD_READ = "dashboard:read"
    LEAD_READ_ALL = "lead:read:all"
    LEAD_READ_ASSIGNED = "lead:read:assigned"
    LEAD_WRITE = "lead:write"
    CALL_READ_ALL = "call:read:all"
    CALL_READ_OWN = "call:read:own"
    CALL_WRITE = "call:write"
    TRANSCRIPT_READ_ALL = "transcript:read:all"
    TRANSCRIPT_READ_OWN = "transcript:read:own"
    FINANCE_READ = "finance:read"
    FINANCE_WRITE = "finance:write"
    TELEGRAM_READ = "telegram:read"
    TELEGRAM_SEND = "telegram:send"
    MCP_READ = "mcp:read"
    MCP_WRITE = "mcp:write"
    USERS_MANAGE_LIMITED = "users:manage:limited"
    USERS_MANAGE_ALL = "users:manage:all"
    SECRETS_MANAGE = "secrets:manage"
    SYSTEM_READ = "system:read"
    SYSTEM_DEPLOY = "system:deploy"
    AUDIT_READ_ALL = "audit:read:all"
    AUDIT_READ_OWN = "audit:read:own"


@dataclass(frozen=True, slots=True)
class Principal:
    subject: str
    role: Role
    auth_type: str
    scopes: frozenset[str] = field(default_factory=frozenset)


_ALL_PERMISSIONS = frozenset(Permission)
ROLE_PERMISSIONS: Mapping[Role, frozenset[Permission]] = {
    Role.OWNER: _ALL_PERMISSIONS,
    Role.ADMIN: frozenset(
        {
            Permission.DASHBOARD_READ,
            Permission.LEAD_READ_ALL,
            Permission.LEAD_WRITE,
            Permission.CALL_READ_ALL,
            Permission.CALL_WRITE,
            Permission.TRANSCRIPT_READ_ALL,
            Permission.FINANCE_READ,
            Permission.FINANCE_WRITE,
            Permission.TELEGRAM_READ,
            Permission.TELEGRAM_SEND,
            Permission.MCP_READ,
            Permission.MCP_WRITE,
            Permission.USERS_MANAGE_LIMITED,
            Permission.SYSTEM_READ,
            Permission.AUDIT_READ_ALL,
        }
    ),
    Role.SELLER: frozenset(
        {
            Permission.DASHBOARD_READ,
            Permission.LEAD_READ_ASSIGNED,
            Permission.LEAD_WRITE,
            Permission.CALL_READ_OWN,
            Permission.TRANSCRIPT_READ_OWN,
            Permission.AUDIT_READ_OWN,
        }
    ),
    Role.VIEWER: frozenset({Permission.DASHBOARD_READ}),
    Role.SERVICE: frozenset(),
}


def has_permission(principal: Principal, permission: Permission) -> bool:
    if principal.role is Role.SERVICE:
        return permission.value in principal.scopes
    return permission in ROLE_PERMISSIONS.get(principal.role, frozenset())


def _dependency(required: Sequence[Permission], *, require_all: bool):
    async def authorize(connection: HTTPConnection) -> Principal:
        # Local import avoids an import cycle: security owns authentication,
        # while this module owns authorization.
        from src.api.security import authorize_connection

        principal = authorize_connection(connection)
        if principal is None:
            raise HTTPException(status_code=401, detail="Unauthorized")
        checks = (has_permission(principal, permission) for permission in required)
        allowed = all(checks) if require_all else any(checks)
        if not allowed:
            raise HTTPException(status_code=403, detail="Forbidden")
        return principal

    authorize.__oisha_permissions__ = tuple(item.value for item in required)
    authorize.__oisha_permission_mode__ = "all" if require_all else "any"
    return Depends(authorize)


def require_permissions(*required: Permission):
    if not required:
        raise ValueError("At least one permission is required")
    return _dependency(required, require_all=True)


def require_any_permission(*required: Permission):
    if not required:
        raise ValueError("At least one permission is required")
    return _dependency(required, require_all=False)


def owns_resource(
    principal: Principal,
    resource: Mapping[str, Any],
    *,
    owner_field: str,
) -> bool:
    if principal.role in {Role.OWNER, Role.ADMIN}:
        return True
    if principal.role is not Role.SELLER:
        return False
    owner = resource.get(owner_field)
    return owner is not None and str(owner) == principal.subject


def scope_owned_rows(
    principal: Principal,
    rows: Iterable[Mapping[str, Any]],
    *,
    owner_field: str,
) -> list[Mapping[str, Any]]:
    materialized = list(rows)
    if principal.role in {Role.OWNER, Role.ADMIN}:
        return materialized
    if principal.role is not Role.SELLER:
        return []
    return [
        row
        for row in materialized
        if row.get(owner_field) is not None
        and str(row.get(owner_field)) == principal.subject
    ]
