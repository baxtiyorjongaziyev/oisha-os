"""CRM Dashboard — birlashtirilgan CRM ma'lumotlari API."""
from __future__ import annotations

import asyncio
import hashlib
import logging
import os
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.api.lead_assignment import (
    apply_assignment_backfill,
    assign_lead,
    parse_assignment_map,
)
from src.api.rbac import (
    Permission,
    Principal,
    Role,
    require_any_permission,
    require_permissions,
)
from src.api.routes.state import api_state
from src.api.security_audit import SecurityAuditEvent, emit_security_audit

router = APIRouter(tags=["crm-dashboard"])
logger = logging.getLogger(__name__)
_assignment_backfill_lock = asyncio.Lock()
_assignment_backfill_signature: str | None = None


class LeadAssignmentRequest(BaseModel):
    seller_subject: str = Field(min_length=1, max_length=128)


async def _apply_configured_assignment_backfill(connection) -> int:
    """Apply one explicit mapping version once per process when requested."""
    global _assignment_backfill_signature
    raw = (os.environ.get("OISHA_LEAD_ASSIGNMENTS_JSON") or "").strip()
    if not raw or raw == "{}":
        return 0
    signature = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    if signature == _assignment_backfill_signature:
        return 0
    async with _assignment_backfill_lock:
        if signature == _assignment_backfill_signature:
            return 0
        try:
            assignments = parse_assignment_map(raw)
        except ValueError as exc:
            logger.error("[crm-dashboard] invalid OISHA_LEAD_ASSIGNMENTS_JSON")
            raise HTTPException(
                status_code=503,
                detail="Lead assignment backfill configuration is invalid",
            ) from exc
        changed = await apply_assignment_backfill(connection, assignments)
        _assignment_backfill_signature = signature
        logger.info("[crm-dashboard] applied %s lead assignment backfill rows", changed)
        return changed


@router.get("/api/crm/dashboard")
async def crm_dashboard(
    principal: Principal = require_permissions(Permission.DASHBOARD_READ),
):
    """Barcha CRM ma'lumotlarini bitta endpointdan olish."""
    result = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "amocrm": {"status": "unknown"},
        "leads": {"total": 0, "hot": 0, "warm": 0, "cold": 0},
        "deals": {"total": 0, "value": 0, "won": 0, "lost": 0},
        "tasks": {"pending": 0, "overdue": 0, "completed_today": 0},
        "contacts": {"total": 0, "new_today": 0},
    }

    try:
        amocrm = None
        if api_state.amocrm_instance:
            amocrm = api_state.amocrm_instance
        elif api_state.db_instance:
            from src.api.routes.amocrm_integration import _get_amocrm_instance

            amocrm = _get_amocrm_instance()
        if amocrm:
            result["amocrm"] = {
                "status": "configured",
                "subdomain": getattr(amocrm, "subdomain", "unknown"),
            }
    except Exception as exc:
        logger.debug("[crm-dashboard] amocrm status check failed: %s", exc)
        result["amocrm"] = {"status": "error", "error": str(exc)}

    if api_state.db_instance:
        try:
            conn = await api_state.db_instance.get_connection()
            if principal.role is Role.SELLER:
                r = await conn.execute(
                    "SELECT COUNT(*) as cnt FROM users WHERE assigned_to = ?",
                    (principal.subject,),
                )
            else:
                r = await conn.execute("SELECT COUNT(*) as cnt FROM users")
            row = await r.fetchone() if hasattr(r, "fetchone") else r.fetchone()
            if row:
                result["leads"]["total"] = (
                    row[0] if isinstance(row, tuple) else row.get("cnt", 0)
                )

            r = await conn.execute(
                "SELECT COUNT(*) as cnt FROM messages WHERE date(created_at) = date('now')"
            )
            row = await r.fetchone() if hasattr(r, "fetchone") else r.fetchone()
            if row:
                result["contacts"]["new_today"] = (
                    row[0] if isinstance(row, tuple) else row.get("cnt", 0)
                )
        except Exception as exc:
            logger.debug("[crm-dashboard] db query failed: %s", exc)

    return result


def _lead_query(principal: Principal) -> tuple[str, tuple[str, ...]]:
    select = (
        "SELECT user_id, first_name AS name, intent, region, business_type, "
        "created_at, assigned_to FROM users "
    )
    if principal.role is Role.SELLER:
        return (
            select + "WHERE assigned_to = ? ORDER BY created_at DESC LIMIT 50",
            (principal.subject,),
        )
    return select + "ORDER BY created_at DESC LIMIT 50", ()


@router.get("/api/crm/leads")
async def crm_leads(
    principal: Principal = require_any_permission(
        Permission.LEAD_READ_ALL,
        Permission.LEAD_READ_ASSIGNED,
    ),
):
    """Leadlar ro'yxati."""
    leads = []
    if api_state.db_instance:
        try:
            conn = await api_state.db_instance.get_connection()
            sql, params = _lead_query(principal)
            r = await conn.execute(sql, params)
            rows = await r.fetchall() if hasattr(r, "fetchall") else r.fetchall()
            for row in rows or []:
                if isinstance(row, dict):
                    leads.append(row)
                else:
                    leads.append(
                        {
                            "user_id": row[0],
                            "name": row[1],
                            "intent": row[2],
                            "region": row[3],
                            "business_type": row[4],
                            "created_at": str(row[5]) if row[5] else None,
                            "assigned_to": row[6],
                        }
                    )
        except Exception as exc:
            logger.debug("[crm-dashboard] leads query failed: %s", exc)

    return {"leads": leads, "total": len(leads)}


@router.post("/api/crm/lead-assignments/backfill")
async def backfill_lead_assignments(
    principal: Principal = require_permissions(Permission.USERS_MANAGE_LIMITED),
):
    """Apply the deployment-controlled existing-data mapping explicitly."""
    if not api_state.db_instance:
        raise HTTPException(status_code=503, detail="Database is unavailable")
    conn = await api_state.db_instance.get_connection()
    changed = await _apply_configured_assignment_backfill(conn)
    emit_security_audit(
        SecurityAuditEvent.privileged_write(
            principal=principal,
            route="/api/crm/lead-assignments/backfill",
            method="POST",
            permissions=(Permission.USERS_MANAGE_LIMITED,),
            outcome="backfilled",
            resource_type="lead_assignment_backfill",
            resource_id=f"changed:{changed}",
        )
    )
    return {"status": "completed", "changed": changed}


@router.put("/api/crm/leads/{user_id}/assignment")
async def update_lead_assignment(
    user_id: int,
    request: LeadAssignmentRequest,
    principal: Principal = require_permissions(Permission.USERS_MANAGE_LIMITED),
):
    """Assign or reassign one lead through the canonical audited write path."""
    if user_id <= 0:
        raise HTTPException(status_code=422, detail="user_id must be positive")
    if not api_state.db_instance:
        raise HTTPException(status_code=503, detail="Database is unavailable")
    conn = await api_state.db_instance.get_connection()
    changed = await assign_lead(
        conn,
        user_id=user_id,
        seller_subject=request.seller_subject,
    )
    if not changed:
        raise HTTPException(status_code=404, detail="Lead not found")
    emit_security_audit(
        SecurityAuditEvent.privileged_write(
            principal=principal,
            route=f"/api/crm/leads/{user_id}/assignment",
            method="PUT",
            permissions=(Permission.USERS_MANAGE_LIMITED,),
            outcome="assigned",
            resource_type="lead",
            resource_id=user_id,
        )
    )
    return {
        "status": "assigned",
        "user_id": user_id,
        "seller_subject": request.seller_subject.strip(),
    }
