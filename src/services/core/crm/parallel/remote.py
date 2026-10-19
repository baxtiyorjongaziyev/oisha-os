"""Strict HTTP adapter reusing the existing runtime's amoCRM authentication."""
from __future__ import annotations

import asyncio
from typing import Any

import requests

from .schema import RemoteLead


class RemoteUnavailable(RuntimeError):
    pass


class RemoteMissing(RemoteUnavailable):
    pass


class AmoRemote:
    def __init__(self, client):
        self.client = client

    async def request(self, method: str, path: str, **kwargs) -> dict:
        if not path.startswith("/api/v4/"):
            raise ValueError("Unsupported endpoint")
        try:
            response = await self.client._request_with_auth(
                getattr(requests, method), self.client.base_url + path,
                timeout=30, **kwargs,
            )
            if response.status_code == 401:
                refreshed = await asyncio.to_thread(self.client.refresh_token)
                if refreshed:
                    response = await self.client._request_with_auth(
                        getattr(requests, method), self.client.base_url + path,
                        timeout=30, **kwargs,
                    )
            if method == "get" and response.status_code == 204:
                return {"_embedded": {}}
            if response.status_code == 404:
                raise RemoteMissing("amocrm_not_found")
            if response.status_code != 200:
                raise RemoteUnavailable("amocrm_http_" + str(response.status_code))
            data = response.json()
            if not isinstance(data, dict):
                raise RemoteUnavailable("amocrm_invalid_response")
            return data
        except RemoteUnavailable:
            raise
        except Exception as exc:
            raise RemoteUnavailable("amocrm_request_failed") from exc

    async def page(self, kind: str, page: int, start: int, end: int) -> tuple[list, bool]:
        paths = {
            "leads": "/api/v4/leads", "contacts": "/api/v4/contacts",
            "tasks": "/api/v4/tasks", "users": "/api/v4/users",
            "pipelines": "/api/v4/leads/pipelines",
        }
        params: dict[str, Any] = {"page": page, "limit": 250}
        if kind in {"leads", "contacts", "tasks"}:
            # No upper bound: edits during pagination must not remove rows from
            # the current collection. The checkpoint remains the scan START.
            params["filter[updated_at][from]"] = max(0, start - 120)
            params["order[id]"] = "asc"
        if kind == "leads":
            params["with"] = "contacts"
        data = await self.request("get", paths[kind], params=params)
        embedded = data.get("_embedded")
        if not isinstance(embedded, dict):
            raise RemoteUnavailable("amocrm_invalid_collection")
        rows = embedded.get(kind, [])
        if not isinstance(rows, list):
            raise RemoteUnavailable("amocrm_invalid_collection")
        return rows, bool(data.get("_links", {}).get("next"))

    async def lead(self, lead_id: int) -> dict:
        data = await self.request("get", f"/api/v4/leads/{lead_id}",
                                  params={"with": "contacts"})
        return RemoteLead.model_validate(data).model_dump()

    async def patch(self, lead_id: int, patch: dict) -> None:
        # No automatic retry after a PATCH: a timeout is an ambiguous outcome.
        await self.request("patch", f"/api/v4/leads/{lead_id}", json=patch)

    async def account(self) -> dict:
        return await self.request("get", "/api/v4/account")

    async def notes(self, lead_id: int) -> list:
        data = await self.request("get", f"/api/v4/leads/{lead_id}/notes",
                                  params={"limit": 50, "order[updated_at]": "desc"})
        notes = data.get("_embedded", {}).get("notes", [])
        if not isinstance(notes, list):
            raise RemoteUnavailable("amocrm_invalid_notes")
        # Do not expose recording URLs or widget payloads. The original is linked.
        return [{"id": n["id"], "created_at": n.get("created_at"),
                 "type": n.get("note_type"),
                 "text": n.get("params", {}).get("text", "")[:10000]}
                for n in notes if isinstance(n, dict) and "id" in n]
