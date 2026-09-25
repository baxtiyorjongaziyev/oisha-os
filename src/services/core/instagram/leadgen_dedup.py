"""
Persistent deduplication storage for Meta Lead Ads (Facebook / Instagram).
Prevents duplicate routing to AmoCRM and duplicate Telegram notifications,
even across service restarts and crashes.
"""
from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Set

import structlog

logger = structlog.get_logger("LeadgenDedup")

_PROJECT_ROOT = Path(__file__).resolve().parents[4]
_DEDUP_FILE = _PROJECT_ROOT / "data" / "processed_leadgen_ids.json"
_LOCK = threading.RLock()
_CACHE: Optional[Set[str]] = None


def _load_cache() -> Set[str]:
    """Load processed leadgen IDs from persistent JSON file."""
    global _CACHE
    with _LOCK:
        if _CACHE is not None:
            return set(_CACHE)

        _CACHE = set()
        if _DEDUP_FILE.exists():
            try:
                with open(_DEDUP_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        _CACHE = set(str(x) for x in data)
                    elif isinstance(data, dict):
                        _CACHE = set(str(k) for k in data.keys())
                logger.info("[LEADGEN DEDUP] Loaded processed leads from disk", count=len(_CACHE))
            except Exception as e:
                logger.error("[LEADGEN DEDUP] Failed to load dedup file", error=str(e))
        return set(_CACHE)


def is_leadgen_processed(leadgen_id: str) -> bool:
    """Check if a leadgen ID has already been routed/processed."""
    if not leadgen_id:
        return False
    clean_id = str(leadgen_id).strip()
    cache = _load_cache()
    if clean_id in cache:
        return True
    try:
        from src.services.core.instagram.leadgen_delivery import is_delivery_complete
        if is_delivery_complete(clean_id):
            mark_leadgen_processed(clean_id)
            return True
    except Exception:
        pass
    return False


def mark_leadgen_processed(
    leadgen_id: str,
    lead_id: Optional[int] = None,
    form_id: Optional[str] = None,
) -> None:
    """
    Mark leadgen ID as processed and atomically persist to disk.
    """
    global _CACHE
    leadgen_id_clean = str(leadgen_id).strip()
    if not leadgen_id_clean:
        return

    with _LOCK:
        if _CACHE is None:
            _load_cache()
        assert _CACHE is not None
        _CACHE.add(leadgen_id_clean)

        _DEDUP_FILE.parent.mkdir(parents=True, exist_ok=True)
        try:
            temp_file = _DEDUP_FILE.with_suffix(".tmp")
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(sorted(list(_CACHE)), f, indent=2)
            temp_file.replace(_DEDUP_FILE)
            logger.info("[LEADGEN DEDUP] Marked lead as processed", leadgen_id=leadgen_id_clean, amo_lead_id=lead_id)
        except Exception as e:
            logger.error("[LEADGEN DEDUP] Failed to write dedup file", error=str(e))


def seed_processed_ids(ids: Iterable[str]) -> int:
    """Bulk seed multiple leadgen IDs (useful for initial backfill)."""
    global _CACHE
    clean_ids = [str(x).strip() for x in ids if str(x).strip()]
    if not clean_ids:
        return 0

    with _LOCK:
        if _CACHE is None:
            _load_cache()
        assert _CACHE is not None
        initial_len = len(_CACHE)
        _CACHE.update(clean_ids)
        added = len(_CACHE) - initial_len

        _DEDUP_FILE.parent.mkdir(parents=True, exist_ok=True)
        try:
            temp_file = _DEDUP_FILE.with_suffix(".tmp")
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(sorted(list(_CACHE)), f, indent=2)
            temp_file.replace(_DEDUP_FILE)
            logger.info("[LEADGEN DEDUP] Seeded leads into disk store", count=len(_CACHE), newly_added=added)
        except Exception as e:
            logger.error("[LEADGEN DEDUP] Failed to seed dedup file", error=str(e))

        return added


def get_all_processed_ids() -> Set[str]:
    """Return all known processed leadgen IDs."""
    return _load_cache()
