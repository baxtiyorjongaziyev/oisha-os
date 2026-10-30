"""Multi-tenant Workspace and Project Registry for CAPI Platform.

Allows targetologists and clients to register multiple independent projects,
each with their own Meta Pixel / Dataset, access token, amoCRM pipeline,
and webhook intake secrets, while keeping data strictly isolated.
"""
from __future__ import annotations

import datetime
import secrets
from typing import Any, Dict, List, Optional


def _pool():
    from src.database_pool import db_pool
    return db_pool


def now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


async def ensure_project_tables():
    await _pool().execute(
        "CREATE TABLE IF NOT EXISTS capi_projects ("
        "id TEXT PRIMARY KEY, "
        "name TEXT NOT NULL, "
        "owner_id TEXT NOT NULL, "
        "dataset_id TEXT NOT NULL DEFAULT '', "
        "access_token TEXT NOT NULL DEFAULT '', "
        "test_code TEXT NOT NULL DEFAULT '', "
        "ad_account_id TEXT NOT NULL DEFAULT '', "
        "crm_pipeline_id TEXT NOT NULL DEFAULT '', "
        "ingest_secret TEXT NOT NULL, "
        "monthly_limit INTEGER NOT NULL DEFAULT 2000, "
        "usage_count INTEGER NOT NULL DEFAULT 0, "
        "is_active INTEGER NOT NULL DEFAULT 1, "
        "created_at TEXT NOT NULL, "
        "updated_at TEXT NOT NULL)"
    )
    # Default Jon Branding project seed if table is empty
    existing = await _pool().execute("SELECT COUNT(*) as cnt FROM capi_projects")
    if existing and existing[0]["cnt"] == 0:
        stamp = now()
        await _pool().execute(
            "INSERT INTO capi_projects "
            "(id, name, owner_id, dataset_id, ad_account_id, ingest_secret, monthly_limit, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                "default",
                "Jon Branding (Asosiy)",
                "system",
                "1134785364752294",
                "act_370591433710957",
                secrets.token_hex(16),
                100000,
                stamp,
                stamp,
            ],
        )
    else:
        # Ensure default project has ad_account_id populated
        await _pool().execute(
            "UPDATE capi_projects SET ad_account_id = 'act_370591433710957' WHERE id = 'default' AND (ad_account_id IS NULL OR ad_account_id = '')"
        )
    await _pool().commit()


async def create_project(
    *,
    name: str,
    owner_id: str,
    dataset_id: str = "",
    access_token: str = "",
    ad_account_id: str = "",
    crm_pipeline_id: str = "",
) -> Dict[str, Any]:
    await ensure_project_tables()
    proj_id = "proj_" + secrets.token_hex(6)
    ingest_sec = "capi_" + secrets.token_hex(16)
    stamp = now()
    await _pool().execute(
        "INSERT INTO capi_projects "
        "(id, name, owner_id, dataset_id, access_token, ad_account_id, crm_pipeline_id, ingest_secret, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            proj_id,
            name.strip(),
            str(owner_id).strip(),
            dataset_id.strip(),
            access_token.strip(),
            ad_account_id.strip(),
            crm_pipeline_id.strip(),
            ingest_sec,
            stamp,
            stamp,
        ],
    )
    await _pool().commit()
    return await get_project(proj_id) or {}


async def get_project(project_id: str) -> Optional[Dict[str, Any]]:
    await ensure_project_tables()
    rows = await _pool().execute(
        "SELECT id, name, owner_id, dataset_id, test_code, ad_account_id, "
        "crm_pipeline_id, ingest_secret, monthly_limit, usage_count, is_active, "
        "CASE WHEN access_token != '' THEN 1 ELSE 0 END AS has_token, "
        "created_at, updated_at FROM capi_projects WHERE id = ?",
        [project_id],
    )
    return dict(rows[0]) if rows else None


async def get_project_by_secret(ingest_secret: str) -> Optional[Dict[str, Any]]:
    await ensure_project_tables()
    rows = await _pool().execute(
        "SELECT id, name, owner_id, dataset_id, access_token, test_code, "
        "ad_account_id, crm_pipeline_id, ingest_secret, monthly_limit, usage_count, "
        "is_active FROM capi_projects WHERE ingest_secret = ? AND is_active = 1",
        [ingest_secret],
    )
    return dict(rows[0]) if rows else None


async def get_project_by_pipeline(pipeline_id: str) -> Optional[Dict[str, Any]]:
    await ensure_project_tables()
    clean = str(pipeline_id or "").strip()
    if not clean:
        return None
    rows = await _pool().execute(
        "SELECT id, name, owner_id, dataset_id, access_token, test_code, "
        "ad_account_id, crm_pipeline_id, ingest_secret, monthly_limit, usage_count, "
        "is_active FROM capi_projects WHERE crm_pipeline_id = ? AND is_active = 1",
        [clean],
    )
    return dict(rows[0]) if rows else None


async def list_projects_for_user(user_id: str, is_admin: bool = False) -> List[Dict[str, Any]]:
    await ensure_project_tables()
    if is_admin:
        rows = await _pool().execute(
            "SELECT id, name, owner_id, dataset_id, ad_account_id, "
            "crm_pipeline_id, ingest_secret, monthly_limit, usage_count, is_active, "
            "CASE WHEN access_token != '' THEN 1 ELSE 0 END AS has_token, "
            "created_at FROM capi_projects ORDER BY (id = 'default') DESC, created_at DESC"
        )
    else:
        rows = await _pool().execute(
            "SELECT id, name, owner_id, dataset_id, ad_account_id, "
            "crm_pipeline_id, ingest_secret, monthly_limit, usage_count, is_active, "
            "CASE WHEN access_token != '' THEN 1 ELSE 0 END AS has_token, "
            "created_at FROM capi_projects WHERE owner_id = ? "
            "ORDER BY created_at DESC",
            [str(user_id)],
        )
        if not rows and str(user_id or "").strip() not in ("", "anonymous"):
            created = await create_project(name="Mening Loyiham #1", owner_id=str(user_id))
            return [created] if created else []
    return [dict(r) for r in rows]


async def increment_project_usage(project_id: str) -> int:
    await _pool().execute(
        "UPDATE capi_projects SET usage_count = usage_count + 1, updated_at = ? WHERE id = ?",
        [now(), project_id],
    )
    await _pool().commit()
    proj = await get_project(project_id)
    return proj["usage_count"] if proj else 0


async def update_project_settings(
    project_id: str,
    *,
    dataset_id: Optional[str] = None,
    access_token: Optional[str] = None,
    ad_account_id: Optional[str] = None,
    crm_pipeline_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    await ensure_project_tables()
    proj = await get_project(project_id)
    if not proj:
        return None
    updates = []
    params = []
    if dataset_id is not None:
        updates.append("dataset_id = ?")
        params.append(dataset_id.strip())
    if access_token is not None:
        updates.append("access_token = ?")
        params.append(access_token.strip())
    if ad_account_id is not None:
        updates.append("ad_account_id = ?")
        params.append(ad_account_id.strip())
    if crm_pipeline_id is not None:
        updates.append("crm_pipeline_id = ?")
        params.append(crm_pipeline_id.strip())
    updates.append("updated_at = ?")
    params.append(now())
    params.append(project_id)
    await _pool().execute(
        f"UPDATE capi_projects SET {', '.join(updates)} WHERE id = ?",  # nosec B608
        params,
    )
    await _pool().commit()
    return await get_project(project_id)

