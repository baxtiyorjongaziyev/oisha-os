"""Access rules for the Jon CRM dialer API (/api/crm/dialer/*).

ApiAccessMiddleware skips this namespace, so these dependencies are the only
guard. `require_dialer_access` authenticates the caller and returns an "actor"
dict; routes take the author's name from it instead of from the request body.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import Depends, Header, HTTPException, Request

from src.api.rbac import Permission, Principal, Role, has_permission
from src.services.core.crm.crm_rbac import CrmRbacGuard

logger = logging.getLogger(__name__)

# Public endpoints inside the /api/crm/dialer/ namespace. Everything else
# requires a valid seller session or an authorized web principal.
_DIALER_WEBHOOK_PATHS = frozenset({"/api/crm/dialer/incoming-call"})
_READ_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})

rbac_guard = CrmRbacGuard()


def _actor_from_principal(principal: Principal, method: str) -> Dict[str, Any]:
    """Web/API principal: apply the platform permission matrix to the dialer."""
    if method.upper() in _READ_METHODS:
        allowed = has_permission(principal, Permission.LEAD_READ_ALL) or has_permission(
            principal, Permission.LEAD_READ_ASSIGNED
        )
    else:
        allowed = has_permission(principal, Permission.LEAD_WRITE)
    if not allowed:
        raise HTTPException(status_code=403, detail="Forbidden")
    role = "admin" if principal.role in {Role.OWNER, Role.ADMIN} else "seller"
    return {"slug": principal.subject, "name": principal.subject, "role": role}


def require_dialer_access(
    request: Request,
    x_secret: Optional[str] = Header(None, alias="X-Webhook-Secret"),
    authorization: Optional[str] = Header(None),
) -> Dict[str, Any]:
    """Router-wide guard: seller session or principal for the API, secret for the ring hook.

    A seller session wins over a principal so authored records carry the
    seller's real name; a weak-PIN session still stops here with 403.
    """
    path = request.url.path.rstrip("/")
    if not path.startswith("/api/crm/dialer"):
        return {}  # HTML shell and static assets stay public; data needs auth
    if path in _DIALER_WEBHOOK_PATHS:
        from src.api.routes.twenty_moizvonki import _verify_webhook_auth

        _verify_webhook_auth(x_secret, authorization, request.query_params.get("secret"))
        return {"slug": "moizvonki-webhook", "name": "Moizvonki", "role": "webhook"}

    from src.api.security import authorize_connection
    from src.services.core.crm.seller_auth import get_current_crm_seller

    try:
        return get_current_crm_seller(request, authorization)
    except HTTPException as exc:
        if exc.status_code != 401:
            raise
        session_error = exc

    principal = authorize_connection(request)
    if principal is None:
        raise session_error
    return _actor_from_principal(principal, request.method)


def ensure_crm_permission(actor: Dict[str, Any], action: str) -> None:
    """403 unless the actor's CRM role allows `action` (see crm_rbac.ROLES_PERMISSIONS)."""
    if not rbac_guard.can_perform(str(actor.get("role") or "seller"), action):
        raise HTTPException(
            status_code=403,
            detail={"code": "crm_permission_denied", "message": "Bu amalga ruxsatingiz yoʻq."},
        )


def require_crm_permission(action: str):
    """Route dependency: authenticated actor whose role allows `action`."""

    def check(actor: Dict[str, Any] = Depends(require_dialer_access)) -> Dict[str, Any]:
        ensure_crm_permission(actor, action)
        return actor

    return Depends(check)
