"""Live smoke test against the REAL Telegram MCP upstream (run on Contabo, read-only).

    cd prototypes/codemode && python smoke_live.py [http://127.0.0.1:8765/mcp]

Uses an in-memory store that refuses writes, so no approval/mutation can happen.
Prints the TS API the model would see, then runs `telegram.get_me()`.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).parent))

from host import CodeModeHost  # noqa: E402
from src.services.core.telegram_mcp.gateway import GatewayService  # noqa: E402
from src.services.core.telegram_mcp.upstream import UpstreamClient  # noqa: E402


class ReadOnlyStore:
    async def initialize(self):
        pass

    async def create(self, *a, **k):
        raise RuntimeError("smoke test must not create approvals")

    async def finish_notification_failure(self, *a):
        pass


async def main(url: str) -> None:
    service = GatewayService(UpstreamClient(url), ReadOnlyStore(), SimpleNamespace())
    await service.start()
    try:
        host = CodeModeHost(service)
        api = await host.describe()
        print(f"--- TS API ({len(api)} chars, {api.count(chr(10))} lines) ---")
        print(api[:600], "...\n")
        out = await host.run("return await telegram.get_me({});", timeout=30)
        print("get_me ->", str(out["result"])[:300])
    finally:
        await service.stop()


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8765/mcp"))
