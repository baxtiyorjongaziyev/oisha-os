"""
Core FastAPI application creation, middleware, router inclusions, and lifespan.
"""
import hmac
import logging
import os
from contextlib import asynccontextmanager
from typing import Any, Dict

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from src.settings import settings
from src.services.api_server.helpers import (
    _get_amocrm_instance,
    _get_db_instance,
    mark_heartbeat,
    add_activity,
)
import src.services.api_server.webhooks as webhooks_module
import src.services.api_server.oauth as oauth_module
import src.services.api_server.dashboard as dashboard_module

logger = logging.getLogger(__name__)

limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI):
    mark_heartbeat("api")
    add_activity("api_started", "ok", {"event": "lifespan_start"})
    yield
    add_activity("api_stopped", "ok", {"event": "lifespan_shutdown"})


app = FastAPI(title="Oisha-OS Enterprise API", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# OAuth2 Middleware for MCP Endpoints
@app.middleware("http")
async def verify_oauth_for_mcp(request: Request, call_next):
    if request.url.path.startswith("/telegram-mcp"):
        if request.method == "OPTIONS":
            return await call_next(request)

        auth_header = request.headers.get("Authorization")
        expected_token = getattr(settings, "OISHA_API_SECRET", "")

        is_authorized = False
        if expected_token and auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
            if token and expected_token and hmac.compare_digest(token.encode("utf-8"), expected_token.encode("utf-8")):
                is_authorized = True

        if not is_authorized:
            return JSONResponse(
                {"detail": "Unauthorized. Bearer token missing or invalid."},
                status_code=401,
                headers={"WWW-Authenticate": "Bearer"},
            )

    return await call_next(request)


# Include internal subpackage routers
app.include_router(webhooks_module.router)
app.include_router(oauth_module.router)
app.include_router(dashboard_module.router)

# Include existing routers
from src.api import admin, dashboard
from src.api.live_monitor import router as live_monitor_router

app.include_router(dashboard.router)
app.include_router(admin.router)
app.include_router(live_monitor_router)

# Hisobchi MCP router
try:
    from src.services.core.hisobchi_mcp import mcp_router
    if mcp_router is not None:
        app.include_router(mcp_router)
        logger.info("[MCP] Hisobchi MCP router mounted at /mcp")
except Exception as exc:
    logger.warning("[MCP] Hisobchi MCP router not mounted: %s", exc)

# Telegram SSE MCP Server
try:
    import sys
    sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "scripts"))
    from oisha_mcp_server import mcp as telegram_mcp_instance
    app.mount("/telegram-mcp", telegram_mcp_instance.sse_app(mount_path="/telegram-mcp"))
    logger.info("[MCP] Telegram SSE MCP server mounted at /telegram-mcp")
except Exception as exc:
    logger.warning("[MCP] Failed to mount Telegram SSE MCP: %s", exc)


# Include route modules
from src.api.routes.health import router as health_router, liveness_probe
from src.api.routes.telegram_routes import router as telegram_router
from src.api.routes.telegram_mcp import router as telegram_mcp_router
from src.api.routes.system_dashboard import router as system_router
from src.api.routes.sales_quality import router as sales_quality_router
from src.api.routes.chat_widget import router as chat_router
from src.api.routes.amocrm_integration import router as amocrm_router
from src.api.routes.amocrm_chats import router as amocrm_chats_router
from src.api.routes.openclaw_gateway import router as openclaw_router
from src.api.routes.ai_analytics import router as ai_router
from src.api.routes.erp_routes import router as erp_router
from src.api.routes.instagram_routes import router as instagram_router
from src.api.routes.product_suite import router as product_router
from src.api.routes.business_commands import router as business_commands_router
from src.api.routes.crm_dashboard import router as crm_dashboard_router
from src.api.routes.finance_dashboard import router as finance_dashboard_router
from src.api.routes.marketing_dashboard import router as marketing_router
from src.api.routes.callmaster_routes import router as callmaster_router
from src.api.routes.dashboard_overview import router as dashboard_overview_router

app.include_router(health_router)
app.include_router(telegram_router)
app.include_router(telegram_mcp_router)
app.include_router(system_router)
app.include_router(sales_quality_router)
app.include_router(chat_router)
app.include_router(amocrm_router)
app.include_router(amocrm_chats_router)
app.include_router(openclaw_router)
app.include_router(ai_router)
app.include_router(erp_router)
app.include_router(instagram_router)
app.include_router(product_router)
app.include_router(business_commands_router)
app.include_router(crm_dashboard_router)
app.include_router(finance_dashboard_router)
app.include_router(marketing_router)
app.include_router(callmaster_router)
app.include_router(dashboard_overview_router)

app.add_api_route("/health", liveness_probe, methods=["GET"], include_in_schema=False)
app.add_api_route("/healthz", liveness_probe, methods=["GET"], include_in_schema=False)
app.add_api_route("/healthz/", liveness_probe, methods=["GET"], include_in_schema=False)

# Mount Static Files
static_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "src", "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

# CORS Middleware
_CORS_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
    "*",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
