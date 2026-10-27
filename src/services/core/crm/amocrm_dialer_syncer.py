"""Bidirectional Real-time Synchronizer between amoCRM and Jon CRM (DialerStore).

Ushbu modul amoCRM (jonbranding.amocrm.ru) va Jon CRM (crm.jonbranding.uz)
o'rtasida ikki tomonlama real vaqtda to'liq sinxronlikni ta'minlaydi:
1. Jon CRM da Kanban harakati -> amoCRM ga darhol PATCH bo'ladi.
2. Jon CRM da izoh yozilganda -> amoCRM primetchaniyasiga tushadi.
3. amoCRM da bitim yangilanganida -> Jon CRM ga darhol upsert bo'ladi.
"""
from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

from src.services.core.crm.dialer_store import DialerStore
from src.services.core.crm.pipelines_catalog import resolve_status_info

logger = logging.getLogger("AmoCrmDialerSyncer")

_SUBDOMAIN = "jonbranding"
_TOKEN_FILE = Path("data/amocrm_token.json")


def _get_access_token() -> Optional[str]:
    """Token faylidan yoki Turso DB dan amoCRM access tokenini oladi."""
    try:
        if _TOKEN_FILE.exists():
            data = json.loads(_TOKEN_FILE.read_text(encoding="utf-8"))
            return data.get("access_token")
    except Exception as exc:
        logger.warning("[AMOCRM SYNC] Token read error: %s", exc)
    return None


def _get_headers() -> Dict[str, str]:
    tok = _get_access_token()
    return {
        "Authorization": f"Bearer {tok}",
        "Content-Type": "application/json",
        "User-Agent": "JonBranding-Oisha/2.0",
    }


async def sync_action_to_amocrm(
    lead_id: int,
    status_id: int,
    pipeline_id: int,
    note: Optional[str] = None,
    seller_name: Optional[str] = None,
) -> bool:
    """Jon CRM dan amoCRM ga bitim bosqichi va izohni real-vaqtda sinxronlaydi."""
    token = _get_access_token()
    if not token or not lead_id:
        return False

    url = f"https://{_SUBDOMAIN}.amocrm.ru/api/v4/leads/{lead_id}"
    payload: Dict[str, Any] = {"status_id": int(status_id)}
    if pipeline_id:
        payload["pipeline_id"] = int(pipeline_id)

    headers = _get_headers()
    try:
        res = await asyncio.to_thread(requests.patch, url, headers=headers, json=payload, timeout=12)
        if res.status_code not in (200, 204):
            logger.warning("[AMOCRM SYNC] Patch failed for lead %s: HTTP %s", lead_id, res.status_code)
            return False

        if note:
            note_url = f"https://{_SUBDOMAIN}.amocrm.ru/api/v4/leads/{lead_id}/notes"
            author_prefix = f"[{seller_name}]: " if seller_name else ""
            note_payload = [{"note_type": "common", "params": {"text": f"{author_prefix}{note}"}}]
            await asyncio.to_thread(requests.post, note_url, headers=headers, json=note_payload, timeout=12)

        logger.info("[AMOCRM SYNC] Lead %s updated in amoCRM (status: %s, pipe: %s)", lead_id, status_id, pipeline_id)
        return True
    except Exception as exc:
        logger.error("[AMOCRM SYNC] Error syncing lead %s to amoCRM: %s", lead_id, exc)
        return False


async def sync_lead_save_to_amocrm(lead_data: Dict[str, Any]) -> bool:
    """Jon CRM dagi bitim kartochkasi o'zgarganda amoCRM ga narx va statusni yozadi."""
    lead_id = lead_data.get("id")
    if not lead_id or not _get_access_token():
        return False

    payload: Dict[str, Any] = {}
    if "price" in lead_data:
        try:
            payload["price"] = float(lead_data["price"])
        except (ValueError, TypeError):
            pass
    if "status_id" in lead_data and lead_data["status_id"]:
        payload["status_id"] = int(lead_data["status_id"])
    if "pipeline_id" in lead_data and lead_data["pipeline_id"]:
        payload["pipeline_id"] = int(lead_data["pipeline_id"])
    if "name" in lead_data and lead_data["name"]:
        payload["name"] = str(lead_data["name"]).strip()

    if not payload:
        return True

    url = f"https://{_SUBDOMAIN}.amocrm.ru/api/v4/leads/{lead_id}"
    try:
        res = await asyncio.to_thread(requests.patch, url, headers=_get_headers(), json=payload, timeout=12)
        return res.status_code in (200, 204)
    except Exception as exc:
        logger.error("[AMOCRM SYNC] Error updating lead %s: %s", lead_id, exc)
        return False


async def sync_note_to_amocrm(lead_id: int, text: str, author: str = "Sotuvchi") -> bool:
    """Jon CRM da izoh qo'shilganda amoCRM primetchaniyasiga ham yozadi."""
    if not lead_id or not text or not _get_access_token():
        return False

    url = f"https://{_SUBDOMAIN}.amocrm.ru/api/v4/leads/{lead_id}/notes"
    payload = [{"note_type": "common", "params": {"text": f"[{author}]: {text}"}}]
    try:
        res = await asyncio.to_thread(requests.post, url, headers=_get_headers(), json=payload, timeout=12)
        return res.status_code in (200, 201)
    except Exception as exc:
        logger.error("[AMOCRM SYNC] Error posting note to lead %s: %s", lead_id, exc)
        return False


async def pull_leads_from_amocrm(limit: int = 150, pipeline_id: Optional[int] = None) -> int:
    """amoCRM dan eng so'nggi yangilangan bitimlarni Jon CRM (DialerStore) ga tortib oladi."""
    token = _get_access_token()
    if not token:
        return 0

    pipe_filter = f"&filter[pipeline_id]={pipeline_id}" if pipeline_id else ""
    url = f"https://{_SUBDOMAIN}.amocrm.ru/api/v4/leads?order[updated_at]=desc&limit={limit}{pipe_filter}"

    try:
        res = await asyncio.to_thread(requests.get, url, headers=_get_headers(), timeout=20)
        if res.status_code != 200:
            logger.warning("[AMOCRM PULL] HTTP %s from amoCRM leads list", res.status_code)
            return 0

        data = res.json()
        leads_raw = data.get("_embedded", {}).get("leads", [])
        if not leads_raw:
            return 0

        store = DialerStore()
        pulled_count = 0

        for l in leads_raw:
            lid = l.get("id")
            if not lid:
                continue

            l_pipe = int(l.get("pipeline_id") or 11162698)
            l_status_id = int(l.get("status_id") or 0)
            st_info = resolve_status_info(l_pipe, status_id=l_status_id)

            existing = store.get_lead(lid)
            tags = [t.get("name") for t in (l.get("_embedded", {}).get("tags") or []) if t.get("name")]

            lead_dict: Dict[str, Any] = {
                "id": lid,
                "pipeline_id": l_pipe,
                "name": l.get("name") or (existing.get("name") if existing else f"Bitim #{lid}"),
                "price": float(l.get("price") or 0.0),
                "status_id": l_status_id,
                "status_slug": st_info["slug"],
                "responsible_user_id": int(l.get("responsible_user_id") or 13021974),
                "is_active": 1 if l_status_id not in (142, 143) else 0,
            }
            if tags:
                lead_dict["tags"] = tags
            if existing:
                lead_dict.setdefault("contact_name", existing.get("contact_name", ""))
                lead_dict.setdefault("phone", existing.get("phone", ""))
                lead_dict.setdefault("company_name", existing.get("company_name", ""))

            store.upsert_lead(lead_dict)
            pulled_count += 1

        logger.info("[AMOCRM PULL] Successfully synced %s leads into Jon CRM", pulled_count)
        return pulled_count
    except Exception as exc:
        logger.error("[AMOCRM PULL] Error pulling leads: %s", exc)
        return 0


def apply_amocrm_webhook_lead_event(data: Dict[str, Any]) -> None:
    """amoCRM webhooki kelganda bitim o'zgarishini Jon CRM ga darhol yozadi."""
    try:
        store = DialerStore()
        for key, val in data.items():
            if "leads[status][" in key and "[id]" in key:
                lead_id = int(val)
                st_key = key.replace("[id]", "[status_id]")
                pipe_key = key.replace("[id]", "[pipeline_id]")
                status_id = int(data.get(st_key) or 0)
                pipe_id = int(data.get(pipe_key) or 11162698)

                if lead_id and status_id:
                    st_info = resolve_status_info(pipe_id, status_id=status_id)
                    store.upsert_lead({
                        "id": lead_id,
                        "pipeline_id": pipe_id,
                        "status_id": status_id,
                        "status_slug": st_info["slug"],
                        "is_active": 1 if status_id not in (142, 143) else 0,
                    })
                    logger.info("[AMOCRM WEBHOOK -> JON CRM] Lead %s moved to %s (%s)", lead_id, st_info["slug"], status_id)
    except Exception as exc:
        logger.warning("[AMOCRM WEBHOOK -> JON CRM] Failed to apply: %s", exc)
