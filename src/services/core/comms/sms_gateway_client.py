"""SMS Gateway for Android cloud-mode client.

Default flow:
    Oisha -> api.sms-gate.app -> Android phone -> SMS

The client is intentionally small and disabled by default. Configure with:
    SMS_GATEWAY_ENABLED=true
    SMS_GATEWAY_BASE_URL=https://api.sms-gate.app/3rdparty/v1
    SMS_GATEWAY_USERNAME=...
    SMS_GATEWAY_PASSWORD=...
"""
from __future__ import annotations

from dataclasses import dataclass
import os
import re
from typing import Any, Iterable

import httpx


DEFAULT_SMS_GATEWAY_BASE_URL = "https://api.sms-gate.app/3rdparty/v1"
_PHONE_RE = re.compile(r"^\+\d{8,15}$")


class SmsGatewayError(RuntimeError):
    """Raised when SMS Gateway rejects or cannot complete a request."""


@dataclass(frozen=True)
class SmsGatewayConfig:
    enabled: bool = False
    base_url: str = DEFAULT_SMS_GATEWAY_BASE_URL
    username: str = ""
    password: str = ""
    timeout_seconds: float = 15.0

    @classmethod
    def from_env(cls) -> "SmsGatewayConfig":
        enabled = os.getenv("SMS_GATEWAY_ENABLED", "").strip().lower() in {"1", "true", "yes", "on"}
        return cls(
            enabled=enabled,
            base_url=(os.getenv("SMS_GATEWAY_BASE_URL") or DEFAULT_SMS_GATEWAY_BASE_URL).rstrip("/"),
            username=os.getenv("SMS_GATEWAY_USERNAME", "").strip(),
            password=os.getenv("SMS_GATEWAY_PASSWORD", "").strip(),
            timeout_seconds=float(os.getenv("SMS_GATEWAY_TIMEOUT_SECONDS", "15") or 15),
        )

    @property
    def is_ready(self) -> bool:
        return self.enabled and bool(self.username and self.password and self.base_url)


@dataclass(frozen=True)
class SmsSendResult:
    ok: bool
    status_code: int | None
    message_id: str | None = None
    raw: dict[str, Any] | list[Any] | str | None = None


class SmsGatewayClient:
    """Async client for capcom6/android-sms-gateway cloud/private API."""

    def __init__(self, config: SmsGatewayConfig | None = None, client: httpx.AsyncClient | None = None) -> None:
        self.config = config or SmsGatewayConfig.from_env()
        self._client = client

    def _normalize_phones(self, phone_numbers: str | Iterable[str]) -> list[str]:
        phones = [phone_numbers] if isinstance(phone_numbers, str) else list(phone_numbers)
        normalized = [phone.strip().replace(" ", "") for phone in phones if str(phone).strip()]
        invalid = [phone for phone in normalized if not _PHONE_RE.match(phone)]
        if invalid:
            raise ValueError(f"Invalid E.164 phone number(s): {', '.join(invalid)}")
        if not normalized:
            raise ValueError("At least one phone number is required")
        return normalized

    async def send_sms(self, phone_numbers: str | Iterable[str], text: str) -> SmsSendResult:
        """Send an SMS via SMS Gateway for Android.

        Does not silently send when credentials are missing; disabled config returns
        a safe no-op result so production can boot without SMS credentials.
        """
        message = (text or "").strip()
        if not message:
            raise ValueError("SMS text is required")
        phones = self._normalize_phones(phone_numbers)
        if not self.config.is_ready:
            return SmsSendResult(ok=False, status_code=None, raw={"disabled": True})

        payload = {
            "textMessage": {"text": message},
            "phoneNumbers": phones,
        }
        url = f"{self.config.base_url}/message"
        close_client = False
        client = self._client
        if client is None:
            client = httpx.AsyncClient(timeout=self.config.timeout_seconds)
            close_client = True
        try:
            response = await client.post(
                url,
                json=payload,
                auth=(self.config.username, self.config.password),
                headers={"Content-Type": "application/json"},
            )
            raw: dict[str, Any] | list[Any] | str
            try:
                raw = response.json()
            except ValueError:
                raw = response.text
            if response.status_code >= 400:
                raise SmsGatewayError(f"SMS gateway failed with HTTP {response.status_code}: {raw}")
            return SmsSendResult(
                ok=True,
                status_code=response.status_code,
                message_id=_extract_message_id(raw),
                raw=raw,
            )
        finally:
            if close_client:
                await client.aclose()


def _extract_message_id(raw: dict[str, Any] | list[Any] | str) -> str | None:
    if isinstance(raw, dict):
        for key in ("id", "messageId", "message_id", "uuid"):
            value = raw.get(key)
            if value:
                return str(value)
        payload = raw.get("payload")
        if isinstance(payload, dict):
            return _extract_message_id(payload)
    if isinstance(raw, list) and raw:
        return _extract_message_id(raw[0])
    return None


def parse_sms_webhook(payload: dict[str, Any]) -> dict[str, Any]:
    """Normalize SMS Gateway webhook payload into Oisha-friendly fields."""
    event = str(payload.get("event") or "")
    body = payload.get("payload") if isinstance(payload.get("payload"), dict) else payload
    return {
        "event": event,
        "message_id": body.get("messageId") or body.get("id"),
        "phone_number": body.get("phoneNumber"),
        "text": body.get("message") or body.get("text") or "",
        "sim_number": body.get("simNumber"),
        "received_at": body.get("receivedAt"),
        "raw": payload,
    }
