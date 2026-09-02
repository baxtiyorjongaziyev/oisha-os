"""
Client dashboard view, background audit, and server runner.
"""
import asyncio
import logging
import time
import uvicorn
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from src.api.routes.state import api_state
from src.services.api_server.helpers import (
    _get_call_backfill_interval_seconds,
    _get_call_backfill_limit,
    _parse_state_json,
    _timestamp_to_iso,
)
from src.api.routes.amocrm_integration import (
    _run_amocrm_call_backfill,
    _CALL_BACKFILL_LAST_STARTED_KEY,
    _CALL_BACKFILL_LAST_FINISHED_KEY,
    _CALL_BACKFILL_LAST_RESULT_KEY,
    _CALL_BACKFILL_LAST_ERROR_KEY,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["dashboard"])

async def client_dashboard(request: Request):
    """Serve the Client Dashboard (MVP)."""
    # Simple check for JWT token in cookies
    token = request.cookies.get("oisha_token")
    if not token:
        return RedirectResponse(url="/api/auth/telegram/login")

    import config
    from src.api import auth_service
    jwt_secret = getattr(config, "JWT_SECRET", config.BOT_TOKEN)
    payload = auth_service.decode_session_jwt(token, jwt_secret)
    if payload is None:
        # Invalid or expired token
        return RedirectResponse(url="/api/auth/telegram/login")
    user_id = payload.get("sub")
    first_name = payload.get("first_name", "Foydalanuvchi")
    role = payload.get("role", "client")

    html_content = f"""
    <!DOCTYPE html>
    <html lang="uz">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Oisha-OS | {first_name}</title>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
        <style>
            :root {{
                --primary: #2563eb;
                --primary-hover: #1d4ed8;
                --bg: #f3f4f6;
                --card-bg: #ffffff;
                --text: #1f2937;
                --text-light: #6b7280;
                --success: #10b981;
                --warning: #f59e0b;
                --danger: #ef4444;
            }}
            * {{ margin: 0; padding: 0; box-sizing: border-box; font-family: 'Inter', sans-serif; }}
            body {{ background-color: var(--bg); color: var(--text); }}
            
            /* Navbar */
            header {{ background: var(--card-bg); padding: 1rem 2rem; box-shadow: 0 1px 3px rgba(0,0,0,0.1); display: flex; justify-content: space-between; align-items: center; position: sticky; top: 0; z-index: 10; }}
            .logo {{ font-weight: 700; font-size: 1.25rem; color: var(--primary); display: flex; align-items: center; gap: 0.5rem; }}
            .user-profile {{ display: flex; align-items: center; gap: 1rem; }}
            .avatar {{ width: 36px; height: 36px; background: var(--primary); color: white; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: 600; }}
            
            /* Main Content */
            main {{ padding: 2rem; max-width: 1200px; margin: 0 auto; }}
            .welcome {{ margin-bottom: 2rem; }}
            .welcome h1 {{ font-size: 1.8rem; margin-bottom: 0.5rem; }}
            .welcome p {{ color: var(--text-light); }}
            
            /* Kanban Board */
            .kanban-board {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 1.5rem; align-items: start; }}
            .column {{ background: var(--card-bg); border-radius: 0.75rem; padding: 1.5rem; box-shadow: 0 1px 3px rgba(0,0,0,0.1); min-height: 400px; }}
            .column-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.5rem; padding-bottom: 0.75rem; border-bottom: 2px solid var(--bg); font-weight: 600; }}
            .count-badge {{ background: var(--bg); padding: 0.25rem 0.75rem; border-radius: 1rem; font-size: 0.875rem; color: var(--text-light); }}
            
            /* Task Cards */
            .task-card {{ background: var(--bg); padding: 1rem; border-radius: 0.5rem; margin-bottom: 1rem; border: 1px solid #e5e7eb; transition: transform 0.2s, box-shadow 0.2s; cursor: pointer; }}
            .task-card:hover {{ transform: translateY(-2px); box-shadow: 0 4px 6px rgba(0,0,0,0.05); }}
            .task-title {{ font-weight: 600; margin-bottom: 0.5rem; font-size: 0.95rem; }}
            .task-meta {{ display: flex; justify-content: space-between; align-items: center; font-size: 0.75rem; color: var(--text-light); margin-top: 1rem; }}
            .priority-tag {{ padding: 0.15rem 0.5rem; border-radius: 0.25rem; font-weight: 500; }}
            .priority-high {{ background: #fee2e2; color: var(--danger); }}
            .priority-medium {{ background: #fef3c7; color: var(--warning); }}
            .priority-low {{ background: #d1fae5; color: var(--success); }}
            
            /* Empty State */
            .empty-state {{ text-align: center; padding: 2rem; color: var(--text-light); font-size: 0.9rem; }}
            
            /* FAB */
            .fab {{ position: fixed; bottom: 2rem; right: 2rem; width: 56px; height: 56px; background: var(--primary); color: white; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 1.5rem; box-shadow: 0 4px 12px rgba(37,99,235,0.4); cursor: pointer; transition: transform 0.2s; border: none; }}
            .fab:hover {{ transform: scale(1.05); background: var(--primary-hover); }}
            
            @media (max-width: 768px) {{
                .kanban-board {{ grid-template-columns: 1fr; }}
                main {{ padding: 1rem; }}
            }}
        </style>
    </head>
    <body>
        <header>
            <div class="logo">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 2 7 12 12 22 7 12 2"></polygon><polyline points="2 17 12 22 22 17"></polyline><polyline points="2 12 12 17 22 12"></polyline></svg>
                Oisha-OS
            </div>
            <div class="user-profile">
                <span style="font-weight: 500; font-size: 0.9rem;">{first_name}</span>
                <div class="avatar">{first_name[0].upper()}</div>
            </div>
        </header>

        <main>
            <div class="welcome">
                <h1>Xush kelibsiz, {first_name}!</h1>
                <p>Loyihalaringiz va vazifalaringiz shu yerda boshqariladi.</p>
            </div>

            <div class="kanban-board">
                <!-- Bajarilmoqda -->
                <div class="column">
                    <div class="column-header">
                        <span style="color: var(--primary);">Jarayonda (In Progress)</span>
                        <span class="count-badge" id="count-progress">0</span>
                    </div>
                    <div id="col-progress" class="task-list">
                        <div class="empty-state">Vazifalar yo'q</div>
                    </div>
                </div>

                <!-- Kutilmoqda -->
                <div class="column">
                    <div class="column-header">
                        <span style="color: var(--warning);">Mijoz Tasdig'ida</span>
                        <span class="count-badge" id="count-review">0</span>
                    </div>
                    <div id="col-review" class="task-list">
                        <div class="empty-state">Vazifalar yo'q</div>
                    </div>
                </div>

                <!-- Bajarildi -->
                <div class="column">
                    <div class="column-header">
                        <span style="color: var(--success);">Tugatilgan</span>
                        <span class="count-badge" id="count-done">0</span>
                    </div>
                    <div id="col-done" class="task-list">
                        <div class="empty-state">Vazifalar yo'q</div>
                    </div>
                </div>
            </div>
        </main>
        
        <script>
            // MVP script for future API connection
            document.addEventListener('DOMContentLoaded', () => {{
                console.log("Dashboard loaded for role: {role}");
                // Future: fetch('/api/tasks') and render
            }});
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

async def background_crm_audit_task():
    while True:
        try:
            try:
                from src.services.debug.crm_audit import AmoCRMAudit
                audit = AmoCRMAudit()
            except ImportError:
                await asyncio.sleep(900)
                continue
            results = await audit.run_full_audit()
            if results and "error" not in results:
                api_state.cached_crm_audit = results
                logger.info("[API] CRM Audit complete. Health: %s%%", results.get("health_score"))
        except Exception as e:
            logger.error("[API] CRM Audit CRASH: %s", e)
        await asyncio.sleep(900)

async def _schedule_amocrm_call_backfill(
    db, *, reason: str = "unknown", limit: int = None, force: bool = False
):
    if api_state._call_backfill_task and not api_state._call_backfill_task.done():
        if not force:
            return {"queued": False, "reason": "already_running"}

    if not force and db:
        try:
            last_started_raw = await db.get_state(_CALL_BACKFILL_LAST_STARTED_KEY)
            if last_started_raw:
                elapsed = time.time() - float(last_started_raw)
                interval = _get_call_backfill_interval_seconds()
                if elapsed < interval:
                    return {
                        "queued": False,
                        "reason": "throttled",
                        "retry_after_seconds": int(interval - elapsed),
                    }
        except Exception as exc:
            logger.debug("[backfill] throttle check failed: %s", exc)

    limit = _get_call_backfill_limit(limit)
    if db:
        try:
            await db.set_state(_CALL_BACKFILL_LAST_STARTED_KEY, str(time.time()))
        except Exception as exc:
            logger.debug("[backfill] failed to set start state: %s", exc)
    
    import sys
    api_srv = sys.modules.get("src.api_server")
    runner = getattr(api_srv, "_run_amocrm_call_backfill", _run_amocrm_call_backfill) if api_srv else _run_amocrm_call_backfill

    api_state._call_backfill_task = asyncio.create_task(
        runner(db, reason=reason, limit=limit)
    )
    return {"queued": True, "reason": reason, "limit": limit}


async def _build_amocrm_call_analysis_status(db) -> dict:
    last_started_raw = None
    last_finished_raw = None
    last_result_raw = ""
    last_error = ""

    if db:
        try:
            last_started_raw = await db.get_state(_CALL_BACKFILL_LAST_STARTED_KEY)
        except Exception as exc:
            logger.debug("[backfill] get state started failed: %s", exc)
        try:
            last_finished_raw = await db.get_state(_CALL_BACKFILL_LAST_FINISHED_KEY)
        except Exception as exc:
            logger.debug("[backfill] get state finished failed: %s", exc)
        try:
            last_result_raw = await db.get_state(_CALL_BACKFILL_LAST_RESULT_KEY) or ""
        except Exception as exc:
            logger.debug("[backfill] get state result failed: %s", exc)
        try:
            last_error = await db.get_state(_CALL_BACKFILL_LAST_ERROR_KEY) or ""
        except Exception as exc:
            logger.debug("[backfill] get state error failed: %s", exc)

    # Memory fallback
    from src.api.routes.state import api_state as _api_state
    mem = api_state._call_backfill_last_status or {}
    if not mem:
        mem = getattr(_api_state, "api_state._call_backfill_last_status", {}) or {}
    if not last_started_raw and mem.get("started_at"):
        last_started_raw = mem["started_at"]
    if not last_finished_raw and mem.get("finished_at"):
        last_finished_raw = mem["finished_at"]
    if not last_result_raw and mem.get("result"):
        last_result_raw = mem["result"]
    if not last_error and mem.get("error"):
        last_error = mem["error"]

    if isinstance(last_result_raw, dict):
        last_result = last_result_raw
    elif last_result_raw:
        last_result = _parse_state_json(last_result_raw)
    else:
        last_result = {}

    # Totals
    totals = {}
    if db:
        try:
            conn = await db.get_connection()
            r = conn.execute(
                "SELECT COUNT(*) as total, "
                "SUM(CASE WHEN source='amocrm' THEN 1 ELSE 0 END) as amocrm, "
                "SUM(CASE WHEN recommended_tasks IS NOT NULL AND recommended_tasks != '[]' THEN 1 ELSE 0 END) as tasks "
                "FROM call_analyses"
            )
            if hasattr(r, "__await__"):
                r = await r
            row = r.fetchone() if hasattr(r, "fetchone") else None
            if row and hasattr(row, "__await__"):
                row = await row
            if row:
                if isinstance(row, dict):
                    totals = {
                        "total_analyses": row.get("total_analyses") or row.get("total", 0),
                        "amocrm_analyses": row.get("amocrm_analyses") or row.get("amocrm", 0),
                        "tasks_created": row.get("tasks_created") or row.get("tasks", 0),
                    }
                else:
                    totals = {
                        "total_analyses": row[0] if len(row) > 0 else 0,
                        "amocrm_analyses": row[1] if len(row) > 1 else 0,
                        "tasks_created": row[2] if len(row) > 2 else 0,
                    }
        except Exception as exc:
            logger.debug("[backfill] totals query failed: %s", exc)

    running = bool(api_state._call_backfill_task and not api_state._call_backfill_task.done())
    last_run = {}
    if last_started_raw or last_finished_raw:
        last_run["started_at"] = last_started_raw if isinstance(last_started_raw, str) and "T" in str(last_started_raw) else _timestamp_to_iso(last_started_raw)
        last_run["finished_at"] = last_finished_raw if isinstance(last_finished_raw, str) and "T" in str(last_finished_raw) else _timestamp_to_iso(last_finished_raw)
        if last_result:
            last_run["result"] = last_result
        if last_error:
            last_run["error"] = last_error

    return {
        "ok": not bool(last_error),
        "running": running,
        "last_run": last_run,
        "totals": totals,
    }


# Backward-compat re-exports: these symbols are pulled back into the
# api_server namespace for legacy callers that do `from src.api_server import X`.
# They are INTENTIONALLY at module end â€” the router modules import from here, so
# importing them earlier would create circular imports. Do not move to the top.
from src.api.routes.chat_widget import (  # noqa: F401
    lookup_user_by_phone,
    get_chat_history,
    send_chat_message,
    SendMessageRequest,
    CreateLeadRequest,
)
from src.api.routes.product_suite import oisha_product_suite  # noqa: F401
from src.api.routes.sales_quality import (  # noqa: F401
    get_sales_quality_overview,
    _build_sales_quality_payload,
    _build_empty_sales_quality,
    _safe_json_list,
    _row_to_dict,
    _score_to_risk,
    _format_duration,
    _avatar,
)
from src.api.routes.system_dashboard import build_health_snapshot  # noqa: F401
from src.api.routes.health import (  # noqa: F401
    liveness_probe,
    production_readiness_probe,
)
from src.api.routes.telegram_routes import telegram_group_access  # noqa: F401
from src.api.routes.openclaw_gateway import (  # noqa: F401
    openclaw_webhook,
    openclaw_health,
    v1_models,
    v1_chat_completions,
)
from src.api.routes.amocrm_integration import (  # noqa: F401
    _process_amocrm_event as process_amocrm_event,
)
try:
    from src.agents.autonomous_sales_agent import AutonomousSalesAgent  # noqa: F401
except Exception:
    AutonomousSalesAgent = None  # type: ignore

# ---------------------------------------------------------------------------
# Entry Points
# ---------------------------------------------------------------------------

def run_api(host: str = "0.0.0.0", port: int = 8080):  # nosec
    from src.services.api_server.core import app
    uvicorn.run(app, host=host, port=port)

