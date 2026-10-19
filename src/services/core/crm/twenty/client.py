"""Twenty REST client with explicit outcomes.

Reads are retried on transient failures. Writes are retried only when the
request provably never reached the server (connect error) or the server
explicitly rejected it before processing (429). A timeout or 5xx after a write
is reported as ``TwentyUncertain`` so callers reconcile instead of re-posting.
"""
from __future__ import annotations

import asyncio
import os
from typing import Any

import httpx


class TwentyError(RuntimeError):
    """Definite failure: the write did not happen."""


class TwentyUncertain(TwentyError):
    """Outcome unknown: the write may or may not have been applied."""


class TwentyNotConfigured(TwentyError):
    pass


def config_from_env() -> tuple[str, str]:
    url = os.getenv("TWENTY_API_URL", "").strip().rstrip("/")
    key = os.getenv("TWENTY_API_KEY", "").strip()
    if not url or not key:
        raise TwentyNotConfigured("twenty_not_configured")
    return url, key


class TwentyClient:
    def __init__(self, base_url: str, api_key: str, *, transport=None,
                 retries: int = 3, backoff: float = 1.0, sleep=asyncio.sleep):
        if not base_url or not api_key:
            raise TwentyNotConfigured("twenty_not_configured")
        self._http = httpx.AsyncClient(
            base_url=base_url.rstrip("/") + "/rest",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=httpx.Timeout(20.0, connect=5.0),
            transport=transport,
        )
        self.retries, self.backoff, self._sleep = retries, backoff, sleep

    async def aclose(self) -> None:
        await self._http.aclose()

    async def _send(self, method: str, path: str, **kwargs) -> dict:
        write = method != "GET"
        for attempt in range(self.retries + 1):
            last = attempt == self.retries
            try:
                response = await self._http.request(method, path, **kwargs)
            except httpx.ConnectError as exc:
                if last:
                    raise TwentyError("twenty_unreachable") from exc
                await self._sleep(self.backoff * 2 ** attempt)
                continue
            except httpx.TransportError as exc:
                if write:
                    raise TwentyUncertain("twenty_write_timeout") from exc
                if last:
                    raise TwentyError("twenty_read_failed") from exc
                await self._sleep(self.backoff * 2 ** attempt)
                continue
            status = response.status_code
            if status == 429 or (status >= 500 and not write):
                if last:
                    raise TwentyError(f"twenty_http_{status}")
                retry_after = response.headers.get("retry-after", "")
                delay = float(retry_after) if retry_after.isdigit() else self.backoff * 2 ** attempt
                await self._sleep(min(delay, 60.0))
                continue
            if status >= 500:
                raise TwentyUncertain(f"twenty_http_{status}")
            if status >= 400:
                raise TwentyError(f"twenty_http_{status}")
            data = response.json() if response.content else {}
            if not isinstance(data, dict):
                raise TwentyError("twenty_invalid_response")
            return data
        raise TwentyError("twenty_retry_exhausted")

    @staticmethod
    def _record(data: dict, key: str) -> dict:
        record = (data.get("data") or {}).get(key)
        if not isinstance(record, dict) or not record.get("id"):
            raise TwentyError("twenty_missing_record")
        return record

    async def create(self, plural: str, singular: str, body: dict) -> dict:
        data = await self._send("POST", f"/{plural}", json=body)
        return self._record(data, "create" + singular[0].upper() + singular[1:])

    async def update(self, plural: str, singular: str, record_id: str, body: dict) -> dict:
        data = await self._send("PATCH", f"/{plural}/{record_id}", json=body)
        return self._record(data, "update" + singular[0].upper() + singular[1:])

    async def get(self, plural: str, record_id: str) -> dict | None:
        try:
            data = await self._send("GET", f"/{plural}/{record_id}")
        except TwentyError as exc:
            if str(exc) == "twenty_http_404":
                return None
            raise
        records = data.get("data") or {}
        return next((v for v in records.values() if isinstance(v, dict)), None)

    async def find(self, plural: str, flt: str, limit: int = 2) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"limit": limit}
        if flt:
            params["filter"] = flt
        data = await self._send("GET", f"/{plural}", params=params)
        rows = (data.get("data") or {}).get(plural)
        if not isinstance(rows, list):
            raise TwentyError("twenty_invalid_collection")
        return rows

    async def members(self) -> list[dict[str, Any]]:
        return await self.find("workspaceMembers", "", limit=200)
