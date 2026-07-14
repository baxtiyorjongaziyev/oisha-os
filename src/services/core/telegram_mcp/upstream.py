from __future__ import annotations

from contextlib import AsyncExitStack
from typing import Any


class UpstreamClient:
    """Small lifecycle wrapper around a Streamable HTTP MCP server."""

    def __init__(self, url: str):
        if not url.startswith(("http://127.0.0.1:", "http://localhost:")):
            raise ValueError("Telegram MCP upstream must use a loopback URL")
        self.url = url
        self._stack: AsyncExitStack | None = None
        self._session: Any = None

    async def start(self) -> "UpstreamClient":
        if self._session is not None:
            return self
        from mcp import ClientSession
        from mcp.client.streamable_http import streamable_http_client

        stack = AsyncExitStack()
        read_stream, write_stream, _ = await stack.enter_async_context(
            streamable_http_client(self.url)
        )
        session = await stack.enter_async_context(ClientSession(read_stream, write_stream))
        await session.initialize()
        self._stack = stack
        self._session = session
        return self

    async def stop(self) -> None:
        stack, self._stack, self._session = self._stack, None, None
        if stack is not None:
            await stack.aclose()

    async def list_tools(self) -> list[Any]:
        await self.start()
        response = await self._session.list_tools()
        return list(response.tools)

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        await self.start()
        try:
            return await self._session.call_tool(name, arguments)
        except Exception:
            await self.stop()
            raise

    async def __aenter__(self) -> "UpstreamClient":
        return await self.start()

    async def __aexit__(self, *_: Any) -> None:
        await self.stop()
