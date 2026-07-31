"""Central authorization boundary for Oisha's private API surfaces.

Accepted credentials:
- exact ``Bearer OISHA_API_SECRET`` for trusted service-to-service calls;
- an owner/admin JWT signed with a strong ``JWT_SECRET`` (or
  ``OISHA_API_SECRET`` as a temporary non-Telegram fallback);
- an authenticated Nginx Basic Auth identity forwarded from a loopback proxy.

The policy deliberately fails closed when secrets are missing or too short.
"""

from __future__ import annotations

import hmac
import json
import os
from typing import Any, Optional

import jwt
from fastapi import Depends, HTTPException
from starlette.requests import HTTPConnection
from starlette.responses import JSONResponse

from src.api.rbac import Principal, Role
import logging
logger = logging.getLogger(__name__)

_ALLOWED_SESSION_ROLES = frozenset({Role.OWNER, Role.ADMIN, Role.SELLER, Role.VIEWER})
_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1", "localhost", "testclient"})
_MIN_SESSION_SECRET_BYTES = 32
_PROTECTED_PREFIXES = (
    "/api/",
    "/internal/",
    "/mcp",
    "/telegram-mcp",
    "/client",
    "/ws/live",
)
_PUBLIC_PATHS = frozenset(
    {
        "/api/auth/telegram/login",
        "/api/auth/telegram/callback",
        "/api/auth/airtable/callback",
        # Meta must reach this exact verification/event endpoint. The route
        # validates the verify token (GET) and x-hub-signature-256 (POST).
        "/api/instagram/webhook",
    }
)


def _clean(value: Any) -> str:
    if value is None:
        return ""
    getter = getattr(value, "get_secret_value", None)
    if callable(getter):
        value = getter()
    return str(value).lstrip("\ufeff").strip()


def _is_strong_session_secret(value: str) -> bool:
    return len(value.encode("utf-8")) >= _MIN_SESSION_SECRET_BYTES


def _session_secret() -> str:
    from src.settings import settings
    """Use a strong non-Telegram key for browser sessions."""
    candidate = _clean(
        getattr(settings, "JWT_SECRET", "") or getattr(settings, "OISHA_API_SECRET", "")
    )
    return candidate if _is_strong_session_secret(candidate) else ""


def authorize_request_values(
    *,
    authorization: str,
    api_secret: str,
    proxy_user: str,
    client_host: str,
    session_token: str,
    jwt_secret: str,
    service_tokens_json: str = "",
    proxy_role_map_json: str = "",
) -> Optional[Principal]:
    """Return a normalized principal when the supplied credentials are trusted."""

    expected_api_secret = _clean(api_secret)
    supplied_authorization = _clean(authorization)
    if expected_api_secret and hmac.compare_digest(
        supplied_authorization, f"Bearer {expected_api_secret}"
    ):
        return Principal(subject="api-secret", role=Role.OWNER, auth_type="bearer")

    bearer_prefix = "Bearer "
    if supplied_authorization.startswith(bearer_prefix):
        supplied_token = supplied_authorization[len(bearer_prefix) :]
        try:
            service_tokens = json.loads(_clean(service_tokens_json) or "{}")
        except (TypeError, ValueError):
            service_tokens = {}
        service = service_tokens.get(supplied_token) if isinstance(service_tokens, dict) else None
        if isinstance(service, dict):
            subject = _clean(service.get("subject"))
            scopes = service.get("scopes")
            if subject and isinstance(scopes, list) and all(
                isinstance(scope, str) and scope.strip() for scope in scopes
            ):
                return Principal(
                    subject=subject,
                    role=Role.SERVICE,
                    auth_type="bearer",
                    scopes=frozenset(scope.strip() for scope in scopes),
                )

    forwarded_user = _clean(proxy_user)
    normalized_host = _clean(client_host).lower()
    if forwarded_user and normalized_host in _LOOPBACK_HOSTS:
        try:
            role_map = json.loads(_clean(proxy_role_map_json) or "{}")
        except (TypeError, ValueError):
            role_map = {}
        mapped_role = role_map.get(forwarded_user) if isinstance(role_map, dict) else None
        try:
            role = Role(_clean(mapped_role).lower())
        except ValueError:
            return None
        if role is Role.SERVICE:
            return None
        return Principal(
            subject=forwarded_user,
            role=role,
            auth_type="trusted_proxy",
        )

    dedicated_jwt_secret = _clean(jwt_secret)
    token = _clean(session_token)
    if not _is_strong_session_secret(dedicated_jwt_secret) or not token:
        return None

    try:
        payload = jwt.decode(token, dedicated_jwt_secret, algorithms=["HS256"])
    except Exception:
        logger.error("Exception handled in %s", __name__, exc_info=True)
        return None

    role_value = _clean(payload.get("role")).lower()
    subject = _clean(payload.get("sub"))
    try:
        role = Role(role_value)
    except ValueError:
        return None
    if role not in _ALLOWED_SESSION_ROLES or not subject:
        return None

    return Principal(subject=subject, role=role, auth_type="session")


def authorize_connection(connection: HTTPConnection) -> Optional[Principal]:
    from src.settings import settings

    client_host = connection.client.host if connection.client else ""
    return authorize_request_values(
        authorization=connection.headers.get("Authorization", ""),
        api_secret=getattr(settings, "OISHA_API_SECRET", "") or "",
        proxy_user=connection.headers.get("X-Oisha-Authenticated-User", ""),
        client_host=client_host,
        session_token=connection.cookies.get("oisha_token", ""),
        jwt_secret=_session_secret(),
        service_tokens_json=getattr(settings, "OISHA_SERVICE_TOKENS_JSON", "") or "",
        proxy_role_map_json=getattr(settings, "OISHA_PROXY_ROLE_MAP_JSON", "") or "",
    )


def require_admin_access(connection: HTTPConnection) -> Principal:
    principal = authorize_connection(connection)
    if principal is None:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return principal


def is_protected_path(path: str) -> bool:
    normalized = path.rstrip("/") or "/"
    if normalized in _PUBLIC_PATHS:
        return False
    return any(
        normalized == prefix.rstrip("/") or normalized.startswith(prefix)
        for prefix in _PROTECTED_PREFIXES
    )


def _secure_session_cookie_headers(headers):
    secured = []
    for name, value in headers:
        if name.lower() == b"set-cookie" and value.lower().startswith(b"oisha_token="):
            lower_value = value.lower()
            if b"; secure" not in lower_value:
                value += b"; Secure"
            if b"; httponly" not in lower_value:
                value += b"; HttpOnly"
        secured.append((name, value))
    return secured


class ApiAccessMiddleware:
    """ASGI middleware protecting HTTP, SSE and WebSocket private surfaces."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        scope_type = scope.get("type")
        if scope_type not in {"http", "websocket"}:
            await self.app(scope, receive, send)
            return

        async def secure_send(message):
            if message.get("type") == "http.response.start":
                message = dict(message)
                message["headers"] = _secure_session_cookie_headers(
                    list(message.get("headers", []))
                )
            await send(message)

        downstream_send = secure_send if scope_type == "http" else send

        if scope_type == "http" and scope.get("method") == "OPTIONS":
            await self.app(scope, receive, downstream_send)
            return

        path = scope.get("path", "")
        if not is_protected_path(path):
            await self.app(scope, receive, downstream_send)
            return

        connection = HTTPConnection(scope)
        if authorize_connection(connection) is not None:
            await self.app(scope, receive, downstream_send)
            return

        if scope_type == "websocket":
            await send({"type": "websocket.close", "code": 4401, "reason": "Unauthorized"})
            return

        response = JSONResponse({"detail": "Unauthorized"}, status_code=401)
        await response(scope, receive, downstream_send)


AdminAccess = Depends(require_admin_access)
