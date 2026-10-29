# src/amocrm_sync.py
"""amoCRM integration module for Oisha‑OS.
Provides:
- OAuth token handling (access / refresh)
- Simple GET / POST helper wrappers
- High‑level helpers used by agents (list_contacts, get_deal, upsert_deal, register_webhook)
"""
import os
import time
import httpx
from pathlib import Path
from .settings import (
    AMOCRM_SUBDOMAIN,
    AMOCRM_CLIENT_ID,
    AMOCRM_CLIENT_SECRET,
    AMOCRM_REDIRECT_URI,
    AMOCRM_LONG_LIVED_TOKEN,
)

BASE_URL = f"https://{AMOCRM_SUBDOMAIN}.amocrm.ru"
TOKEN_URL = f"{BASE_URL}/oauth2/access_token"

# ----------------------------------------------------------------------
# Token management – store tokens in kv_settings (existing helpers)
# ----------------------------------------------------------------------
def _store_token(data: dict) -> None:
    """Persist access & refresh token in kv_settings.
    The project already has ``set_kv_setting`` helper in ``src/database``.
    """
    from .database import set_kv_setting

    set_kv_setting("AMOCRM_ACCESS_TOKEN", data["access_token"])
    set_kv_setting("AMOCRM_REFRESH_TOKEN", data["refresh_token"])
    # ``expires_in`` is seconds (default 86400). Keep a safety buffer.
    expires_at = int(time.time()) + data.get("expires_in", 86400) - 60
    set_kv_setting("AMOCRM_EXPIRES_AT", str(expires_at))


def _load_token() -> dict:
    from .database import get_kv_setting

    return {
        "access_token": get_kv_setting("AMOCRM_ACCESS_TOKEN") or "",
        "refresh_token": get_kv_setting("AMOCRM_REFRESH_TOKEN") or "",
        "expires_at": int(get_kv_setting("AMOCRM_EXPIRES_AT") or "0"),
    }


def _refresh_token_if_needed() -> str:
    token = _load_token()
    if not token["access_token"] or token["expires_at"] < int(time.time()):
        # Refresh flow
        payload = {
            "client_id": AMOCRM_CLIENT_ID,
            "client_secret": AMOCRM_CLIENT_SECRET,
            "grant_type": "refresh_token",
            "refresh_token": token["refresh_token"],
            "redirect_uri": AMOCRM_REDIRECT_URI,
        }
        resp = httpx.post(TOKEN_URL, data=payload, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        _store_token(data)
        return data["access_token"]
    return token["access_token"]

# ----------------------------------------------------------------------
# Low‑level wrappers
# ----------------------------------------------------------------------
def _api_get(path: str, params: dict | None = None) -> dict:
    access_token = _refresh_token_if_needed()
    headers = {"Authorization": f"Bearer {access_token}"}
    url = f"{BASE_URL}{path}"
    resp = httpx.get(url, headers=headers, params=params, timeout=20)
    resp.raise_for_status()
    return resp.json()


def _api_post(path: str, json_body: dict) -> dict:
    access_token = _refresh_token_if_needed()
    headers = {"Authorization": f"Bearer {access_token}"}
    url = f"{BASE_URL}{path}"
    resp = httpx.post(url, headers=headers, json=json_body, timeout=20)
    resp.raise_for_status()
    return resp.json()

# ----------------------------------------------------------------------
# Public helpers used by Oisha‑OS agents / workflows
# ----------------------------------------------------------------------
def list_contacts(limit: int = 50, offset: int = 0) -> list[dict]:
    """Return a list of contacts (leads) from amoCRM."""
    data = _api_get("/api/v4/contacts", params={"limit": limit, "offset": offset})
    return data.get("_embedded", {}).get("contacts", [])


def get_deal(deal_id: int) -> dict:
    """Fetch a single deal by its ID."""
    return _api_get(f"/api/v4/leads/{deal_id}")


def upsert_deal(deal: dict) -> dict:
    """Create or update a deal.
    If ``deal`` contains ``id`` → update, otherwise create.
    """
    if "id" in deal:
        return _api_post(f"/api/v4/leads/{deal['id']}", deal)
    else:
        return _api_post("/api/v4/leads", deal)


def register_webhook(event: str, target_url: str) -> dict:
    """Register a webhook for a specific amoCRM event.
    ``event`` examples: ``lead_added``, ``lead_status_changed``.
    """
    payload = {
        "destination": target_url,
        "events": [event],
        "settings": {"post_to_chat": False},
    }
    return _api_post("/api/v4/webhooks", payload)
