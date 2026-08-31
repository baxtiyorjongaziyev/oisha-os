"""System dashboard API routes for operational and technical metrics."""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Query
from src.api.rbac import Permission, require_permissions
from src.api.routes.state import api_state
from src.time_utils import get_local_now
from src.settings import settings

router = APIRouter(prefix="/api/system", tags=["system-dashboard"])
logger = logging.getLogger(__name__)


@router.get("/metrics", dependencies=[require_permissions(Permission.SYSTEM_READ)])
async def get_system_metrics():
    """Tizimning to'liq operatsion va texnik metrikalari."""
    from src.services.core.agent_runtime import get_runtime_context

    runtime = get_runtime_context()
    signals_res = await get_system_signals()

    db_connected = api_state.db_instance is not None
    amocrm_connected = api_state.amocrm_instance is not None
    userbot_authorized = runtime.get("userbot_authorized", False)

    users_count = 0
    tasks_count = 0
    if api_state.db_instance:
        try:
            conn = await api_state.db_instance.get_connection()
            r_users = await conn.execute("SELECT COUNT(*) FROM users")
            row_u = await r_users.fetchone() if hasattr(r_users, "fetchone") else r_users.fetchone()
            users_count = row_u[0] if row_u else 0

            r_tasks = await conn.execute("SELECT COUNT(*) FROM tasks")
            row_t = await r_tasks.fetchone() if hasattr(r_tasks, "fetchone") else r_tasks.fetchone()
            tasks_count = row_t[0] if row_t else 0
        except Exception:
            pass

    return {
        "timestamp": get_local_now().isoformat(),
        "status": "operational",
        "system": {
            "environment": getattr(settings, "ENVIRONMENT", "production"),
            "python_version": runtime.get("python_version"),
            "health_score": signals_res.get("health_score", 100),
        },
        "database": {"connected": db_connected, "users_count": users_count, "tasks_count": tasks_count},
        "integrations": {"amocrm": amocrm_connected, "userbot": userbot_authorized, "telegram_bot": bool(getattr(settings, "BOT_TOKEN", None))},
        "pipeline_health": signals_res.get("signals", []),
    }


@router.post("/crm-audit", dependencies=[require_permissions(Permission.LEAD_WRITE)])
async def run_crm_audit(limit: int = Query(20, ge=1, le=100)):
    """AmoCRM dagi aktiv sdelkalarni PipelineAuditor orqali AI tahlil qilish."""
    if api_state.crm_audit_running:
        raise HTTPException(status_code=409, detail="CRM audit is already running.")
    if not api_state.amocrm_instance:
        raise HTTPException(status_code=503, detail="AmoCRM client is not initialized.")

    api_state.crm_audit_running = True
    try:
        from src.services.core.pipeline.auditor import PipelineAuditor
        auditor = PipelineAuditor(amocrm=api_state.amocrm_instance, airtable=api_state.airtable_instance, db=api_state.db_instance)
        return await auditor.audit_all_deals(limit=limit)
    finally:
        api_state.crm_audit_running = False


def _check_telegram_signal(runtime: Dict[str, Any]) -> Dict[str, Any]:
    userbot_auth = runtime.get("userbot_authorized", False)
    bot_token_set = bool(getattr(settings, "BOT_TOKEN", None))
    if userbot_auth and bot_token_set:
        return {"pipeline": "telegram_dual_head", "name": "Telegram Control Plane (@jonairobot + Telethon)", "status": "healthy", "severity": "info", "message": "Userbot va Bot API to'liq ulangan, 24/7 jonli rejimda.", "action": None}
    return {"pipeline": "telegram_dual_head", "name": "Telegram Control Plane", "status": "degraded", "severity": "critical", "message": "Userbot sessiyasi yoki Bot Token uzilgan.", "action": "Oracle VM'da session keeper va BOT_TOKEN'ni tekshirish."}


async def _check_amocrm_signal() -> Dict[str, Any]:
    amocrm_conf = bool(getattr(settings, "AMOCRM_SUBDOMAIN", None))
    leads_count = 0
    if api_state.db_instance:
        try:
            conn = await api_state.db_instance.get_connection()
            r = await conn.execute("SELECT COUNT(*) FROM users")
            row = await r.fetchone() if hasattr(r, "fetchone") else r.fetchone()
            leads_count = row[0] if row else 0
        except Exception:
            pass
    if amocrm_conf and leads_count > 0:
        return {"pipeline": "amocrm_crm", "name": "AmoCRM v4 & Lidlar Voronkasi", "status": "healthy", "severity": "info", "message": f"AmoCRM ulangan ({leads_count} ta lid bazada mavjud, 500 limit nazoratda).", "action": None}
    if amocrm_conf and leads_count == 0:
        return {"pipeline": "amocrm_crm", "name": "AmoCRM v4 & Lidlar Voronkasi", "status": "warning", "severity": "warning", "message": "AmoCRM sozlangan, ammo bazada 0 ta faol lid mavjud (Webhook yoki sinxron kutilyapti).", "action": "AmoCRM dan /crm_sync yoki yangi so'rov yuborish."}
    return {"pipeline": "amocrm_crm", "name": "AmoCRM v4 & Lidlar Voronkasi", "status": "disconnected", "severity": "critical", "message": "AMOCRM_SUBDOMAIN yoki token sozlanmagan.", "action": "Sozlamalardan AmoCRM v4 integratsiyasini ulash."}


async def _check_finance_signal() -> Dict[str, Any]:
    has_finance = api_state.finance_source is not None
    tx_count, source_name = 0, "Turso DB"
    if has_finance:
        try:
            snap = await api_state.finance_source.get_snapshot()
            tx_count = len(snap.transactions)
            source_name = "Google Sheets (Pul oqimi)" if "sheet" in str(snap.source) else str(snap.source)
        except Exception:
            pass
    if tx_count == 0 and api_state.db_instance:
        try:
            conn = await api_state.db_instance.get_connection()
            r = await conn.execute("SELECT COUNT(*) FROM hisobchi_transactions")
            row = await r.fetchone() if hasattr(r, "fetchone") else r.fetchone()
            tx_count = row[0] if row else 0
        except Exception:
            pass
    if has_finance and tx_count > 0:
        return {"pipeline": "hisobchi_finance", "name": "Hisobchi AI & Moliya Oqimi", "status": "healthy", "severity": "info", "message": f"Moliya manbasi ulangan ({tx_count} ta real tranzaksiya mavjud • {source_name}).", "action": None}
    return {"pipeline": "hisobchi_finance", "name": "Hisobchi AI & Moliya Oqimi", "status": "warning", "severity": "warning", "message": "Google Sheets yoki Karta SMS gatewaydan yangi to'lovlar kutilmoqda (0 ta tranzaksiya).", "action": "Telegramda /kirim yoki /chiqim kiritish, yoki Karta SMS botini tekshirish."}


async def _check_frog_signal() -> Dict[str, Any]:
    task_count = 0
    if api_state.db_instance:
        try:
            conn = await api_state.db_instance.get_connection()
            r = await conn.execute("SELECT COUNT(*) FROM tasks WHERE status NOT IN ('Done', 'Completed')")
            row = await r.fetchone() if hasattr(r, "fetchone") else r.fetchone()
            task_count = row[0] if row else 0
        except Exception:
            pass
    if task_count > 0:
        return {"pipeline": "frog_agent", "name": "FrogAgent ROI Vazifalar", "status": "healthy", "severity": "info", "message": f"Kunlik {task_count} ta operatsion vazifa faol ijroda.", "action": None}
    return {"pipeline": "frog_agent", "name": "FrogAgent ROI Vazifalar", "status": "warning", "severity": "warning", "message": "Hozirda ijro etilayotgan faol Frog vazifalari mavjud emas.", "action": "Telegramda /frog orqali bugungi 1-raqamli vazifani belgilang."}


async def _check_salescoach_signal() -> Dict[str, Any]:
    calls_count = 0
    if api_state.db_instance:
        try:
            conn = await api_state.db_instance.get_connection()
            r = await conn.execute("SELECT COUNT(*) FROM call_analyses")
            row = await r.fetchone() if hasattr(r, "fetchone") else r.fetchone()
            calls_count = row[0] if row else 0
        except Exception:
            pass
    if calls_count > 0:
        return {"pipeline": "salescoach_audio", "name": "SalesCoach AI (Audio Skoring)", "status": "healthy", "severity": "info", "message": f"{calls_count} ta qo'ng'iroq tahlili bazada saqlangan.", "action": None}
    return {"pipeline": "salescoach_audio", "name": "SalesCoach AI (Audio Skoring)", "status": "idle", "severity": "info", "message": "Audio yozuvlar navbati bo'sh (yangi qo'ng'iroq audio fayli kutilmoqda).", "action": "Audio yozuv yuklash yoki Fireflies.ai integratsiyasini ulash."}


@router.get("/signals", dependencies=[require_permissions(Permission.SYSTEM_READ)])
async def get_system_signals():
    """Real vaqtdagi barcha ma'lumot oqimlari diagnostikasi va uzilish signallari."""
    from src.services.core.agent_runtime import get_runtime_context

    runtime = get_runtime_context()
    signals: List[Dict[str, Any]] = [
        _check_telegram_signal(runtime),
        await _check_amocrm_signal(),
        await _check_finance_signal(),
        await _check_frog_signal(),
        await _check_salescoach_signal(),
    ]

    healthy_count = sum(1 for s in signals if s["status"] == "healthy")
    health_percentage = int((healthy_count / len(signals)) * 100) if signals else 100

    return {
        "timestamp": get_local_now().isoformat(),
        "health_score": health_percentage,
        "total_pipelines": len(signals),
        "healthy_count": healthy_count,
        "has_critical": any(s["severity"] == "critical" for s in signals),
        "has_warning": any(s["severity"] == "warning" for s in signals),
        "signals": signals,
    }


def _get_legacy_runtime_inventory() -> List[Dict[str, Any]]:
    if api_state.legacy_runtime_inventory_cache is None:
        import os
        from src.services.core.agent_runtime import collect_legacy_runtime_inventory

        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        api_state.legacy_runtime_inventory_cache = collect_legacy_runtime_inventory(repo_root)
    return list(api_state.legacy_runtime_inventory_cache)


async def build_health_snapshot(
    include_inventory: bool = False, include_traces: bool = False
) -> Dict[str, Any]:
    """Helper to build health snapshot for dashboard."""
    from src.services.core.agent_runtime import get_runtime_context, get_storage_health

    runtime = get_runtime_context()
    db_path = runtime.get("state_db_path") or getattr(api_state.db_instance, "db_path", None)
    recent_job_runs: List[Dict[str, Any]] = []
    recent_agent_actions: List[Dict[str, Any]] = []
    storage_counts: Dict[str, int] = {}
    storage_cache_used = False

    if api_state.db_instance:
        try:
            async def load_storage_snapshot() -> Dict[str, Any]:
                return {
                    "recent_job_runs": await api_state.db_instance.get_recent_job_runs(limit=10),
                    "storage_counts": await api_state.db_instance.get_storage_counts(),
                    "updated_at": get_local_now().isoformat(),
                }

            api_state._health_db_snapshot_cache = await asyncio.wait_for(
                load_storage_snapshot(),
                timeout=api_state._HEALTH_DB_TIMEOUT_SECONDS,
            )
            recent_job_runs = list(api_state._health_db_snapshot_cache["recent_job_runs"])
            storage_counts = dict(api_state._health_db_snapshot_cache["storage_counts"])
        except asyncio.TimeoutError:
            storage_cache_used = True
        except Exception as exc:
            storage_cache_used = True
            logger.warning("[API] Could not fetch storage health: %s", exc)

        if storage_cache_used:
            recent_job_runs = list(api_state._health_db_snapshot_cache.get("recent_job_runs", []))
            storage_counts = dict(api_state._health_db_snapshot_cache.get("storage_counts", {}))

        if include_traces:
            try:
                recent_agent_actions = await asyncio.wait_for(
                    api_state.db_instance.get_recent_agent_actions(limit=25),
                    timeout=api_state._HEALTH_DB_TIMEOUT_SECONDS,
                )
            except Exception as exc:
                logger.debug("[dashboard] get agent actions failed: %s", exc)

    storage_health = get_storage_health(
        db_path,
        recent_job_runs=recent_job_runs,
        backend=runtime.get("state_backend", "sqlite"),
        storage_counts=storage_counts,
    )
    storage_health["cached"] = storage_cache_used
    storage_health["cache_updated_at"] = api_state._health_db_snapshot_cache.get("updated_at")

    signals_res = await get_system_signals()
    snapshot = {
        "timestamp": get_local_now().isoformat(),
        "status": getattr(api_state, "cached_status", {}),
        "runtime": runtime,
        "storage": storage_health,
        "telegram_userbot_access": dict(getattr(api_state, "_userbot_group_access_snapshot", {})),
        "health_score": signals_res.get("health_score", 100),
        "signals": signals_res.get("signals", []),
    }
    if include_inventory:
        snapshot["legacy_runtime_inventory"] = _get_legacy_runtime_inventory()
    if include_traces:
        snapshot["agent_actions"] = recent_agent_actions
    return snapshot
