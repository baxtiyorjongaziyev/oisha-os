"""CRM Dashboard — birlashtirilgan CRM ma'lumotlari API."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter

from src.api.rbac import (
    Permission,
    Principal,
    Role,
    require_any_permission,
    require_permissions,
)
from src.api.routes.state import api_state

router = APIRouter(tags=["crm-dashboard"])
logger = logging.getLogger(__name__)


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

    # AmoCRM status
    try:
        amocrm = None
        if api_state.amocrm_instance:
            amocrm = api_state.amocrm_instance
        elif api_state.db_instance:
            from src.api.routes.amocrm_integration import _get_amocrm_instance
            amocrm = _get_amocrm_instance()

        if amocrm:
            result["amocrm"] = {"status": "configured", "subdomain": getattr(amocrm, "subdomain", "unknown")}
    except Exception as exc:
        logger.debug("[crm-dashboard] amocrm status check failed: %s", exc)
        result["amocrm"] = {"status": "error", "error": str(exc)}

    # DB-based stats
    if api_state.db_instance:
        try:
            conn = await api_state.db_instance.get_connection()

            # Users/leads count
            r = await conn.execute("SELECT COUNT(*) as cnt FROM users")
            row = await r.fetchone() if hasattr(r, "fetchone") else r.fetchone()
            if row:
                result["leads"]["total"] = row[0] if isinstance(row, tuple) else row.get("cnt", 0)

            # Messages today
            r = await conn.execute(
                "SELECT COUNT(*) as cnt FROM messages WHERE date(created_at) = date('now')"
            )
            row = await r.fetchone() if hasattr(r, "fetchone") else r.fetchone()
            if row:
                result["contacts"]["new_today"] = row[0] if isinstance(row, tuple) else row.get("cnt", 0)

        except Exception as exc:
            logger.debug("[crm-dashboard] db query failed: %s", exc)

    return result


def _lead_query(principal: Principal) -> tuple[str, tuple[str, ...]]:
    select = (
        "SELECT user_id, first_name AS name, intent, region, business_type, "
        "created_at, assigned_to "
        "FROM users "
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
            for row in (rows or []):
                if isinstance(row, dict):
                    leads.append(row)
                else:
                    leads.append({
                        "user_id": row[0],
                        "name": row[1],
                        "intent": row[2],
                        "region": row[3],
                        "business_type": row[4],
                        "created_at": str(row[5]) if row[5] else None,
                        "assigned_to": row[6],
                    })
        except Exception as exc:
            logger.debug("[crm-dashboard] leads query failed: %s", exc)

    return {"leads": leads, "total": len(leads)}
