"""Read-only CRM context: Call Intelligence analyses + AmoCRM-synced notes.

Source: ``data/crm_dialer.db`` ``dialer_leads`` (filled by the AmoCRM sync and
``CallIntelService``). Matching by phone digits or client-name tokens. Never writes.
"""
from __future__ import annotations

import json
import logging
import os
import re
import sqlite3
from typing import Any, Dict, List, Optional

logger = logging.getLogger("SalesCopilot")

DB_PATH = "data/crm_dialer.db"
_STOP = {"jon", "branding", "mchj", "ooo", "llc", "brend", "brand"}


def _tokens(text: str) -> set[str]:
    return {w for w in re.findall(r"[\wʻʼ']+", (text or "").lower()) if len(w) >= 4 and w not in _STOP}


def _digits(text: str) -> str:
    return "".join(ch for ch in str(text or "") if ch.isdigit())[-9:]


def _notes(row: Dict[str, Any]) -> List[Dict[str, Any]]:
    raw = row.get("notes_json") or "[]"
    try:
        data = json.loads(raw) if isinstance(raw, str) else list(raw)
    except (TypeError, ValueError):
        return []
    return [n for n in data if isinstance(n, dict)]


def summarize(row: Dict[str, Any], max_notes: int = 3) -> Dict[str, Any]:
    notes = _notes(row)
    intel = [n for n in notes if n.get("note_type") == "call_intel"]
    other = [n for n in notes if n.get("note_type") != "call_intel"]
    last_intel = intel[-1].get("ai_analysis") if intel else None
    return {
        "lead_id": row.get("id"),
        "lead": row.get("name") or "",
        "price": row.get("price"),
        "call_summary": (last_intel or {}).get("summary", "") if isinstance(last_intel, dict) else "",
        "notes": [str(n.get("text") or "")[:200] for n in other[-max_notes:]],
    }


def find_context(client_name: str, phone: str = "", db_path: str = DB_PATH) -> Optional[Dict[str, Any]]:
    """Best lead for a client; ambiguous name matches (>1 lead) return ``None``."""
    if not os.path.exists(db_path):
        return None
    want_phone = _digits(phone)
    want_tokens = _tokens(client_name)
    if not want_phone and not want_tokens:
        return None
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=5.0)
        conn.row_factory = sqlite3.Row
        try:
            rows = [dict(r) for r in conn.execute("SELECT * FROM dialer_leads")]
        finally:
            conn.close()
    except sqlite3.Error as exc:
        logger.debug("[SALES_COPILOT] context db unavailable: %s", exc)
        return None
    if want_phone:
        for r in rows:
            if want_phone and want_phone == _digits(r.get("phone") or r.get("contact_phone") or ""):
                return summarize(r)
    hits = [r for r in rows if want_tokens & _tokens(f"{r.get('contact_name') or ''} {r.get('name') or ''}")]
    # Common first names (e.g. "Muhammad") hit many leads: only a unique match counts.
    return summarize(hits[0]) if len(hits) == 1 else None
