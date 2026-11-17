"""Kunlik oqim: yigʻish -> merge -> reja -> (dry-run | tasdiq) -> yozish -> snapshot."""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Awaitable, Callable, Optional

from src.time_utils import get_local_now, is_quiet_hours

from .approval import approval_buttons, conflict_buttons, conflict_text, is_approved
from .merge import CANON, Change, absorb, plan, resolve
from .models import SYNC_FIELDS, Person

logger = logging.getLogger(__name__)
COHORT_FIELD = "_cohorts"


@dataclass
class Deps:
    store: Any
    collect: Callable[[], Awaitable[list[Person]]]
    adapters: list
    notify: Callable[..., Awaitable[Any]]
    drip: Optional[Callable[..., Awaitable[dict]]] = None
    enabled: bool = False
    dry_run: bool = True
    bulk_threshold: int = 20
    tg_daily_limit: int = 120
    folder_id: int = 13
    extra: dict = field(default_factory=dict)


async def _canonical(d: Deps) -> dict[str, Person]:
    canon = await d.store.load_people()
    pool = list(canon.values())
    for inc in await d.collect():
        hit = resolve(pool, inc)
        if hit:
            absorb(hit, inc)
        else:
            pool.append(inc)
            canon[inc.key] = inc
    return canon


def _apply_resolutions(canon, resolved, snaps, reads) -> None:
    """Owner tanlagan qiymat kanonga yoziladi; tizimlardagi eski farq özgarish deb sanalmaydi."""
    for key, fields in resolved.items():
        if key not in canon:
            continue
        for f, v in fields.items():
            if f not in SYNC_FIELDS:
                continue
            setattr(canon[key], f, v)
            for system, rows in reads.items():
                if key in rows:
                    snaps.setdefault(system, {}).setdefault(key, {})[f] = rows[key].get(f, "")


async def _reads(d: Deps, canon, errors: list[str]) -> dict:
    reads = {}
    for a in d.adapters:
        try:
            reads[a.name] = await a.read_all(canon)
        except Exception as exc:
            logger.error("[COMMUNITY_SYNC] %s read: %s", a.name, exc)
            errors.append(a.name)
    return reads


def _cohort_changes(canon, snaps, adapters, reads) -> list[Change]:
    out = []
    for key, p in canon.items():
        now = ",".join(sorted(p.cohorts))
        before = snaps.get(CANON, {}).get(key, {}).get(COHORT_FIELD)
        if before is not None and before == now:
            continue
        for a in adapters:
            if a.name in reads and a.name != "telegram":
                out.append(Change(a.name, key, "cohorts", now))
    return out


def _summary(changes, adapters, reads) -> dict[str, int]:
    return {
        a.name: len({c.key for c in changes if c.system == a.name})
        for a in adapters if a.name in reads
    }


async def _apply(d: Deps, canon, changes, reads, errors) -> None:
    for a in d.adapters:
        if a.name not in reads:
            continue
        mine = [c for c in changes if c.system == a.name]
        try:
            res = await a.apply(mine, canon) if mine else {"keys": []}
        except Exception as exc:
            logger.error("[COMMUNITY_SYNC] %s apply: %s", a.name, exc)
            errors.append(a.name)
            continue
        changed = {c.key for c in mine}
        for key in set(res.get("keys", [])) | (set(reads[a.name]) - changed):
            p = canon.get(key)
            if p:
                await d.store.save_snapshot(a.name, key, {f: getattr(p, f) for f in a.fields})


async def _persist(d: Deps, canon) -> None:
    for key, p in canon.items():
        await d.store.upsert_person(p)
        snap = dict(p.fields(), **{COHORT_FIELD: ",".join(sorted(p.cohorts))})
        await d.store.save_snapshot(CANON, key, snap)
    await d.store.clear_resolved()


async def _report_conflicts(d: Deps, conflicts) -> None:
    for c in conflicts:
        await d.store.add_conflict(c)
        await d.notify(conflict_text(c), buttons=conflict_buttons(c))


async def run_once(d: Deps, *, dry_run: Optional[bool] = None, now: Optional[datetime] = None) -> dict:
    now = now or get_local_now()
    dry = d.dry_run if dry_run is None else dry_run
    if not d.enabled:
        return {"status": "disabled"}
    if is_quiet_hours(now):
        return {"status": "quiet_hours"}
    errors: list[str] = []
    canon = await _canonical(d)
    reads = await _reads(d, canon, errors)
    snaps = await d.store.load_snapshots()
    _apply_resolutions(canon, await d.store.resolved_values(), snaps, reads)
    fields = {a.name: a.fields for a in d.adapters}
    changes, conflicts = plan(canon, snaps, reads, fields)
    changes += _cohort_changes(canon, snaps, d.adapters, reads)
    summary = _summary(changes, d.adapters, reads)
    out = {"plan": summary, "conflicts": len(conflicts), "people": len(canon), "errors": errors}
    if dry:
        await d.notify(f"Community sync (dry-run): {len(canon)} kishi, reja {summary}, konflikt {len(conflicts)}")
        return dict(out, status="dry_run")
    await _report_conflicts(d, conflicts)
    if max(summary.values(), default=0) > d.bulk_threshold and not await is_approved(d.store, now):
        await d.notify(f"Community sync: katta yozuv {summary}. Tasdiqlaysizmi?", buttons=approval_buttons())
        return dict(out, status="awaiting_approval")
    await _apply(d, canon, changes, reads, errors)
    await _persist(d, canon)
    if d.drip:
        out["telegram_drip"] = await d.drip(d.store, canon, d.tg_daily_limit, now)
    await d.notify(f"Community sync: {len(canon)} kishi, yozildi {summary}, xato {errors or 'yöq'}")
    return dict(out, status="applied")
