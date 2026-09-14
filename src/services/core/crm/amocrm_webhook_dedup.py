"""Dedup guard for AmoCRM webhook side effects.

AmoCRM often fires several separate webhook POSTs for one logical change
(e.g. lead add + status + responsible_user assignment land as distinct
requests within seconds of each other). Without this guard, each POST
re-runs enrichment/call-analysis/process_new_lead for the same lead_id,
producing duplicate CRM notes and duplicate team notifications.

This only gates the duplicate-prone side effects (enrichment, call
analysis, process_new_lead) — callers should run pipeline enforcement
and Won-transition publishing before checking this, so those never get
skipped by the dedup window.
"""
from __future__ import annotations

from typing import Dict

_DEDUP_SECONDS = 30
_recent_lead_events: Dict[int, float] = {}


def is_duplicate_lead_event(lead_id: int, now: float) -> bool:
    """Returns True if a note/notification pass already ran for lead_id recently."""
    last_seen = _recent_lead_events.get(lead_id)
    if last_seen is not None and (now - last_seen) < _DEDUP_SECONDS:
        return True
    _recent_lead_events[lead_id] = now
    _evict_stale(now)
    return False


def _evict_stale(now: float) -> None:
    """Bound memory: drop stale entries so this dict doesn't grow forever."""
    if len(_recent_lead_events) <= 1000:
        return
    cutoff = now - _DEDUP_SECONDS
    for k, v in list(_recent_lead_events.items()):
        if v < cutoff:
            del _recent_lead_events[k]
