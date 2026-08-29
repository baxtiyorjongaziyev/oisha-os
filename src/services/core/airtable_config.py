"""Fail-closed Airtable credential access for runtime integrations."""

from typing import Any

import httpx

from src.settings import settings


class AirtableConfigurationError(RuntimeError):
    """Raised when Airtable cannot be used without a configured secret."""


class AirtableResponseError(RuntimeError):
    """Raised when Airtable returns a successful but unsafe response shape."""


def _secret_value(configured: Any) -> str:
    if hasattr(configured, "get_secret_value"):
        configured = configured.get_secret_value()
    return configured.strip() if isinstance(configured, str) else ""


def require_airtable_api_key() -> str:
    """Return the configured Airtable PAT without allowing a code fallback."""
    api_key = _secret_value(getattr(settings, "AIRTABLE_API_KEY", None))
    if not api_key:
        raise AirtableConfigurationError(
            "AIRTABLE_API_KEY is required in the runtime secret configuration"
        )
    return api_key


def airtable_request_headers() -> dict[str, str]:
    """Build Airtable headers only after secret configuration is validated."""
    return {
        "Authorization": f"Bearer {require_airtable_api_key()}",
        "Content-Type": "application/json",
    }


def airtable_records_page(
    response: httpx.Response,
    *,
    resource: str,
) -> tuple[list[dict[str, Any]], str | None]:
    """Validate an Airtable records page before callers use it for decisions."""
    response.raise_for_status()
    try:
        payload = response.json()
    except ValueError as exc:
        raise AirtableResponseError(
            f"Airtable {resource} response was not valid JSON"
        ) from exc
    if not isinstance(payload, dict):
        raise AirtableResponseError(
            f"Airtable {resource} response must be a JSON object"
        )

    records = payload.get("records")
    if not isinstance(records, list) or any(
        not isinstance(record, dict) for record in records
    ):
        raise AirtableResponseError(
            f"Airtable {resource} response requires a records list"
        )

    offset = payload.get("offset")
    if offset is not None and (
        not isinstance(offset, str) or not offset.strip()
    ):
        raise AirtableResponseError(
            f"Airtable {resource} response contains an invalid offset"
        )
    return records, offset
