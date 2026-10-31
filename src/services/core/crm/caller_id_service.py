"""Real-time Caller ID & Inbound Call Pop-up Service for Jon CRM.

Sotuvchining Moizvonki Android ilovasida kiruvchi qo'ng'iroq bo'lgan vaqtda
(call.start hodisasi), aynan o'sha sotuvchi ochgan CRM ekranida
kim telefon qilayotgani (Mijoz ismi, kompaniyasi, bitim bosqichi, byudjeti)
real-vaqt rejimida pop-up (Caller ID) bo'lib chiqadi.
"""
from __future__ import annotations

import asyncio
from datetime import datetime
import json
import logging
import re
import time
from typing import Any, Dict, List, Optional

from src.services.core.crm.dialer_store import DialerStore
from src.services.core.crm.team_roster import find_staff, get_moizvonki_rep_map

logger = logging.getLogger(__name__)

# Moizvonki email -> Sotuvchi profili xaritasi (Single Source of Truth: team_roster)
MOIZVONKI_REP_MAP: Dict[str, Dict[str, Any]] = get_moizvonki_rep_map()

_active_call_events: Dict[str, Dict[str, Any]] = {}
_listeners: List[asyncio.Queue] = []


def resolve_rep(identifier: Optional[str]) -> Dict[str, Any]:
    """Resolve Moizvonki account or seller name/slug into structured rep info."""
    clean = (identifier or "").strip().lower()
    if clean in MOIZVONKI_REP_MAP:
        return MOIZVONKI_REP_MAP[clean]
    member = find_staff(clean)
    if member:
        return {
            "slug": member.slug,
            "name": member.name,
            "rep_id": member.amocrm_user_id,
            "tg": member.tg_username,
            "tg_user_id": member.tg_user_id,
        }
    return {"slug": "unknown", "name": "Noma'lum Moizvonki akkaunti", "rep_id": None}


class CallerIdHub:
    """Manages real-time inbound call dispatching to connected seller UI sessions."""

    def __init__(self, store: Optional[DialerStore] = None) -> None:
        self.store = store or DialerStore()

    def process_incoming_ring(
        self,
        phone: str,
        account: Optional[str] = None,
        call_id: Optional[str] = None,
        source: Optional[str] = "Moizvonki",
    ) -> Dict[str, Any]:
        """Triggered upon `call.start` webhook: looks up caller in CRM and broadcasts."""
        rep = resolve_rep(account)
        lead = self.store.find_lead_by_phone(phone)
        now_ts = time.time()

        event = {
            "type": "ring",
            "call_id": call_id or f"ring_{int(now_ts)}",
            "phone": phone,
            "target_rep_slug": rep["slug"],
            "target_rep_name": rep["name"],
            "target_rep_id": rep["rep_id"],
            "source": source,
            "created_at": datetime.now().strftime("%H:%M:%S"),
            "timestamp": now_ts,
            "lead": {
                "id": lead["id"],
                "name": lead.get("name") or f"Bitim #{lead['id']}",
                "contact_name": lead.get("contact_name") or "Mijoz",
                "company_name": lead.get("company_name") or "",
                "price": lead.get("price") or 0,
                "status_slug": lead.get("status_slug") or "yangi",
                "responsible_name": lead.get("responsible_name") or rep["name"],
            } if lead else None,
        }

        # Cache active ring for rep for polling fallback (TTL 45s)
        _active_call_events[rep["slug"]] = event

        # Notify any open SSE/long-poll connections
        for q in list(_listeners):
            try:
                q.put_nowait(event)
            except Exception:
                pass

        logger.info(
            "[CALLER-ID] Inbound ring: phone=%s rep=%s lead_id=%s",
            phone,
            rep["slug"],
            lead["id"] if lead else "new",
        )
        return event

    def dismiss_ring(self, rep_slug: str, call_id: Optional[str] = None) -> None:
        """Dismiss caller ID card when call finishes or rep answers/declines."""
        cur = _active_call_events.get(rep_slug)
        if cur and (not call_id or cur.get("call_id") == call_id):
            _active_call_events.pop(rep_slug, None)

    def get_active_ring(self, rep_slug: str) -> Optional[Dict[str, Any]]:
        """Fetch active ringing event for seller's screen (auto-expires after 45s)."""
        ev = _active_call_events.get(rep_slug)
        if not ev:
            # Also check 'all' or admin
            ev = _active_call_events.get("all")
        if ev and time.time() - ev.get("timestamp", 0) > 45:
            _active_call_events.pop(rep_slug, None)
            return None
        return ev
