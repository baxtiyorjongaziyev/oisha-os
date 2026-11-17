"""Kanonik shaxs yozuvi va kontakt nomlash qoidalari."""

import re
from dataclasses import dataclass, field
from typing import Optional

from .cohorts import cohort_from_code, cohort_rank

SYNC_FIELDS = (
    "first_name", "last_name", "phone", "username", "company", "activity", "region",
)
_SUFFIX_RE = re.compile(r"\s*\b(?:TN|3K)\d+ Gr\s*$")


@dataclass
class Person:
    key: str
    tg_id: Optional[int] = None
    username: str = ""
    first_name: str = ""
    last_name: str = ""
    phone: str = ""
    company: str = ""
    activity: str = ""
    region: str = ""
    cohorts: set[str] = field(default_factory=set)
    ext: dict[str, str] = field(default_factory=dict)

    def fields(self) -> dict[str, str]:
        return {f: getattr(self, f) or "" for f in SYNC_FIELDS}


def strip_suffix(name: str) -> str:
    return _SUFFIX_RE.sub("", name or "").strip()


def existing_suffix(name: str) -> str:
    m = _SUFFIX_RE.search(name or "")
    return m.group(0).strip() if m else ""


def primary_suffix(p: Person) -> Optional[str]:
    for code in sorted(p.cohorts, key=cohort_rank):
        suffix = cohort_from_code(code).suffix
        if suffix:
            return suffix
    return None


def name_locked(p: Person, existing: str) -> bool:
    """Boshqa kohort suffiksli nom: bu tizimda ism öqilmaydi va özgartirilmaydi."""
    suf = existing_suffix(existing)
    return bool(suf) and suf != primary_suffix(p)


def display_name(p: Person, existing: str = "") -> str:
    """'Ism Familya <suffix>'. Boshqa kohort suffiksi bor nom özgarmaydi."""
    if name_locked(p, existing):
        return existing
    parts = (strip_suffix(p.first_name), strip_suffix(p.last_name))
    base = " ".join(x for x in parts if x).strip()
    base = base or (p.username and "@" + p.username) or p.phone
    suffix = primary_suffix(p)
    return f"{base} {suffix}" if suffix else base


def labels_for(p: Person) -> list[str]:
    return sorted(cohort_from_code(c).label for c in p.cohorts)
