"""Self-hosted Callmaster API routes."""
from __future__ import annotations

import hashlib
import hmac
import json
import os
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field
from starlette.requests import HTTPConnection

from src.api.rbac import Permission, Principal, Role, has_permission
from src.api.security import authorize_connection
from src.services.core.callmaster_service import CallmasterStore


router = APIRouter(prefix="/api/callmaster", tags=["callmaster"])


class CampaignCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    audio_url: str = Field(min_length=1, max_length=1000)
    description: str = ""
    max_parallel_calls: int = Field(default=10, ge=1, le=1000)
    retry_limit: int = Field(default=1, ge=0, le=10)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ContactImportItem(BaseModel):
    phone: str
    name: str = ""
    lead_id: Optional[int] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ContactImportRequest(BaseModel):
    contacts: List[ContactImportItem] = Field(min_length=1, max_length=5000)


class LaunchRequest(BaseModel):
    provider: str = Field(default="local", max_length=64)


def _store() -> CallmasterStore:
    return CallmasterStore()


def _api_secret() -> str:
    return (os.getenv("CALLMASTER_API_SECRET") or os.getenv("OISHA_API_SECRET") or "").strip()


def _webhook_secret() -> str:
    return (os.getenv("CALLMASTER_WEBHOOK_SECRET") or _api_secret()).strip()


def _require_admin(auth_header: str) -> None:
    secret = _api_secret()
    if not secret:
        raise HTTPException(status_code=503, detail="CALLMASTER_API_SECRET is not configured")
    if not hmac.compare_digest(auth_header or "", f"Bearer {secret}"):
        raise HTTPException(status_code=401, detail="Unauthorized")


def _require_callmaster_permission(permission: Permission):
    async def dependency(connection: HTTPConnection) -> Principal:
        principal = authorize_connection(connection)
        if principal is None:
            authorization = connection.headers.get("Authorization", "")
            try:
                _require_admin(authorization)
            except HTTPException:
                raise HTTPException(status_code=401, detail="Unauthorized") from None
            principal = Principal(
                subject="callmaster-api-secret",
                role=Role.OWNER,
                auth_type="bearer",
            )
        if not has_permission(principal, permission):
            raise HTTPException(status_code=403, detail="Forbidden")
        return principal

    dependency.__oisha_permissions__ = (permission.value,)
    dependency.__oisha_permission_mode__ = "all"
    return Depends(dependency)


def _verify_webhook(
    *,
    raw_body: bytes,
    signature: str,
    shared_secret_header: str,
) -> None:
    secret = _webhook_secret()
    allow_unsigned = os.getenv("CALLMASTER_ALLOW_UNSIGNED_WEBHOOKS", "").lower() in {"1", "true", "yes"}
    if not secret:
        if allow_unsigned:
            return
        raise HTTPException(status_code=503, detail="CALLMASTER_WEBHOOK_SECRET is not configured")

    if shared_secret_header and hmac.compare_digest(shared_secret_header, secret):
        return

    if signature.startswith("sha256="):
        expected = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
        if hmac.compare_digest(signature, f"sha256={expected}"):
            return

    raise HTTPException(status_code=401, detail="Invalid webhook signature")


@router.post(
    "/campaigns",
    dependencies=[_require_callmaster_permission(Permission.CALL_WRITE)],
)
async def create_campaign(
    body: CampaignCreateRequest,
):
    campaign = _store().create_campaign(**body.model_dump())
    return {"ok": True, "campaign": campaign}


@router.post(
    "/campaigns/{campaign_id}/contacts",
    dependencies=[_require_callmaster_permission(Permission.CALL_WRITE)],
)
async def import_contacts(
    campaign_id: str,
    body: ContactImportRequest,
):
    try:
        result = _store().add_contacts(
            campaign_id,
            [item.model_dump() for item in body.contacts],
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="campaign_not_found") from None
    return {"ok": True, **result}


@router.post(
    "/campaigns/{campaign_id}/launch",
    dependencies=[_require_callmaster_permission(Permission.CALL_WRITE)],
)
async def launch_campaign(
    campaign_id: str,
    body: LaunchRequest = LaunchRequest(),
):
    try:
        result = _store().launch_campaign(campaign_id, provider=body.provider)
    except KeyError:
        raise HTTPException(status_code=404, detail="campaign_not_found") from None
    return {"ok": True, **result}


@router.get(
    "/campaigns/{campaign_id}",
    dependencies=[_require_callmaster_permission(Permission.CALL_READ_ALL)],
)
async def get_campaign(
    campaign_id: str,
):
    try:
        result = _store().get_campaign(campaign_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="campaign_not_found") from None
    return {"ok": True, **result}


@router.post("/webhook")
async def callmaster_webhook(
    request: Request,
    x_callmaster_signature: str = Header(default=""),
    x_callmaster_webhook_secret: str = Header(default=""),
):
    raw_body = await request.body()
    _verify_webhook(
        raw_body=raw_body,
        signature=x_callmaster_signature,
        shared_secret_header=x_callmaster_webhook_secret,
    )
    try:
        payload = json.loads(raw_body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="invalid_json") from None
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="invalid_payload")
    result = _store().record_webhook_event(payload)
    return {"ok": True, **result}

