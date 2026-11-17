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
NO_COHORT_SYSTEMS = ("telegram",)


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
    clock: Callable[[], datetime] = get_local_now
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
    """Kohortlar har tizim uchun alohida snapshot bilan solishtiriladi (muvaffaqiyatsiz yozuv qayta urinadi)."""
    out = []
    for a in adapters:
        if a.name not in reads or a.name in NO_COHORT_SYSTEMS:
            continue
        for key, p in canon.items():
            now = ",".join(sorted(p.cohorts))
            if snaps.get(a.name, {}).get(key, {}).get(COHORT_FIELD) != now:
                out.append(Change(a.name, key, "cohorts", now))
    return out


def _summary(changes, adapters, reads) -> dict[str, int]:
    return {
        a.name: len({c.key for c in changes if c.system == a.name})
        for a in adapters if a.name in reads
    }


async def _snapshot(d: Deps, a, key: str, values: dict, p: Person) -> None:
    snap = dict(values)
    if a.name not in NO_COHORT_SYSTEMS:
        snap[COHORT_FIELD] = ",".join(sorted(p.cohorts))
    await d.store.save_snapshot(a.name, key, snap)


async def _apply_one(d: Deps, a, canon, changes, rows, snaps, blocked=frozenset()) -> None:
    mine = [c for c in changes if c.system == a.name]
    res = await a.apply(mine, canon) if mine else {"keys": [], "written": {}}
    written = res.get("written", {})
    for key in res.get("keys", []):
        if key in canon:
            values = written.get(key) or {f: getattr(canon[key], f) for f in a.fields}
            await _snapshot(d, a, key, values, canon[key])
    changed = {c.key for c in mine}
    for key, row in rows.items():
        if key in changed or key not in canon or key in blocked:
            continue  # ochiq konflikt: baza snapshot surilmaydi
        # Özgarishsiz kalit: tizimda turgan qiymat snapshot boʻladi
        prev = snaps.get(a.name, {}).get(key, {})
        values = {f: row.get(f, "") for f in a.fields}
        if any(prev.get(f) != v for f, v in values.items()) or COHORT_FIELD not in prev:
            await _snapshot(d, a, key, values, canon[key])


async def _apply(d: Deps, canon, changes, reads, snaps, errors, blocked=frozenset()) -> bool:
    for a in d.adapters:
        if a.name not in reads:
            continue
        if is_quiet_hours(d.clock()):
            return False
        try:
            await _apply_one(d, a, canon, changes, reads[a.name], snaps, blocked)
        except Exception as exc:
            logger.error("[COMMUNITY_SYNC] %s apply: %s", a.name, exc)
            errors.append(a.name)
    return True


async def _persist(d: Deps, canon, blocked=frozenset()) -> None:
    for key, p in canon.items():
        await d.store.upsert_person(p)
        if key not in blocked:
            await d.store.save_snapshot(CANON, key, p.fields())
    await d.store.clear_resolved()


async def _report_conflicts(d: Deps, conflicts) -> None:
    known = {(c.key, c.field): c.values for c in await d.store.open_conflicts()}
    for c in conflicts:
        if known.get((c.key, c.field)) == c.values:
            continue  # bir xil konflikt qayta yuborilmaydi
        await d.store.add_conflict(c)
        await d.notify(conflict_text(c), buttons=conflict_buttons(c))


async def _build_plan(d: Deps, errors):
    canon = await _canonical(d)
    reads = await _reads(d, canon, errors)
    snaps = await d.store.load_snapshots()
    _apply_resolutions(canon, await d.store.resolved_values(), snaps, reads)
    fields = {a.name: a.fields for a in d.adapters}
    changes, conflicts = plan(canon, snaps, reads, fields)
    changes += _cohort_changes(canon, snaps, d.adapters, reads)
    blocked = {c.key for c in conflicts}
    # Konfliktli kalit hech bir tizimga yozilmaydi: aks holda butun yozuv eski qiymatni bosadi
    changes = [c for c in changes if c.key not in blocked]
    return canon, reads, snaps, changes, conflicts


async def run_once(d: Deps, *, dry_run: Optional[bool] = None, now: Optional[datetime] = None) -> dict:
    if now is not None:
        d.clock = lambda: now
    dry = d.dry_run if dry_run is None else dry_run
    if not d.enabled:
        return {"status": "disabled"}
    if is_quiet_hours(d.clock()):
        return {"status": "quiet_hours"}
    errors: list[str] = []
    canon, reads, snaps, changes, conflicts = await _build_plan(d, errors)
    summary = _summary(changes, d.adapters, reads)
    out = {"plan": summary, "conflicts": len(conflicts), "people": len(canon), "errors": errors}
    if dry:
        await d.notify(f"Community sync (dry-run): {len(canon)} kishi, reja {summary}, konflikt {len(conflicts)}")
        return dict(out, status="dry_run")
    await _report_conflicts(d, conflicts)
    if max(summary.values(), default=0) > d.bulk_threshold and not await is_approved(d.store, d.clock()):
        await d.notify(f"Community sync: katta yozuv {summary}. Tasdiqlaysizmi?", buttons=approval_buttons())
        return dict(out, status="awaiting_approval")
    blocked = frozenset(c.key for c in conflicts)
    if not await _apply(d, canon, changes, reads, snaps, errors, blocked):
        return dict(out, status="quiet_hours")
    await _persist(d, canon, blocked)
    if d.drip and not is_quiet_hours(d.clock()):
        out["telegram_drip"] = await d.drip(d.store, canon, d.tg_daily_limit, d.clock())
    await d.notify(f"Community sync: {len(canon)} kishi, yozildi {summary}, xato {errors or 'yöq'}")
    return dict(out, status="applied")
