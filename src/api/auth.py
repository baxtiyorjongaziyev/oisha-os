"""API Key Authentication — Multi-tenant support for Oisha-OS."""

from __future__ import annotations

import hashlib
import json
import logging
import secrets
import time
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field
from sqlalchemy import select

from src.database import Database
from src.settings import settings

logger = logging.getLogger(__name__)

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
api_key_query = APIKeyHeader(name="api_key", auto_error=False)


class APIKey(BaseModel):
    """API Key model."""
    id: int
    org_id: str
    name: str
    key_hash: str
    key_prefix: str
    scopes: list[str] = Field(default_factory=list)
    rate_limit: int = 1000
    rate_window_seconds: int = 60
    is_active: bool = True
    expires_at: Optional[datetime] = None
    created_at: datetime
    last_used_at: Optional[datetime] = None


class OrgContext(BaseModel):
    """Organization context for request."""
    org_id: str
    org_name: str
    api_key_id: int
    scopes: list[str]
    rate_limit: int
    rate_window: int


class APIKeyManager:
    """Manage API keys for multi-tenant access."""

    def __init__(self, db: Database):
        self.db = db

    def _hash_key(self, key: str) -> str:
        """Hash API key for storage."""
        return hashlib.sha256(key.encode()).hexdigest()

    def _generate_key(self) -> tuple[str, str]:
        """Generate new API key and prefix."""
        prefix = "osk_" + secrets.token_urlsafe(8)
        key = prefix + "_" + secrets.token_urlsafe(32)
        return key, prefix

    async def create_key(
        self,
        org_id: str,
        name: str,
        scopes: list[str] = None,
        rate_limit: int = 1000,
        rate_window_seconds: int = 60,
        expires_days: int = None
    ) -> tuple[str, APIKey]:
        """Create new API key. Returns (plain_key, key_model)."""
        plain_key, prefix = self._generate_key()
        key_hash = self._hash_key(plain_key)

        expires_at = None
        if expires_days:
            expires_at = datetime.utcnow() + timedelta(days=expires_days)

        scopes = scopes or ["read", "write"]

        query = """
            INSERT INTO api_keys (org_id, name, key_hash, key_prefix, scopes, rate_limit, rate_window_seconds, expires_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            RETURNING id
        """
        conn = await self.db.get_connection()
        result = await conn.execute(query, (
            org_id, name, key_hash, prefix,
            "[" + ",".join(f'"{s}"' for s in scopes) + "]",
            rate_limit, rate_window_seconds, expires_at
        ))
        row = await result.fetchone()
        key_id = row[0] if row else None

        key_model = APIKey(
            id=key_id,
            org_id=org_id,
            name=name,
            key_hash=key_hash,
            key_prefix=prefix,
            scopes=scopes,
            rate_limit=rate_limit,
            rate_window_seconds=rate_window_seconds,
            expires_at=expires_at,
            created_at=datetime.utcnow()
        )

        logger.info("[Auth] Created API key %s for org %s", prefix, org_id)
        return plain_key, key_model

    async def validate_key(self, key: str) -> Optional[APIKey]:
        """Validate API key and return key model."""
        if not key or not key.startswith("osk_"):
            return None

        key_hash = self._hash_key(key)

        conn = await self.db.get_connection()
        result = await conn.execute(
            """SELECT id, org_id, name, key_hash, key_prefix, scopes, rate_limit, rate_window_seconds, is_active, expires_at, created_at, last_used_at
               FROM api_keys WHERE key_hash = ? AND is_active = 1""",
            (key_hash,)
        )
        row = await result.fetchone()

        if not row:
            return None

        key_model = APIKey(
            id=row[0],
            org_id=row[1],
            name=row[2],
            key_hash=row[3],
            key_prefix=row[4],
            scopes=json.loads(row[5]) if isinstance(row[5], str) else row[5],
            rate_limit=row[6],
            rate_window_seconds=row[7],
            is_active=bool(row[8]),
            expires_at=row[9] if row[9] else None,
            created_at=row[10],
            last_used_at=row[11] if row[11] else None
        )

        # Check expiration
        if key_model.expires_at and key_model.expires_at < datetime.utcnow():
            logger.warning("[Auth] Expired API key used: %s", key_model.key_prefix)
            return None

        # Update last_used_at
        await conn.execute(
            "UPDATE api_keys SET last_used_at = ? WHERE id = ?",
            (datetime.utcnow(), key_model.id)
        )

        return key_model

    async def revoke_key(self, key_id: int, org_id: str) -> bool:
        """Revoke API key."""
        conn = await self.db.get_connection()
        result = await conn.execute(
            "UPDATE api_keys SET is_active = 0 WHERE id = ? AND org_id = ?",
            (key_id, org_id)
        )
        return result.rowcount > 0

    async def list_keys(self, org_id: str) -> list[APIKey]:
        """List API keys for organization."""
        conn = await self.db.get_connection()
        result = await conn.execute(
            """SELECT id, org_id, name, key_hash, key_prefix, scopes, rate_limit, rate_window_seconds, is_active, expires_at, created_at, last_used_at
               FROM api_keys WHERE org_id = ? ORDER BY created_at DESC""",
            (org_id,)
        )
        rows = await result.fetchall()

        keys = []
        for row in rows:
            keys.append(APIKey(
                id=row[0],
                org_id=row[1],
                name=row[2],
                key_hash=row[3],
                key_prefix=row[4],
                scopes=json.loads(row[5]) if isinstance(row[5], str) else row[5],
                rate_limit=row[6],
                rate_window_seconds=row[7],
                is_active=bool(row[8]),
                expires_at=row[9] if row[9] else None,
                created_at=row[10],
                last_used_at=row[11] if row[11] else None
            ))
        return keys


async def get_org_context(
    request: Request,
    api_key_header: str = Depends(api_key_header),
    api_key_query: str = Depends(api_key_query)
) -> OrgContext:
    """FastAPI dependency to get organization context from API key."""
    api_key = api_key_header or api_key_query

    if not api_key:
        # Fallback to legacy OISHA_API_SECRET for backward compatibility
        legacy_secret = getattr(settings, "OISHA_API_SECRET", "")
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer ") and auth_header[7:] == legacy_secret:
            return OrgContext(
                org_id="legacy",
                org_name="Legacy Internal",
                api_key_id=0,
                scopes=["admin"],
                rate_limit=10000,
                rate_window=60
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required. Use X-API-Key header or api_key query param.",
            headers={"WWW-Authenticate": "APIKey"}
        )

    db = Database()
    await db.init_instance()
    manager = APIKeyManager(db)

    key_model = await manager.validate_key(api_key)
    if not key_model:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired API key",
            headers={"WWW-Authenticate": "APIKey"}
        )

    # Get org name
    conn = await db.get_connection()
    result = await conn.execute("SELECT name FROM organizations WHERE id = ?", (key_model.org_id,))
    org_row = await result.fetchone()
    org_name = org_row[0] if org_row else key_model.org_id

    return OrgContext(
        org_id=key_model.org_id,
        org_name=org_name,
        api_key_id=key_model.id,
        scopes=key_model.scopes,
        rate_limit=key_model.rate_limit,
        rate_window=key_model.rate_window_seconds
    )


def require_scope(required_scope: str):
    """Dependency factory to require specific scope."""
    async def check_scope(ctx: OrgContext = Depends(get_org_context)) -> OrgContext:
        if required_scope not in ctx.scopes and "admin" not in ctx.scopes:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Required scope: {required_scope}"
            )
        return ctx
    return check_scope


class RateLimiter:
    """Simple in-memory rate limiter per API key."""

    def __init__(self):
        self._buckets: dict[str, list[float]] = {}

    def check_rate_limit(self, key: str, limit: int, window_seconds: int) -> bool:
        """Check if request is within rate limit."""
        now = time.time()
        if key not in self._buckets:
            self._buckets[key] = []

        # Remove old entries
        self._buckets[key] = [t for t in self._buckets[key] if now - t < window_seconds]

        if len(self._buckets[key]) >= limit:
            return False

        self._buckets[key].append(now)
        return True


_rate_limiter = RateLimiter()


async def rate_limit_dependency(ctx: OrgContext = Depends(get_org_context)) -> OrgContext:
    """Rate limit dependency."""
    key = f"ratelimit:{ctx.org_id}:{ctx.api_key_id}"
    if not _rate_limiter.check_rate_limit(key, ctx.rate_limit, ctx.rate_window):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded: {ctx.rate_limit} requests per {ctx.rate_window}s"
        )
    return ctx