"""SalesCoach AI HTTP bridge for Oisha-OS."""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, Dict, List, Optional

import httpx

from src.context import app_ctx
from src.settings import settings

logger = logging.getLogger("SalesCoachSync")


def _secret_text(value: Any) -> str:
    getter = getattr(value, "get_secret_value", None)
    return str(getter() if callable(getter) else value or "").strip()


def _cfg(name: str, default: Any) -> Any:
    """Read typed settings first, then undeclared deployment env vars safely."""
    configured = getattr(settings, name, None)
    if configured is not None and not (
        isinstance(configured, str) and not configured.strip()
    ):
        return configured

    raw = os.getenv(name)
    if raw is None:
        return default
    if isinstance(default, bool):
        return raw.strip().lower() in {"1", "true", "yes", "on"}
    if isinstance(default, int):
        try:
            return int(raw)
        except ValueError:
            return default
    if isinstance(default, float):
        try:
            return float(raw)
        except ValueError:
            return default
    return raw


class SalesCoachSync:
    """Client for the side-by-side salescoach-ai REST API."""

    def __init__(self):
        self.base_url = str(_cfg("SALESCOACH_API_URL", "")).rstrip("/")
        self.token = _secret_text(_cfg("SALESCOACH_SERVICE_TOKEN", ""))
        self.enabled = bool(_cfg("SALESCOACH_ENABLED", False)) and bool(self.base_url)
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            headers = {"Content-Type": "application/json"}
            if self.token:
                headers["Authorization"] = f"Bearer {self.token}"
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=headers,
                timeout=15.0,
            )
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def get_suggestion(
        self,
        message: str,
        history: Optional[List[Dict]] = None,
        crm_status: str = "",
        service_type: str = "branding",
        customer_name: str = "",
    ) -> Optional[Dict[str, Any]]:
        if not self.enabled:
            return None
        try:
            payload = {
                "message": message,
                "history": history or [],
                "crmStatus": crm_status,
                "serviceType": service_type,
            }
            if customer_name:
                payload["customerName"] = customer_name
            response = await self.client.post("/v1/negotiations/suggest", json=payload)
            response.raise_for_status()
            data = response.json()
            return data if isinstance(data, dict) else None
        except Exception as exc:
            logger.warning(
                "[SalesCoach] suggestion failed: %s",
                type(exc).__name__,
            )
            return None

    async def analyze_conversation(
        self,
        *,
        lead_id: int,
        manager_id: str,
        messages: List[Dict[str, Any]],
        crm_status: str = "",
    ) -> Optional[Dict[str, Any]]:
        """Send a bounded Telegram business-dialog batch for structured scoring."""
        if not self.enabled:
            return None

        bounded_messages = []
        for message in messages[-50:]:
            text = str(message.get("text") or "").strip()
            if not text:
                continue
            bounded = dict(message)
            bounded["text"] = text[:4000]
            bounded_messages.append(bounded)
        if not bounded_messages:
            return None
        payload = {
            "leadId": int(lead_id),
            "managerId": str(manager_id),
            "crmStatus": crm_status,
            "messages": bounded_messages,
        }
        for attempt in range(5):
            try:
                response = await self.client.post(
                    "/v1/negotiations/analyze-conversation",
                    json=payload,
                    timeout=30.0,
                )
                response.raise_for_status()
                data = response.json()
                return data if isinstance(data, dict) else None
            except Exception as exc:
                logger.warning(
                    "[SalesCoach] conversation analysis attempt %s failed: %s",
                    attempt + 1,
                    type(exc).__name__,
                )
                if attempt < 4:
                    await asyncio.sleep(0.25 * (2**attempt))
        return None

    async def get_realtime_tip(
        self,
        message: str,
        crm_status: str = "",
    ) -> Optional[Dict[str, Any]]:
        if not self.enabled:
            return None
        try:
            response = await self.client.post(
                "/v1/negotiations/realtime",
                json={"message": message, "crmStatus": crm_status},
            )
            response.raise_for_status()
            data = response.json()
            return data if isinstance(data, dict) else None
        except Exception as exc:
            logger.warning(
                "[SalesCoach] realtime tip failed: %s",
                type(exc).__name__,
            )
            return None

    async def upload_voice(
        self,
        audio_bytes: bytes,
        customer_name: str = "",
        customer_phone: str = "",
        direction: str = "OUTBOUND",
        content_type: str = "audio/ogg",
        ext: str = "ogg",
    ) -> Optional[Dict[str, Any]]:
        if not self.enabled:
            return None
        try:
            init_response = await self.client.post(
                "/v1/calls",
                json={
                    "customerName": customer_name or None,
                    "customerPhone": customer_phone or None,
                    "direction": direction,
                    "ext": ext,
                    "contentType": content_type,
                },
            )
            init_response.raise_for_status()
            init_data = init_response.json()
            call_id = init_data["callId"]
            upload_url = init_data["uploadUrl"]

            upload_response = await self.client.put(
                upload_url,
                content=audio_bytes,
                headers={"Content-Type": content_type},
            )
            if upload_response.status_code not in (200, 204):
                raise RuntimeError(
                    f"S3 upload failed: {upload_response.status_code}"
                )

            confirm_response = await self.client.post(
                f"/v1/calls/{call_id}/confirm",
                json={},
            )
            confirm_response.raise_for_status()
            logger.info("[SalesCoach] call uploaded: %s", call_id)
            return {"callId": call_id, "status": "TRANSCRIBING"}
        except Exception as exc:
            logger.warning(
                "[SalesCoach] voice upload failed: %s",
                type(exc).__name__,
            )
            return None

    async def get_pipeline_insights(
        self,
        days: int = 7,
    ) -> Optional[Dict[str, Any]]:
        if not self.enabled:
            return None
        try:
            response = await self.client.get(
                f"/v1/negotiations/pipeline-insights?days={days}"
            )
            response.raise_for_status()
            data = response.json()
            return data if isinstance(data, dict) else None
        except Exception as exc:
            logger.warning(
                "[SalesCoach] pipeline insights failed: %s",
                type(exc).__name__,
            )
            return None


app_ctx.salescoach_sync: Optional[SalesCoachSync] = None


def get_salescoach_sync() -> SalesCoachSync:
    if app_ctx.salescoach_sync is None:
        app_ctx.salescoach_sync = SalesCoachSync()
    return app_ctx.salescoach_sync
