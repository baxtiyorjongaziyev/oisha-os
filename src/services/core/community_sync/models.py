"""Kanonik shaxs yozuvi va kontakt nomlash qoidalari."""

import re
from dataclasses import dataclass, field
from typing import Optional

from .cohorts import cohort_from_code, cohort_rank

SYNC_FIELDS = (
    "first_name", "last_name", "phone", "username", "company", "activity", "region",
)
_SUFFIX_RE = re.compile(r"\b(?:TN|3K)\d+ Gr\s*$")


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


def primary_suffix(p: Person) -> Optional[str]:
    for code in sorted(p.cohorts, key=cohort_rank):
        suffix = cohort_from_code(code).suffix
        if suffix:
            return suffix
    return None


def display_name(p: Person, existing: str = "") -> str:
    """'Ism Familya <suffix>'. Boshqa kohort suffiksi bor nom özgarmaydi."""
    if existing and _SUFFIX_RE.search(existing):
        return existing
    base = " ".join(x for x in (p.first_name, p.last_name) if x).strip()
    base = base or (p.username and "@" + p.username) or p.phone
    suffix = primary_suffix(p)
    return f"{base} {suffix}" if suffix else base


def labels_for(p: Person) -> list[str]:
    return sorted(cohort_from_code(c).label for c in p.cohorts)
