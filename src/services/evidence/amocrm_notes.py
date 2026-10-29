"""Read recent amoCRM lead notes as evidence messages.

Read-only. Unlike the ROP fetcher this reports *whether* the read succeeded,
so a failed amoCRM call shows up as unknown coverage instead of "no promises".
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, List, Optional, Tuple

import requests

from src.services.evidence.payment_promises import MANAGER, SourceMessage

logger = logging.getLogger("EvidenceAmoNotes")

SOURCE = "amocrm_note"
_TEXT_NOTE_TYPES = ("common", "service_message")
_TIMEOUT = 30
_MAX_PAGES = 8


async def fetch_recent_notes(
    amocrm: Any,
    *,
    days: int = 14,
    now: Optional[datetime] = None,
    session: Any = None,
) -> Tuple[List[SourceMessage], str]:
    """Return (messages, status). status is "ok" or a short failure reason."""
    if amocrm is None or not getattr(amocrm, "base_url", None):
        return [], "amocrm sozlanmagan"
    http = session or requests
    now = now or datetime.now(timezone.utc)
    since = int((now - timedelta(days=days)).timestamp())
    url = f"{amocrm.base_url}/api/v4/leads/notes"
    params: Optional[dict] = {"limit": 250, "filter[updated_at][from]": since}
    for i, note_type in enumerate(_TEXT_NOTE_TYPES):
        params[f"filter[note_type][{i}]"] = note_type

    messages: List[SourceMessage] = []
    for page in range(_MAX_PAGES):
        try:
            resp = await asyncio.to_thread(
                http.get, url, headers=amocrm._get_headers(), params=params, timeout=_TIMEOUT
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("[EVIDENCE] notes page %s failed: %s", page, exc)
            return messages, f"amoCRM so'rovi xato: {type(exc).__name__}"
        if resp.status_code == 204:
            break  # amoCRM answers 204 when nothing matches
        if resp.status_code != 200:
            logger.warning("[EVIDENCE] notes page %s -> HTTP %s", page, resp.status_code)
            return messages, f"amoCRM HTTP {resp.status_code}"
        try:
            body = resp.json() or {}
        except ValueError:
            logger.warning("[EVIDENCE] notes page %s: invalid JSON", page)
            return messages, "amoCRM javobi o'qilmadi (JSON xato)"
        if not isinstance(body, dict):
            return messages, "amoCRM javobi kutilmagan formatda"
        for note in (body.get("_embedded") or {}).get("notes") or []:
            msg = _to_message(note)
            if msg:
                messages.append(msg)
        nxt = ((body.get("_links") or {}).get("next") or {}).get("href")
        if not nxt:
            break
        url, params = nxt, None
    else:
        return messages, f"faqat {_MAX_PAGES} sahifa o'qildi"
    return messages, "ok"


def _to_message(note: dict) -> Optional[SourceMessage]:
    text = (note.get("params") or {}).get("text") or ""
    created = note.get("created_at")
    if not text.strip() or not created:
        return None
    author = note.get("created_by")
    return SourceMessage(
        source=SOURCE,
        source_id=str(note.get("id")),
        # Notes are written by managers, so promises here are manager-reported.
        speaker=f"Menejer {author}" if author else "Menejer",
        speaker_role=MANAGER,
        said_at=datetime.fromtimestamp(int(created), tz=timezone.utc),
        text=text,
        lead_id=str(note.get("entity_id")) if note.get("entity_id") else None,
    )
