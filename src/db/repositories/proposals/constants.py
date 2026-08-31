"""
Constants and statuses for Proposals repository.
"""
VALID_STATUSES = {
    "proposed",
    "accepted",
    "queued",
    "in_progress",
    "done",
    "failed",
    "rejected",
    "deferred",
}

ALLOWED_TRANSITIONS = {
    "proposed": {"accepted", "rejected", "deferred"},
    "deferred": {"proposed", "accepted", "rejected"},
    "accepted": {"queued", "in_progress", "deferred", "rejected"},
    "queued": {"in_progress", "failed", "deferred"},
    "in_progress": {"done", "failed", "deferred"},
    "failed": {"accepted", "deferred", "rejected"},
    "done": set(),
    "rejected": set(),
}

_LEGACY_AGENT_TABLE_MARKERS = frozenset({"area", "gap", "proposal"})
