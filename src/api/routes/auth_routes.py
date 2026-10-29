"""API Key Management Routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from typing import Optional

from src.api.auth import get_org_context, APIKeyManager, OrgContext, require_scope
from src.database import Database

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class CreateKeyRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    scopes: list[str] = Field(default=["read", "write"])
    rate_limit: int = Field(default=1000, ge=1, le=100000)
    rate_window_seconds: int = Field(default=60, ge=1, le=86400)
    expires_days: Optional[int] = Field(default=None, ge=1, le=3650)


class CreateKeyResponse(BaseModel):
    key: str
    key_id: int
    prefix: str
    name: str
    scopes: list[str]
    rate_limit: int
    rate_window_seconds: int
    expires_at: Optional[str] = None


class KeyInfo(BaseModel):
    key_id: int
    name: str
    prefix: str
    scopes: list[str]
    rate_limit: int
    rate_window_seconds: int
    is_active: bool
    expires_at: Optional[str] = None
    created_at: str
    last_used_at: Optional[str] = None


@router.post("/keys", response_model=CreateKeyResponse, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    request: CreateKeyRequest,
    ctx: OrgContext = Depends(require_scope("admin"))
):
    """Create new API key for organization."""
    db = Database()
    await db.init_instance()
    manager = APIKeyManager(db)

    plain_key, key_model = await manager.create_key(
        org_id=ctx.org_id,
        name=request.name,
        scopes=request.scopes,
        rate_limit=request.rate_limit,
        rate_window_seconds=request.rate_window_seconds,
        expires_days=request.expires_days
    )

    return CreateKeyResponse(
        key=plain_key,
        key_id=key_model.id,
        prefix=key_model.key_prefix,
        name=key_model.name,
        scopes=key_model.scopes,
        rate_limit=key_model.rate_limit,
        rate_window_seconds=key_model.rate_window_seconds,
        expires_at=key_model.expires_at.isoformat() if key_model.expires_at else None
    )


@router.get("/keys", response_model=list[KeyInfo])
async def list_api_keys(
    ctx: OrgContext = Depends(require_scope("admin"))
):
    """List API keys for organization."""
    db = Database()
    await db.init_instance()
    manager = APIKeyManager(db)

    keys = await manager.list_keys(ctx.org_id)

    return [
        KeyInfo(
            key_id=k.id,
            name=k.name,
            prefix=k.key_prefix,
            scopes=k.scopes,
            rate_limit=k.rate_limit,
            rate_window_seconds=k.rate_window_seconds,
            is_active=k.is_active,
            expires_at=k.expires_at.isoformat() if k.expires_at else None,
            created_at=k.created_at.isoformat(),
            last_used_at=k.last_used_at.isoformat() if k.last_used_at else None
        )
        for k in keys
    ]


@router.delete("/keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_api_key(
    key_id: int,
    ctx: OrgContext = Depends(require_scope("admin"))
):
    """Revoke API key."""
    db = Database()
    await db.init_instance()
    manager = APIKeyManager(db)

    success = await manager.revoke_key(key_id, ctx.org_id)
    if not success:
        raise HTTPException(status_code=404, detail="Key not found")


@router.get("/me", response_model=OrgContext)
async def get_current_org(ctx: OrgContext = Depends(get_org_context)):
    """Get current organization context."""
    return ctx