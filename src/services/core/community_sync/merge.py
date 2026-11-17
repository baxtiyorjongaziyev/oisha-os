"""Identity resolution va maydon darajasidagi 3 tomonlama merge (sof funksiyalar)."""

from dataclasses import dataclass
from typing import Optional

from .models import SYNC_FIELDS, Person

CANON = "_canon"  # kollektor yangilagan kanonik qiymat uchun psevdo-tizim


@dataclass(frozen=True)
class Change:
    system: str
    key: str
    field: str
    value: str


@dataclass
class Conflict:
    key: str
    field: str
    values: dict[str, str]


def _norm_user(u: str) -> str:
    return (u or "").lstrip("@").lower()


def resolve(people: list[Person], incoming: Person) -> Optional[Person]:
    """Telegram id -> telefon -> username. Ism böyicha hech qachon."""
    if incoming.tg_id:
        for p in people:
            if p.tg_id == incoming.tg_id:
                return p
    if incoming.phone:
        for p in people:
            if p.phone and p.phone == incoming.phone:
                return p
    if incoming.username:
        for p in people:
            if p.username and _norm_user(p.username) == _norm_user(incoming.username):
                return p
    return None


def absorb(target: Person, incoming: Person) -> None:
    """Bösh maydonlarni töldiradi, kohortlarni birlashtiradi; töliqni almashtirmaydi."""
    for f in SYNC_FIELDS:
        if not getattr(target, f) and getattr(incoming, f):
            setattr(target, f, getattr(incoming, f))
    target.tg_id = target.tg_id or incoming.tg_id
    target.cohorts |= incoming.cohorts
    for k, v in incoming.ext.items():
        target.ext.setdefault(k, v)


def merge_field(
    base: dict[str, str], current: dict[str, str]
) -> tuple[Optional[str], Optional[dict[str, str]]]:
    """(yangi qiymat | None, konflikt qiymatlari | None)."""
    changed = {
        s: v for s, v in current.items() if v and v != base.get(s, "")
    }
    if not changed:
        return None, None
    if len(set(changed.values())) == 1:
        return next(iter(changed.values())), None
    return None, changed


def _field_plan(key, f, person, snapshots, reads):
    canon_val = getattr(person, f) or ""
    canon_snap = snapshots.get(CANON, {}).get(key)
    base = {CANON: canon_snap.get(f, "") if canon_snap is not None else canon_val}
    current = {CANON: canon_val}
    for system, rows in reads.items():
        if key in rows:
            current[system] = rows[key].get(f, "") or ""
            base[system] = snapshots.get(system, {}).get(key, {}).get(f, "")
    return merge_field(base, current)


def plan(
    canonical: dict[str, Person],
    snapshots: dict[str, dict[str, dict[str, str]]],
    reads: dict[str, dict[str, dict[str, str]]],
) -> tuple[list[Change], list[Conflict]]:
    """Kanonikni joyida yangilaydi, tizimlarga yozish rejasini qaytaradi."""
    changes: list[Change] = []
    conflicts: list[Conflict] = []
    for key, person in canonical.items():
        for f in SYNC_FIELDS:
            value, clash = _field_plan(key, f, person, snapshots, reads)
            if clash:
                conflicts.append(Conflict(key, f, clash))
                continue
            if value is not None:
                setattr(person, f, value)
            target = getattr(person, f) or ""
            if not target:
                continue
            for system, rows in reads.items():
                if rows.get(key, {}).get(f, "") != target:
                    changes.append(Change(system, key, f, target))
    return changes, conflicts
