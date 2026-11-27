"""Unified 5-system client profile sync (Google, Telegram, amoCRM, Airtable, Second Brain)."""
from __future__ import annotations

from .models import UnifiedClientProfile, is_eligible_client, merge_profiles
from .runner import UnifiedSyncReport, run_unified_client_sync

__all__ = [
    "UnifiedClientProfile",
    "UnifiedSyncReport",
    "is_eligible_client",
    "merge_profiles",
    "run_unified_client_sync",
]
