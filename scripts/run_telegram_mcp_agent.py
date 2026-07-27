from __future__ import annotations

import argparse
import asyncio
import os
from urllib.parse import urlparse

from mcp.server.stdio import stdio_server

from src.services.core.telegram_mcp.approval_ui import TelegramApprovalNotifier
from src.services.core.telegram_mcp.gateway import (
    GatewayService,
    build_mcp_server,
    parse_allowed_agent_ids,
    require_allowed_agent_id,
)
from src.services.core.telegram_mcp.store import ApprovalStore
from src.services.core.telegram_mcp.upstream import UpstreamClient


def _secret(value: object) -> str:
    getter = getattr(value, "get_secret_value", None)
    return str(getter() if callable(getter) else value or "").strip()


def _require_loopback_url(value: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"}:
        raise RuntimeError("Telegram MCP upstream must use HTTP")
    if parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise RuntimeError("Telegram MCP upstream must stay on loopback")
    return value


async def run(agent_id: str) -> None:
    from src.settings import settings

    allowed = parse_allowed_agent_ids(os.getenv("TELEGRAM_MCP_AGENT_IDS"))
    requester = require_allowed_agent_id(agent_id, allowed)
    upstream_url = _require_loopback_url(settings.TELEGRAM_MCP_UPSTREAM_URL)
    service = GatewayService(
        UpstreamClient(upstream_url),
        ApprovalStore("data/telegram_mcp_approvals.db"),
        TelegramApprovalNotifier(_secret(settings.BOT_TOKEN), settings.OWNER_ID),
        approval_ttl_seconds=settings.TELEGRAM_MCP_APPROVAL_TTL_SECONDS,
    )
    server = build_mcp_server(service, requester=requester)
    await service.start()
    try:
        async with stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream,
                write_stream,
                server.create_initialization_options(),
            )
    finally:
        await service.stop()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Approval-gated Oisha Telegram MCP bridge for one AI agent."
    )
    parser.add_argument("--agent", required=True)
    args = parser.parse_args()
    asyncio.run(run(args.agent))


if __name__ == "__main__":
    main()
