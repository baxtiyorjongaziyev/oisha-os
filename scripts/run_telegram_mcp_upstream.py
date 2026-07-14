from __future__ import annotations

import os


def main() -> None:
    dedicated = (os.getenv("TELEGRAM_MCP_SESSION_STRING") or "").strip()
    production = (os.getenv("USERBOT_SESSION_STRING") or "").strip()
    if not dedicated:
        raise RuntimeError("TELEGRAM_MCP_SESSION_STRING is required")
    if production and dedicated == production:
        raise RuntimeError("Telegram MCP must not reuse USERBOT_SESSION_STRING")
    os.environ["TELEGRAM_SESSION_STRING"] = dedicated
    os.environ.setdefault("TELEGRAM_API_ID", os.getenv("API_ID", ""))
    os.environ.setdefault("TELEGRAM_API_HASH", os.getenv("API_HASH", ""))
    os.environ.setdefault("TELEGRAM_EXPOSED_TOOLS", "all")
    os.environ["MCP_TRANSPORT"] = "http"
    os.environ["MCP_HOST"] = "127.0.0.1"
    os.environ["MCP_PORT"] = "8765"

    from main import main as telegram_mcp_main

    telegram_mcp_main()


if __name__ == "__main__":
    main()
