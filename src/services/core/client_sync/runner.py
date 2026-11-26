"""Orchestrator for 5-system unified client profile sync."""
from __future__ import annotations

import logging
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional

from .models import UnifiedClientProfile, is_eligible_client, merge_profiles

logger = logging.getLogger(__name__)


@dataclass
class UnifiedSyncReport:
    total_input: int = 0
    eligible_clients: int = 0
    skipped_ineligible: int = 0
    dry_run: bool = True
    per_system: Dict[str, Dict[str, int]] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)


async def run_unified_client_sync(
    raw_profiles: Iterable[UnifiedClientProfile],
    *,
    sync_adapters: Optional[List[Any]] = None,
    async_adapters: Optional[List[Any]] = None,
    dry_run: bool = True,
    limit: Optional[int] = None,
) -> UnifiedSyncReport:
    """Group profiles by canonical +998 phone, merge, filter eligible, and sync all 5 systems."""
    report = UnifiedSyncReport(dry_run=dry_run)
    grouped: Dict[str, List[UnifiedClientProfile]] = defaultdict(list)

    for prof in raw_profiles:
        report.total_input += 1
        if not prof.canonical_key:
            report.skipped_ineligible += 1
            continue
        grouped[prof.canonical_key].append(prof)

    canonical: List[UnifiedClientProfile] = []
    for key in sorted(grouped):
        merged = merge_profiles(grouped[key])
        if not is_eligible_client(merged):
            report.skipped_ineligible += 1
            continue
        canonical.append(merged)

    if limit is not None and limit > 0:
        canonical = canonical[:limit]
    report.eligible_clients = len(canonical)

    for adapter in sync_adapters or []:
        counts: Counter = Counter()
        for prof in canonical:
            try:
                status = adapter.sync_profile(prof, dry_run=dry_run)
                counts[status] += 1
            except Exception as exc:
                counts["failed"] += 1
                report.errors.append(f"{adapter.name}:{prof.phone}:{type(exc).__name__}")
                logger.warning("[CLIENT_SYNC] %s failed for %s: %s", adapter.name, prof.phone, exc)
        report.per_system[adapter.name] = dict(counts)

    for adapter in async_adapters or []:
        counts = Counter()
        for prof in canonical:
            try:
                status = await adapter.sync_profile_async(prof, dry_run=dry_run)
                counts[status] += 1
            except Exception as exc:
                counts["failed"] += 1
                report.errors.append(f"{adapter.name}:{prof.phone}:{type(exc).__name__}")
                logger.warning("[CLIENT_SYNC] %s failed for %s: %s", adapter.name, prof.phone, exc)
        report.per_system[adapter.name] = dict(counts)

    return report
