"""amoCRM v4 chat-link, exact phone lookup, and duplicate-lead helpers."""
from __future__ import annotations

import asyncio
import re
import time
from typing import Any, Dict, List, Optional

import requests  # type: ignore
import structlog

logger = structlog.get_logger()

_CHANNEL_UNLINKED_TTL_SECONDS = 3600.0


def _digits_tail9(value: Any) -> str:
    digits = re.sub(r"\D+", "", str(value or ""))
    return digits[-9:] if len(digits) >= 9 else ""


def _contact_phone_tails(contact: Dict[str, Any]) -> set[str]:
    tails: set[str] = set()
    for field in contact.get("custom_fields_values") or []:
        if str(field.get("field_code") or "").upper() != "PHONE":
            continue
        for item in field.get("values") or []:
            tail = _digits_tail9(item.get("value"))
            if tail:
                tails.add(tail)
    return tails


class AmoCRMChatsMixin:
    """Async amoCRM v4 helpers for chat-to-contact linking and safe auto-merge."""

    async def _authed_request(
        self,
        request_fn: Any,
        url: str,
        **kwargs: Any,
    ) -> Optional[Any]:
        """Execute an HTTP request off the event loop with one 401 refresh retry."""
        if not getattr(self, "access_token", None):
            await asyncio.to_thread(self._load_token)
        try:
            response = await self._request_with_auth(request_fn, url, **kwargs)
            if response.status_code == 401 and await asyncio.to_thread(self.refresh_token):
                response = await self._request_with_auth(request_fn, url, **kwargs)
            return response
        except Exception as exc:
            logger.error("[AMOCRM CHATS] request failed (%s): %s", url, type(exc).__name__)
            return None

    async def find_contacts_by_phone_async(self, phone: str) -> List[Dict[str, Any]]:
        """Find all amoCRM contacts whose PHONE field matches the last 9 digits."""
        target_tail = _digits_tail9(phone)
        if not target_tail:
            return []

        digits = re.sub(r"\D+", "", str(phone or ""))
        queries = [digits] if digits else []
        if target_tail not in queries:
            queries.append(target_tail)

        url = f"{self.base_url}/api/v4/contacts"
        by_id: Dict[int, Dict[str, Any]] = {}
        for q in queries:
            resp = await self._authed_request(
                requests.get,
                url,
                params={"query": q, "with": "leads", "limit": 50},
                timeout=30,
            )
            if resp is None or resp.status_code != 200:
                continue
            for contact in resp.json().get("_embedded", {}).get("contacts", []) or []:
                cid = contact.get("id")
                if not cid or int(cid) in by_id:
                    continue
                if target_tail in _contact_phone_tails(contact):
                    by_id[int(cid)] = contact
            if by_id:
                break
        return list(by_id.values())

    async def find_contacts_by_query_async(self, query: str) -> List[Dict[str, Any]]:
        """Search contacts by free-text query (e.g. Telegram username) with linked leads."""
        clean = str(query or "").strip()
        if len(clean) < 3:
            return []
        url = f"{self.base_url}/api/v4/contacts"
        resp = await self._authed_request(
            requests.get,
            url,
            params={"query": clean, "with": "leads", "limit": 25},
            timeout=30,
        )
        if resp is None or resp.status_code != 200:
            return []
        return resp.json().get("_embedded", {}).get("contacts", []) or []

    def is_chat_channel_unlinked(self) -> bool:
        """True while /api/v4/contacts/chats is in temporary cooldown after 400 channel-unlinked."""
        if getattr(self, "_chat_channel_unlinked", False):
            until = float(getattr(self, "_chat_channel_unlinked_until", 0.0) or 0.0)
            if until <= 0.0:
                return True
            if time.time() < until:
                return True
            self._chat_channel_unlinked = False
        return False

    def _mark_chat_channel_unlinked(self) -> None:
        self._chat_channel_unlinked = True
        self._chat_channel_unlinked_until = time.time() + _CHANNEL_UNLINKED_TTL_SECONDS

    async def get_talks_async(
        self,
        *,
        contact_id: Optional[int] = None,
        limit: int = 250,
        page: int = 1,
    ) -> List[Dict[str, Any]]:
        """Read amoCRM Talks (GET /api/v4/talks), which exposes lead-level chat provenance."""
        params: Dict[str, Any] = {"limit": min(max(int(limit), 1), 250), "page": max(1, int(page))}
        if contact_id:
            params["filter[contact_id]"] = int(contact_id)
        url = f"{self.base_url}/api/v4/talks"
        resp = await self._authed_request(requests.get, url, params=params, timeout=30)
        if resp is None or resp.status_code != 200:
            return []
        return resp.json().get("_embedded", {}).get("talks", []) or []

    async def link_chat_to_contact(self, contact_id: int, chat_id: str) -> bool:
        """Bind an amoJo chat UUID to an amoCRM contact via POST /api/v4/contacts/chats."""
        cid = int(contact_id or 0)
        chat_uuid = str(chat_id or "").strip()
        if cid <= 0 or not chat_uuid or self.is_chat_channel_unlinked():
            return False
        url = f"{self.base_url}/api/v4/contacts/chats"
        payload = [{"contact_id": cid, "chat_id": chat_uuid}]
        resp = await self._authed_request(requests.post, url, json=payload, timeout=30)
        if resp is not None and resp.status_code in (200, 201):
            logger.info("[AMOCRM CHATS] Linked chat %s -> contact %s", chat_uuid, cid)
            return True
        code = getattr(resp, "status_code", "err")
        body_text = str(getattr(resp, "text", "") or "").lower()
        if code == 400 and "channel must be linked" in body_text:
            self._mark_chat_channel_unlinked()
            logger.info(
                "[AMOCRM CHATS] /contacts/chats unavailable (channel not linked to OAuth client); "
                "using /talks + /leads/{id}/link fallback for %ds",
                int(_CHANNEL_UNLINKED_TTL_SECONDS),
            )
            return False
        logger.warning("[AMOCRM CHATS] link_chat_to_contact failed (%s): contact=%s", code, cid)
        return False

    @staticmethod
    def _talk_to_chat_row(talk: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "contact_id": talk.get("contact_id"),
            "chat_id": talk.get("chat_id"),
            "entity_id": talk.get("entity_id"),
            "entity_type": talk.get("entity_type"),
            "origin": talk.get("origin"),
        }

    async def get_contact_chats(
        self,
        *,
        contact_id: Optional[int] = None,
        chat_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Query chat associations via /contacts/chats with paginated /talks fallback."""
        if bool(contact_id) == bool(chat_id):
            raise ValueError("Specify exactly one of contact_id or chat_id")

        if not self.is_chat_channel_unlinked():
            params: Dict[str, Any] = (
                {"contact_id": int(contact_id)} if contact_id else {"chat_id": str(chat_id).strip()}
            )
            url = f"{self.base_url}/api/v4/contacts/chats"
            resp = await self._authed_request(requests.get, url, params=params, timeout=30)
            if resp is not None and resp.status_code == 200:
                return resp.json().get("_embedded", {}).get("chats", []) or []
            body_text = str(getattr(resp, "text", "") or "").lower()
            if getattr(resp, "status_code", None) == 400 and "channel must be linked" in body_text:
                self._mark_chat_channel_unlinked()

        if contact_id:
            talks = await self.get_talks_async(contact_id=int(contact_id), limit=50)
            return [self._talk_to_chat_row(t) for t in talks if t.get("chat_id")]

        target_chat = str(chat_id or "").strip()
        for page in range(1, 5):
            talks = await self.get_talks_async(limit=250, page=page)
            if not talks:
                break
            matched = [self._talk_to_chat_row(t) for t in talks if str(t.get("chat_id") or "").strip() == target_chat]
            if matched:
                return matched
            if len(talks) < 250:
                break
        return []

    async def verify_contact_linked_to_lead(self, lead_id: int, contact_id: int) -> bool:
        """Read-after-write verification that contact_id is linked on lead_id."""
        url = f"{self.base_url}/api/v4/leads/{int(lead_id)}"
        resp = await self._authed_request(requests.get, url, params={"with": "contacts"}, timeout=30)
        if resp is None or resp.status_code != 200:
            return False
        contacts = (resp.json().get("_embedded") or {}).get("contacts") or []
        return any(int(c.get("id") or 0) == int(contact_id) for c in contacts)

    async def get_contact_call_notes_count(self, contact_id: int) -> int:
        """Count prior inbound/outbound telephony call notes on a contact."""
        notes = await self.get_notes(
            "contacts",
            entity_id=int(contact_id),
            note_types=["call_in", "call_out"],
            limit=25,
        )
        return len(notes)

    async def link_contact_to_lead_async(self, lead_id: int, contact_id: int) -> bool:
        """Attach an additional contact (e.g. Telegram chat contact) to an existing lead."""
        url = f"{self.base_url}/api/v4/leads/{int(lead_id)}/link"
        payload = [{"to_entity_id": int(contact_id), "to_entity_type": "contacts"}]
        resp = await self._authed_request(requests.post, url, json=payload, timeout=30)
        if resp is not None and resp.status_code in (200, 204):
            logger.info("[AMOCRM CHATS] Linked contact %s -> lead %s", contact_id, lead_id)
            return True
        code = getattr(resp, "status_code", "err")
        logger.warning("[AMOCRM CHATS] link_contact_to_lead failed (%s): lead=%s", code, lead_id)
        return False

    async def close_duplicate_lead(
        self,
        lead_id: int,
        *,
        loss_reason_id: Optional[int] = None,
    ) -> bool:
        """Close a merged duplicate lead (status_id=143) without polluting ad-loss stats."""
        url = f"{self.base_url}/api/v4/leads/{int(lead_id)}"
        payload: Dict[str, Any] = {"status_id": 143}
        if loss_reason_id and int(loss_reason_id) > 0:
            payload["loss_reason_id"] = int(loss_reason_id)
        resp = await self._authed_request(requests.patch, url, json=payload, timeout=30)
        if resp is not None and resp.status_code in (200, 204):
            logger.info("[AMOCRM CHATS] Closed duplicate lead %s", lead_id)
            return True
        code = getattr(resp, "status_code", "err")
        logger.warning("[AMOCRM CHATS] close_duplicate_lead failed (%s): lead=%s", code, lead_id)
        return False

    async def reassign_task_to_lead(self, task_id: int, target_lead_id: int) -> bool:
        """Move an existing open task to target_lead_id via PATCH (preserves ID & task_type_id)."""
        tid = int(task_id or 0)
        lid = int(target_lead_id or 0)
        if tid <= 0 or lid <= 0:
            return False
        url = f"{self.base_url}/api/v4/tasks/{tid}"
        payload = {"entity_id": lid, "entity_type": "leads"}
        resp = await self._authed_request(requests.patch, url, json=payload, timeout=30)
        if resp is not None and resp.status_code in (200, 204):
            logger.info("[AMOCRM CHATS] Reassigned task %s -> lead %s", tid, lid)
            return True
        code = getattr(resp, "status_code", "err")
        logger.warning("[AMOCRM CHATS] reassign_task_to_lead failed (%s): task=%s", code, tid)
        return False

    async def add_lead_note_async(self, lead_id: int, text: str) -> bool:
        """Async wrapper around add_lead_note so callers stay non-blocking."""
        result = await asyncio.to_thread(self.add_lead_note, int(lead_id), text)
        return bool(result)

    async def add_phone_to_contact_async(self, contact_id: int, phone: str) -> bool:
        """Safely append a phone number to an amoCRM contact without overwriting existing ones."""
        cid = int(contact_id or 0)
        target_tail = _digits_tail9(phone)
        if cid <= 0 or not target_tail:
            return False

        digits = re.sub(r"\D+", "", str(phone or ""))
        formatted = f"+{digits}" if digits and not str(phone).strip().startswith("+") else str(phone).strip()

        existing_values: List[Dict[str, Any]] = []
        details = await self.get_contact_details_async(cid, cache_ttl_seconds=0) if hasattr(self, "get_contact_details_async") else None
        if details:
            if target_tail in _contact_phone_tails(details):
                return True
            for field in details.get("custom_fields_values") or []:
                if str(field.get("field_code") or "").upper() != "PHONE":
                    continue
                for item in field.get("values") or []:
                    val = str(item.get("value") or "").strip()
                    if val:
                        entry: Dict[str, Any] = {"value": val}
                        if item.get("enum_code"):
                            entry["enum_code"] = item["enum_code"]
                        existing_values.append(entry)

        existing_values.append({"value": formatted, "enum_code": "MOB"})
        url = f"{self.base_url}/api/v4/contacts/{cid}"
        payload = {
            "custom_fields_values": [
                {"field_code": "PHONE", "values": existing_values}
            ]
        }
        resp = await self._authed_request(requests.patch, url, json=payload, timeout=30)
        if resp is not None and resp.status_code in (200, 204):
            cache = getattr(self, "_contact_details_cache", None)
            if isinstance(cache, dict):
                cache.pop(cid, None)
            logger.info("[AMOCRM CHATS] Added phone to contact %s", cid)
            return True
        code = getattr(resp, "status_code", "err")
        logger.warning("[AMOCRM CHATS] add_phone_to_contact failed (%s): contact=%s", code, cid)
        return False
