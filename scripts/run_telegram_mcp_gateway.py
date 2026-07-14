from __future__ import annotations

import os

import uvicorn

from src.services.core.telegram_mcp.approval_ui import TelegramApprovalNotifier
from src.services.core.telegram_mcp.gateway import GatewayService, build_http_app
from src.services.core.telegram_mcp.store import ApprovalStore
from src.services.core.telegram_mcp.upstream import UpstreamClient


def _secret(value: object) -> str:
    getter = getattr(value, "get_secret_value", None)
    return str(getter() if callable(getter) else value or "").strip()


def main() -> None:
    from src.settings import settings

    host = os.getenv("TELEGRAM_MCP_GATEWAY_HOST", "127.0.0.1")
    port = int(os.getenv("TELEGRAM_MCP_GATEWAY_PORT", "8766"))
    if host not in {"127.0.0.1", "localhost"}:
        raise RuntimeError("Telegram MCP gateway must bind to loopback")
    upstream = UpstreamClient(settings.TELEGRAM_MCP_UPSTREAM_URL)
    store = ApprovalStore("data/telegram_mcp_approvals.db")
    notifier = TelegramApprovalNotifier(
        _secret(settings.BOT_TOKEN), settings.OWNER_ID
    )
    service = GatewayService(
        upstream,
        store,
        notifier,
        approval_ttl_seconds=settings.TELEGRAM_MCP_APPROVAL_TTL_SECONDS,
    )
    uvicorn.run(build_http_app(service), host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
