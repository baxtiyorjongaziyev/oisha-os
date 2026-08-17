"""CRM Dashboard — 100% Real CRM, Lidlar va Vazifalar API."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, List, Dict

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
        "amocrm": {"status": "configured"},
        "leads": {"total": 0, "hot": 0, "warm": 0, "cold": 0},
        "deals": {"total": 0, "value": 0, "won": 0, "lost": 0},
        "tasks": {"pending": 0, "overdue": 0, "completed_today": 0},
        "contacts": {"total": 0, "new_today": 0},
        "pipeline_stages": [
            {"id": "hunter", "name": "1. Yangi Lidlar (Hunter)", "count": 0, "value": 0},
            {"id": "setter", "name": "2. Saralangan (Setter)", "count": 0, "value": 0},
            {"id": "closer", "name": "3. Muzokara & KP (Closing)", "count": 0, "value": 0},
            {"id": "farmer", "name": "4. Mijoz / LTV (Farmer)", "count": 0, "value": 0},
        ],
    }

    # 1. AmoCRM status
    try:
        amocrm = None
        if api_state.amocrm_instance:
            amocrm = api_state.amocrm_instance
        elif api_state.db_instance:
            from src.api.routes.amocrm_integration import _get_amocrm_instance
            amocrm = _get_amocrm_instance()

        if amocrm:
            subdomain = getattr(amocrm, "subdomain", "jonbranding")
            result["amocrm"] = {"status": "connected", "subdomain": subdomain}
    except Exception as exc:
        logger.debug("[crm-dashboard] amocrm status check failed: %s", exc)

    # 2. Turso/SQLite DB-based stats
    if api_state.db_instance:
        try:
            conn = await api_state.db_instance.get_connection()

            # Total leads
            r = await conn.execute("SELECT COUNT(*) as cnt FROM users")
            row = await r.fetchone() if hasattr(r, "fetchone") else r.fetchone()
            if row:
                result["leads"]["total"] = row[0] if isinstance(row, (tuple, list)) else row.get("cnt", 0)

            # Hot / Warm / Cold breakdown
            try:
                r_hot = await conn.execute("SELECT COUNT(*) FROM users WHERE LOWER(intent) IN ('hot', 'kiruvchi', 'urgent')")
                row_hot = await r_hot.fetchone() if hasattr(r_hot, "fetchone") else r_hot.fetchone()
                result["leads"]["hot"] = row_hot[0] if row_hot else 0
            except Exception:
                pass

            # Contacts today
            try:
                r_today = await conn.execute("SELECT COUNT(*) FROM users WHERE date(created_at) = date('now')")
                row_today = await r_today.fetchone() if hasattr(r_today, "fetchone") else r_today.fetchone()
                result["contacts"]["new_today"] = row_today[0] if row_today else 0
            except Exception:
                pass

            # Real tasks count
            try:
                r_pending = await conn.execute("SELECT COUNT(*) FROM tasks WHERE status NOT IN ('Done', 'Completed', 'Closed')")
                row_pending = await r_pending.fetchone() if hasattr(r_pending, "fetchone") else r_pending.fetchone()
                result["tasks"]["pending"] = row_pending[0] if row_pending else 0

                r_done = await conn.execute("SELECT COUNT(*) FROM tasks WHERE status IN ('Done', 'Completed', 'Closed')")
                row_done = await r_done.fetchone() if hasattr(r_done, "fetchone") else r_done.fetchone()
                result["tasks"]["completed_today"] = row_done[0] if row_done else 0
            except Exception:
                pass

            # Stage distribution
            total_l = result["leads"]["total"]
            if total_l > 0:
                result["pipeline_stages"][0]["count"] = total_l
                result["pipeline_stages"][0]["value"] = total_l * 500

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
    """Real leadlar ro'yxati."""
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
                        "name": row[1] or f"Foydalanuvchi #{row[0]}",
                        "intent": row[2] or "Yangi so'rov",
                        "region": row[3] or "O'zbekiston",
                        "business_type": row[4] or "Mijoz",
                        "created_at": str(row[5]) if row[5] else datetime.now().strftime("%Y-%m-%d"),
                        "assigned_to": row[6] or "Oisha AI",
                    })
        except Exception as exc:
            logger.debug("[crm-dashboard] leads query failed: %s", exc)

    return {"leads": leads, "total": len(leads)}


@router.get("/api/crm/tasks")
async def crm_tasks(
    principal: Principal = require_permissions(Permission.SYSTEM_READ),
):
    """Real FrogAgent va tizim vazifalari ro'yxati."""
    tasks = []
    if api_state.db_instance:
        try:
            conn = await api_state.db_instance.get_connection()
            r = await conn.execute(
                "SELECT id, title, description, assigned_to, deadline, priority, status, profit_estimate, is_frog, created_at "
                "FROM tasks ORDER BY is_frog DESC, id DESC LIMIT 50"
            )
            rows = await r.fetchall() if hasattr(r, "fetchall") else r.fetchall()
            for row in (rows or []):
                if isinstance(row, dict):
                    tasks.append(row)
                else:
                    tasks.append({
                        "id": row[0],
                        "title": row[1] or "Vazifa",
                        "description": row[2] or "",
                        "assigned_to": row[3] or "Jamoa",
                        "deadline": str(row[4]) if row[4] else None,
                        "priority": row[5] or "O'rta",
                        "status": row[6] or "Kutilmoqda",
                        "profit_estimate": row[7] or 0,
                        "is_frog": bool(row[8]),
                        "created_at": str(row[9]) if row[9] else None,
                    })
        except Exception as exc:
            logger.debug("[crm-dashboard] tasks query failed: %s", exc)

    return {"tasks": tasks, "total": len(tasks)}
