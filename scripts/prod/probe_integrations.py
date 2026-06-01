"""Read-only production integration probe with secret-safe JSON output."""

import asyncio
import json
import os
import sys
from typing import Any, Dict

import requests

sys.path.insert(0, os.getcwd())

from src.services.core.airtable_sync import AirtableSync
from src.services.core.amocrm_sync import AmoCRMSync
from src.settings import settings


def _secret_text(value: Any) -> str:
    getter = getattr(value, "get_secret_value", None)
    return str(getter() if callable(getter) else value or "")


def _telegram_probe() -> Dict[str, Any]:
    token = _secret_text(settings.BOT_TOKEN).strip()
    result: Dict[str, Any] = {
        "configured": bool(token),
        "bot_ok": False,
        "supports_guest_queries": False,
        "webhook_url_set": False,
        "pending_update_count": None,
        "groups": {},
        "topic_kirim_configured": bool(settings.TOPIC_KIRIM_ID),
    }
    if not token:
        return result

    base_url = f"https://api.telegram.org/bot{token}"
    try:
        response = requests.get(f"{base_url}/getMe", timeout=15)
        payload = response.json()
        result["bot_ok"] = response.status_code == 200 and bool(payload.get("ok"))
        result["supports_guest_queries"] = bool(
            (payload.get("result") or {}).get("supports_guest_queries")
        )
        webhook_response = requests.get(f"{base_url}/getWebhookInfo", timeout=15)
        webhook = webhook_response.json().get("result") or {}
        result["webhook_url_set"] = bool(webhook.get("url"))
        result["pending_update_count"] = webhook.get("pending_update_count")
    except Exception as exc:
        result["error"] = type(exc).__name__
        return result

    for label, chat_id in (
        ("crm_group", settings.CRM_GROUP_ID),
        ("team_group", settings.TEAM_GROUP_ID),
    ):
        if not chat_id:
            result["groups"][label] = {"configured": False}
            continue
        try:
            response = requests.get(
                f"{base_url}/getChat",
                params={"chat_id": chat_id},
                timeout=15,
            )
            payload = response.json()
            result["groups"][label] = {
                "configured": True,
                "ok": response.status_code == 200 and bool(payload.get("ok")),
                "http_status": response.status_code,
            }
        except Exception as exc:
            result["groups"][label] = {
                "configured": True,
                "ok": False,
                "error": type(exc).__name__,
            }

    return result


def _airtable_probe() -> Dict[str, Any]:
    try:
        airtable = AirtableSync()
        response = airtable._request(
            "GET",
            airtable.endpoint,
            retry=False,
            params={"maxRecords": 1},
        )
        return {
            "configured": bool(airtable.api_key and airtable.base_id),
            "ok": response.status_code == 200,
            "http_status": response.status_code,
            "billing_cooldown": response.status_code == 429
            and "PUBLIC_API_BILLING_LIMIT_EXCEEDED" in (response.text or ""),
        }
    except Exception as exc:
        return {"configured": False, "ok": False, "error": type(exc).__name__}


async def _amocrm_probe() -> Dict[str, Any]:
    secret = _secret_text(settings.AMOCRM_CLIENT_SECRET)
    amocrm = AmoCRMSync(
        subdomain=settings.AMOCRM_SUBDOMAIN,
        client_id=settings.AMOCRM_CLIENT_ID,
        client_secret=secret,
        redirect_url=settings.AMOCRM_REDIRECT_URL,
    )
    account_ok = await amocrm.check_connection()
    leads = await amocrm.get_leads_detailed(limit=1) if account_ok else []
    return {
        "configured": bool(settings.AMOCRM_SUBDOMAIN and settings.AMOCRM_CLIENT_ID),
        "account_ok": bool(account_ok),
        "lead_read_ok": bool(account_ok and isinstance(leads, list)),
        "sample_leads": len(leads),
        "last_error": amocrm.last_error,
    }


async def main() -> None:
    result = {
        "amocrm": await _amocrm_probe(),
        "airtable": await asyncio.to_thread(_airtable_probe),
        "telegram_bot_api": await asyncio.to_thread(_telegram_probe),
    }
    print(json.dumps(result, ensure_ascii=True, sort_keys=True))


if __name__ == "__main__":
    asyncio.run(main())
