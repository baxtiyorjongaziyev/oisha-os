"""Dedup guard for AmoCRM webhook side effects.

AmoCRM often fires several separate webhook POSTs for one logical change
(e.g. lead add + status + responsible_user assignment land as distinct
requests within seconds of each other). Without this guard, each POST
re-runs enrichment/call-analysis/process_new_lead for the same lead_id,
producing duplicate CRM notes and duplicate team notifications.

The dedup key includes the lead's new status_id (falling back to a
"no-status" bucket when the webhook carries no status change), not just
lead_id. Two webhooks for the same lead but different status transitions
(e.g. a plain status update immediately followed by a Won transition)
must each run their own side effects — keying on lead_id alone would let
the second, more important transition get silently swallowed by the
first one's dedup window.

This only gates the duplicate-prone side effects (enrichment, call
analysis, process_new_lead) — callers should run pipeline enforcement
and Won-transition publishing before checking this, so those never get
skipped by the dedup window.
"""
from __future__ import annotations

from typing import Dict, Optional, Tuple

_DEDUP_SECONDS = 30
_NO_STATUS = -1
_recent_lead_events: Dict[Tuple[int, int], float] = {}


def is_duplicate_lead_event(lead_id: int, now: float, status_id: Optional[int] = None) -> bool:
    """Returns True if a note/notification pass already ran for this lead_id +
    status_id combination recently."""
    key = (lead_id, status_id if status_id is not None else _NO_STATUS)
    last_seen = _recent_lead_events.get(key)
    if last_seen is not None and (now - last_seen) < _DEDUP_SECONDS:
        return True
    _recent_lead_events[key] = now
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
