"""
Helper functions and runtime utilities for Oisha-OS API Server.
"""
import hmac
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from src.context import app_ctx
from src.settings import settings

logger = logging.getLogger(__name__)


async def _maybe_await(val: Any) -> Any:
    if hasattr(val, "__await__"):
        return await val
    return val


def _setting_text(key: str, default: str = "") -> str:
    val = getattr(settings, key, default)
    if val is None:
        return default
    val_str = str(val).strip()
    return val_str if val_str else default


def _secret_setting_text(key: str, default: str = "") -> str:
    return _setting_text(key, default)


def set_telegram_ai_ingress_status(enabled: bool, reason: str = "") -> None:
    from src.api.routes.health import api_state
    api_state.telegram_ai_ingress_enabled = bool(enabled)
    api_state.telegram_ai_ingress_reason = (
        str(reason or ("enabled" if enabled else "disabled"))
    )


def mark_heartbeat(component: str = "api") -> None:
    from src.api.routes.health import api_state
    api_state.last_heartbeat[component] = datetime.now(timezone.utc).isoformat()


def add_activity(
    action: str,
    status: str = "ok",
    detail: Optional[Dict[str, Any]] = None,
) -> None:
    from src.api.routes.health import api_state
    api_state.recent_activity.append(
        {
            "action": action,
            "status": status,
            "detail": detail or {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    )


def update_api_status(status_update: Dict[str, Any]) -> None:
    from src.api.routes.health import api_state
    for k, v in status_update.items():
        if hasattr(api_state, k):
            setattr(api_state, k, v)


def get_legacy_runtime_inventory() -> Dict[str, Any]:
    from src.api.routes.health import api_state
    inv = api_state.inventory_snapshot or {}
    return inv.get("features", {})


def _timestamp_to_iso(ts: Any) -> Optional[str]:
    if ts is None:
        return None
    try:
        ts_float = float(ts)
        return datetime.fromtimestamp(ts_float, tz=timezone.utc).isoformat()
    except (ValueError, TypeError, OSError):
        return None


def _parse_state_json(state_str: Optional[str]) -> Dict[str, Any]:
    if not state_str:
        return {}
    try:
        data = json.loads(state_str)
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return {}


def _get_cron_secret_value() -> str:
    return (
        getattr(settings, "CRON_SECRET", "")
        or getattr(settings, "OISHA_API_SECRET", "")
        or ""
    ).strip()


def _is_authorized_cron_request(provided: Optional[str]) -> bool:
    secret = _get_cron_secret_value()
    if not secret:
        return True
    if not provided:
        return False
    return hmac.compare_digest(provided.strip(), secret)


def _get_call_backfill_limit(request_limit: Optional[int] = None) -> int:
    if request_limit is not None and request_limit > 0:
        return max(1, min(int(request_limit), 200))
    configured = getattr(settings, "CALL_BACKFILL_BATCH_LIMIT", None)
    if configured is not None:
        try:
            return max(1, min(int(configured), 200))
        except (TypeError, ValueError):
            pass
    return 30


def _get_call_backfill_interval_seconds(request_interval: Optional[int] = None) -> int:
    if request_interval is not None and request_interval > 0:
        return max(30, min(int(request_interval), 3600))
    configured = getattr(settings, "CALL_BACKFILL_INTERVAL_SECONDS", None)
    if configured is not None:
        try:
            return max(30, min(int(configured), 3600))
        except (TypeError, ValueError):
            pass
    return 300


def _get_db_instance() -> Optional[Any]:
    db = getattr(app_ctx, "db_instance", None) or getattr(app_ctx, "db", None)
    if db is not None:
        return db
    try:
        from src.database import Database
        return Database()
    except Exception:
        return None


def _get_amocrm_instance() -> Optional[Any]:
    amo = getattr(app_ctx, "amocrm_instance", None) or getattr(app_ctx, "amocrm", None)
    if amo is not None:
        return amo
    try:
        from src.services.core.crm.amocrm_sync import AmoCRMSync
        return AmoCRMSync()
    except Exception:
        return None
