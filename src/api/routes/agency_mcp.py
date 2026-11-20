"""Oisha business MCP: restricted, read-only JSON-RPC over HTTPS.

Unlike Oisha Connect (which grants access to personal Telegram chats), this
endpoint exposes an explicit catalog of business datasets. It is not a raw SQL
gateway, arbitrary URL fetcher, or write/mutation interface.

Auth: standard Oisha bearer/session boundary plus Permission.MCP_READ and
per-source RBAC permissions. Dedicated service tokens with narrow scopes are
recommended. No tokens appear in URLs.
"""
from __future__ import annotations

import json
import logging
from datetime import date
from typing import Any

from fastapi import APIRouter, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import HTTPException
from fastapi.responses import JSONResponse, Response

from src.api.rbac import Permission, Principal, has_permission, require_permissions
from src.api.routes.attendance_routes import _RateLimiter

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/agency-mcp", tags=["agency-mcp"])
_MCP_AUTH = require_permissions(Permission.MCP_READ)
_PROTOCOL = "2025-06-18"
_MAX_REQUEST_BYTES = 16_384
_MAX_RESULT_BYTES = 128_000
_RATE_LIMITER = _RateLimiter(limit=60, window_s=60)

# Only explicitly reviewed read paths may be published here. Never accept a
# caller-provided URL, database query, table name, or arbitrary method.
SOURCES: dict[str, tuple[str, tuple[Permission, ...], str]] = {
    "sales_report": ("AmoCRM daily/weekly/monthly sales summary", (Permission.DASHBOARD_READ,), "amocrm"),
    "pipeline": ("Organization-wide revenue and pipeline overview", (Permission.DASHBOARD_READ, Permission.FINANCE_READ), "amocrm_and_finance"),
    "leads": ("CRM leads; capped at 50 source rows", (Permission.LEAD_READ_ALL,), "oisha_crm"),
    "tasks": ("Internal CRM and FrogAgent task summaries", (Permission.SYSTEM_READ,), "oisha_tasks"),
    "marketing": ("Cached Meta Ads and CRM attribution summary", (Permission.MARKETING_READ,), "oisha_marketing_cache"),
    "finance": ("Finance KPIs from configured real source", (Permission.FINANCE_READ,), "oisha_finance"),
    "finance_transactions": ("Recent finance transactions, bounded result", (Permission.FINANCE_READ,), "oisha_finance"),
    "sales_quality": ("Call-analysis team quality overview", (Permission.CALL_READ_ALL,), "oisha_calls"),
    "conversion": ("Lead-to-sale conversion overview", (Permission.FINANCE_READ,), "oisha_conversion"),
    "projects": ("ERP project summary", (Permission.FINANCE_READ,), "oisha_erp"),
    "team": ("ERP team summary", (Permission.USERS_MANAGE_LIMITED,), "oisha_erp"),
}

_TOOL_LIST = [
    {
        "name": "list_business_sources",
        "description": "List Oisha business datasets allowed by your account and their original data sources.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
        "annotations": {"readOnlyHint": True},
    },
    {
        "name": "read_business_source",
        "description": "Read one whitelisted Oisha business dataset. Read only; no raw SQL, arbitrary URLs or mutations.",
        "inputSchema": {
            "type": "object",
            "required": ["source"],
            "properties": {
                "source": {"type": "string", "enum": list(SOURCES)},
                "period": {"type": "string", "enum": ["daily", "weekly", "monthly"], "default": "monthly"},
                "start_date": {"type": "string", "description": "Optional YYYY-MM-DD for marketing"},
                "end_date": {"type": "string", "description": "Optional YYYY-MM-DD for marketing"},
                "days": {"type": "integer", "minimum": 1, "maximum": 90, "default": 30},
                "limit": {"type": "integer", "minimum": 1, "maximum": 100, "default": 50},
            },
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": True},
    },
]


def _rpc(rid: Any, result: Any) -> dict:
    return {"jsonrpc": "2.0", "id": rid, "result": result}


def _error(rid: Any, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": rid, "error": {"code": code, "message": message}}


def _tool_text(payload: Any, *, error: bool = False) -> dict:
    return {
        "content": [{"type": "text", "text": json.dumps(jsonable_encoder(payload), ensure_ascii=False)}],
        "isError": error,
    }


def _can_read(principal: Principal, source: str) -> bool:
    return source in SOURCES and all(
        has_permission(principal, permission) for permission in SOURCES[source][1]
    )


def _positive_int(value: Any, *, maximum: int, name: str) -> int:
    if type(value) is not int or not 1 <= value <= maximum:
        raise ValueError(f"{name} must be an integer between 1 and {maximum}")
    return value


def _dates(args: dict) -> tuple[str | None, str | None]:
    start, end = args.get("start_date"), args.get("end_date")
    if start is None and end is None:
        return None, None
    if not isinstance(start, str) or not isinstance(end, str):
        raise ValueError("start_date and end_date must both be supplied")
    try:
        a, b = date.fromisoformat(start), date.fromisoformat(end)
    except ValueError as exc:
        raise ValueError("Use YYYY-MM-DD date format") from exc
    if b < a or (b - a).days > 366:
        raise ValueError("Date range must be ordered and no longer than 366 days")
    return a.isoformat(), b.isoformat()


def _unwrap(payload: Any) -> Any:
    if isinstance(payload, Response):
        if payload.status_code >= 400:
            raise RuntimeError(f"upstream_status_{payload.status_code}")
        try:
            return json.loads(payload.body)
        except (TypeError, ValueError) as exc:
            raise RuntimeError("upstream_invalid_json") from exc
    return payload


async def _read(source: str, args: dict, principal: Principal) -> Any:
    period = args.get("period", "monthly")
    if period not in ("daily", "weekly", "monthly"):
        raise ValueError("Invalid period")
    days = _positive_int(args.get("days", 30), maximum=90, name="days")
    limit = _positive_int(args.get("limit", 50), maximum=100, name="limit")
    start, end = _dates(args)

    if source == "sales_report":
        from src.api.routes.crm_reports import crm_reports

        return await crm_reports(period=period, principal=principal)

    if source == "pipeline":
        from src.api.routes.dashboard_overview import dashboard_overview

        return await dashboard_overview(principal=principal)

    if source == "leads":
        from src.api.routes.crm_dashboard import crm_leads

        result = await crm_leads(principal=principal)
        result["leads"] = result.get("leads", [])[:limit]
        result["returned"] = len(result["leads"])
        return result

    if source == "tasks":
        from src.api.routes.crm_dashboard import crm_tasks

        result = await crm_tasks(principal=principal)
        if isinstance(result, dict) and isinstance(result.get("tasks"), list):
            result["tasks"] = result["tasks"][:limit]
            result["returned"] = len(result["tasks"])
        return result

    if source == "marketing":
        from src.api.routes.marketing_dashboard import get_marketing_performance

        return await get_marketing_performance(start_date=start, end_date=end)

    if source == "finance":
        from src.api.routes.finance_dashboard import finance_dashboard

        return await finance_dashboard()

    if source == "finance_transactions":
        from src.api.routes.finance_dashboard import finance_transactions

        result = await finance_transactions()
        transactions = result.get("transactions", [])
        result["transactions"] = transactions[:limit]
        result["returned"] = len(result["transactions"])
        result["truncated"] = len(transactions) > limit
        return result

    if source == "sales_quality":
        from src.api.routes.sales_quality import get_sales_quality_overview

        return await get_sales_quality_overview(principal=principal)

    if source == "conversion":
        from src.api.routes.ai_analytics_pkg.conversion import get_conversion_overview

        return await get_conversion_overview(days=days)

    if source in ("projects", "team"):
        from src.api.routes.state import api_state

        if api_state.db_instance is None:
            return {"available": False, "reason": "database_not_configured"}
        if source == "projects":
            from src.services.core.project_engine import ProjectEngine

            return await ProjectEngine(db=api_state.db_instance).get_project_stats()
        from src.services.core.hr_engine import HREngine

        return await HREngine(db=api_state.db_instance).get_team_summary()

    raise ValueError("Unknown source")


async def _handle(message: Any, principal: Principal) -> dict | None:
    if not isinstance(message, dict) or message.get("jsonrpc") != "2.0":
        return _error(None, -32600, "Invalid Request")
    rid = message.get("id")
    if "id" not in message:
        return None  # notifications do not receive a response
    method = message.get("method")
    if method == "initialize":
        return _rpc(rid, {
            "protocolVersion": _PROTOCOL,
            "serverInfo": {"name": "oisha-agency", "version": "1.0.0"},
            "capabilities": {"tools": {"listChanged": False}},
            "instructions": "Read-only business data. Sources may be unavailable when upstream integrations are offline.",
        })
    if method == "ping":
        return _rpc(rid, {})
    if method == "tools/list":
        return _rpc(rid, {"tools": _TOOL_LIST})
    if method != "tools/call":
        return _error(rid, -32601, "Method not found")

    params = message.get("params") or {}
    if not isinstance(params, dict) or not isinstance(params.get("arguments", {}), dict):
        return _error(rid, -32602, "Invalid tool arguments")
    name, args = params.get("name"), params.get("arguments") or {}
    if name == "list_business_sources":
        if args:
            return _error(rid, -32602, "Unexpected arguments")
        return _rpc(rid, _tool_text({
            "sources": [{
                "id": key, "description": description, "origin": origin,
                "required_scopes": [permission.value for permission in permissions],
            } for key, (description, permissions, origin) in SOURCES.items()
            if _can_read(principal, key)],
            "note": "Only data configured and available in Oisha can be fetched.",
        }))
    if name != "read_business_source":
        return _error(rid, -32602, "Unknown tool")
    if not set(args).issubset({"source", "period", "days", "limit", "start_date", "end_date"}):
        return _error(rid, -32602, "Unsupported arguments")
    source = args.get("source")
    if not isinstance(source, str) or source not in SOURCES:
        return _error(rid, -32602, "Unknown source")
    if not _can_read(principal, source):
        return _rpc(rid, _tool_text({"error": "permission_denied"}, error=True))
    try:
        data = jsonable_encoder(_unwrap(await _read(source, args, principal)))
        payload = {"source": source, "origin": SOURCES[source][2],
                   "available": not (isinstance(data, dict) and data.get("available") is False),
                   "data": data}
        if len(json.dumps(payload, ensure_ascii=False).encode("utf-8")) > _MAX_RESULT_BYTES:
            return _rpc(rid, _tool_text({"error": "result_too_large", "hint": "Reduce limit"}, error=True))
        return _rpc(rid, _tool_text(payload))
    except ValueError as exc:
        return _rpc(rid, _tool_text({"error": "invalid_arguments", "message": str(exc)}, error=True))
    except (HTTPException, RuntimeError):
        logger.warning("[agency-mcp] Source unavailable: %s", source)
        return _rpc(rid, _tool_text({"error": "source_unavailable", "source": source}, error=True))
    except Exception:
        logger.exception("[agency-mcp] Unexpected read failure for %s", source)
        return _rpc(rid, _tool_text({"error": "source_unavailable", "source": source}, error=True))


@router.post("")
async def agency_mcp(request: Request, principal: Principal = _MCP_AUTH):
    _RATE_LIMITER.check(f"agency-mcp:{principal.subject}")
    body = await request.body()
    if len(body) > _MAX_REQUEST_BYTES:
        return JSONResponse({"error": "request_too_large"}, status_code=413)
    try:
        message = json.loads(body)
    except ValueError:
        return JSONResponse(_error(None, -32700, "Parse error"), status_code=400)
    if not isinstance(message, dict):
        return JSONResponse(_error(None, -32600, "Invalid Request"), status_code=400)
    response = await _handle(message, principal)
    return JSONResponse(response) if response is not None else Response(status_code=202)
