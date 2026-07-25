"""Central authorization boundary for Oisha's private API surfaces.

Accepted credentials:
- exact ``Bearer OISHA_API_SECRET`` for trusted service-to-service calls;
- an owner/admin JWT signed with ``JWT_SECRET`` (or ``OISHA_API_SECRET`` as a
  temporary non-Telegram fallback);
- an authenticated Nginx Basic Auth identity forwarded from a loopback proxy.

The policy deliberately fails closed when secrets are missing.
"""

from __future__ import annotations

import hmac
import os
from typing import Any, Optional

import jwt
from fastapi import Depends, HTTPException
from starlette.requests import HTTPConnection
from starlette.responses import JSONResponse

_ALLOWED_SESSION_ROLES = frozenset({"owner", "admin"})
_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1", "localhost", "testclient"})
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
    }
)


def _clean(value: Any) -> str:
    if value is None:
        return ""
    getter = getattr(value, "get_secret_value", None)
    if callable(getter):
        value = getter()
    return str(value).lstrip("\ufeff").strip()


def _session_secret() -> str:
    """Use a dedicated JWT key, never the Telegram bot token."""
    return _clean(os.environ.get("JWT_SECRET") or os.environ.get("OISHA_API_SECRET"))


def authorize_request_values(
    *,
    authorization: str,
    api_secret: str,
    proxy_user: str,
    client_host: str,
    session_token: str,
    jwt_secret: str,
) -> Optional[dict[str, str]]:
    """Return a normalized principal when the supplied credentials are trusted."""

    expected_api_secret = _clean(api_secret)
    supplied_authorization = _clean(authorization)
    if expected_api_secret and hmac.compare_digest(
        supplied_authorization, f"Bearer {expected_api_secret}"
    ):
        return {"auth_type": "bearer", "role": "owner", "subject": "api-secret"}

    forwarded_user = _clean(proxy_user)
    normalized_host = _clean(client_host).lower()
    if forwarded_user and normalized_host in _LOOPBACK_HOSTS:
        return {
            "auth_type": "trusted_proxy",
            "role": "admin",
            "subject": forwarded_user,
        }

    dedicated_jwt_secret = _clean(jwt_secret)
    token = _clean(session_token)
    if not dedicated_jwt_secret or not token:
        return None

    try:
        payload = jwt.decode(token, dedicated_jwt_secret, algorithms=["HS256"])
    except Exception:
        return None

    role = _clean(payload.get("role")).lower()
    subject = _clean(payload.get("sub"))
    if role not in _ALLOWED_SESSION_ROLES or not subject:
        return None

    return {"auth_type": "session", "role": role, "subject": subject}


def authorize_connection(connection: HTTPConnection) -> Optional[dict[str, str]]:
    client_host = connection.client.host if connection.client else ""
    return authorize_request_values(
        authorization=connection.headers.get("Authorization", ""),
        api_secret=os.environ.get("OISHA_API_SECRET", ""),
        proxy_user=connection.headers.get("X-Oisha-Authenticated-User", ""),
        client_host=client_host,
        session_token=connection.cookies.get("oisha_token", ""),
        jwt_secret=_session_secret(),
    )


def require_admin_access(connection: HTTPConnection) -> dict[str, str]:
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
