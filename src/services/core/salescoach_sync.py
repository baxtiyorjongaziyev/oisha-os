"""
SalesCoach AI HTTP Bridge
oisha-os → salescoach-ai API ga so'rovlar yuboradi.

⚠️ settings.py YANGILANMAYDI (Coordinator owns) — env varlar getattr bilan o'qiladi.
Coordinator settings.py ga qo'shishi kerak: SALESCOACH_API_URL, SALESCOACH_SERVICE_TOKEN,
SALESCOACH_ENABLED.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import httpx

from src.settings import settings

logger = logging.getLogger("SalesCoachSync")


def _cfg(name: str, default):
    return getattr(settings, name, default)


class SalesCoachSync:
    """salescoach-ai REST API bilan muloqot qiluvchi klient."""

    def __init__(self):
        self.base_url = str(_cfg("SALESCOACH_API_URL", "")).rstrip("/")
        self.token = str(_cfg("SALESCOACH_SERVICE_TOKEN", ""))
        self.enabled = bool(_cfg("SALESCOACH_ENABLED", False)) and bool(self.base_url)
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            headers = {"Content-Type": "application/json"}
            if self.token:
                headers["Authorization"] = f"Bearer {self.token}"
            self._client = httpx.AsyncClient(
                base_url=self.base_url, headers=headers, timeout=15.0
            )
        return self._client

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    # ── Negotiation Suggestion ─────────────────────────────────

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
            resp = await self.client.post("/v1/negotiations/suggest", json=payload)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.warning(f"[SalesCoach] get_suggestion failed: {e}")
            return None

    # ── Realtime Tip ───────────────────────────────────────────

    async def get_realtime_tip(
        self, message: str, crm_status: str = ""
    ) -> Optional[Dict[str, Any]]:
        if not self.enabled:
            return None
        try:
            resp = await self.client.post(
                "/v1/negotiations/realtime",
                json={"message": message, "crmStatus": crm_status},
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.warning(f"[SalesCoach] get_realtime_tip failed: {e}")
            return None

    # ── Voice Upload for Scoring ───────────────────────────────

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
            init_resp = await self.client.post(
                "/v1/calls",
                json={
                    "customerName": customer_name or None,
                    "customerPhone": customer_phone or None,
                    "direction": direction,
                    "ext": ext,
                    "contentType": content_type,
                },
            )
            init_resp.raise_for_status()
            init_data = init_resp.json()
            call_id = init_data["callId"]
            upload_url = init_data["uploadUrl"]

            s3_resp = await self.client.put(
                upload_url, content=audio_bytes, headers={"Content-Type": content_type}
            )
            if s3_resp.status_code not in (200, 204):
                raise RuntimeError(f"S3 upload failed: {s3_resp.status_code}")

            confirm_resp = await self.client.post(f"/v1/calls/{call_id}/confirm", json={})
            confirm_resp.raise_for_status()

            logger.info(f"[SalesCoach] Call uploaded: {call_id}")
            return {"callId": call_id, "status": "TRANSCRIBING"}
        except Exception as e:
            logger.warning(f"[SalesCoach] upload_voice failed: {e}")
            return None

    # ── Pipeline Insights ──────────────────────────────────────

    async def get_pipeline_insights(self, days: int = 7) -> Optional[Dict[str, Any]]:
        if not self.enabled:
            return None
        try:
            resp = await self.client.get(f"/v1/negotiations/pipeline-insights?days={days}")
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.warning(f"[SalesCoach] get_pipeline_insights failed: {e}")
            return None


_instance: Optional[SalesCoachSync] = None


def get_salescoach_sync() -> SalesCoachSync:
    global _instance
    if _instance is None:
        _instance = SalesCoachSync()
    return _instance
