"""Guruh nomi -> kohort kodi, suffiks va Google label."""

import re
from dataclasses import dataclass
from typing import Optional

_TN_RE = re.compile(r"tez\s*natija\D{0,5}(\d+)", re.IGNORECASE)
_3K_RE = re.compile(r"(?:3\s*kunlik|intensiv|\b3k)\D{0,20}?(\d+)", re.IGNORECASE)
SECTOR_PREFIX = "S:"


@dataclass(frozen=True)
class Cohort:
    code: str
    suffix: Optional[str]
    label: str


def cohort_for_group(title: str) -> Optional[Cohort]:
    title = (title or "").strip()
    if not title:
        return None
    m = _TN_RE.search(title)
    if m:
        n = int(m.group(1))
        return Cohort(f"TN{n}", f"TN{n} Gr", f"TEZ NATIJA {n}")
    m = _3K_RE.search(title)
    if m:
        n = int(m.group(1))
        return Cohort(f"3K{n}", f"3K{n} Gr", f"3K{n}")
    return Cohort(SECTOR_PREFIX + title, None, title)


def cohort_from_code(code: str) -> Cohort:
    if code.startswith(SECTOR_PREFIX):
        return Cohort(code, None, code[len(SECTOR_PREFIX):])
    c = cohort_for_group(
        f"TEZ NATIJA {code[2:]}" if code.startswith("TN") else f"3k {code[2:]}"
    )
    return c or Cohort(code, None, code)


def cohort_rank(code: str) -> tuple[int, int, str]:
    """Eng eski kohort birinchi: raqam kichik, tengda TN oldin."""
    if code.startswith(SECTOR_PREFIX):
        return (1, 0, code)
    kind = 0 if code.startswith("TN") else 1
    digits = re.sub(r"\D", "", code[2:]) or "0"
    return (0, int(digits) * 2 + kind, code)
