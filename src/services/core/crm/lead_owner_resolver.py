"""Lid egasini aniqlash — "bu kimning lidi?" savoliga dalil bilan javob.

Sotuvchilar bitta amoCRM userʼda ishlagani uchun "Ответственный" maydoni egani
koʼrsatmaydi. Shuning uchun ega quyidagi dalillardan aniqlanadi:

1. Teg (``menejer:Rayxona`` yoki shunchaki ``Shahnoza``) — rasmiy daʼvo.
2. Moizvonki qoʼngʼiroqlari (``call_analyses``) — kim birinchi boʼlib haqiqiy
   suhbat qilgan (>= ``REAL_CALL_SECONDS``).

Qoida: teg bor boʼlsa — ega teg egasi. Teg yoʼq boʼlsa — birinchi haqiqiy
qoʼngʼiroq qilgan sotuvchi. Teg va birinchi qoʼngʼiroq turli odam boʼlsa yoki
bir nechta sotuvchi teg qoʼygan boʼlsa — "nizo" deb belgilanadi, rahbar hal qiladi.
"""
from __future__ import annotations

import html
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

from src.schedulers.unowned_lead_alert import MANAGER_TAG_PREFIXES

REAL_CALL_SECONDS = 20

# Turli yozilishlar -> kanonik ism.
NAME_ALIASES: Dict[str, str] = {
    "shahnoza": "Shahnoza",
    "rayxona": "Rayxona",
    "rayxon": "Rayxona",
    "rayhona": "Rayxona",
    "mumtozmaxal": "Mumtozmaxal",
    "mumtoz": "Mumtozmaxal",
    "baxtiyorjon": "Baxtiyorjon",
}


def canonical_name(raw: str) -> str:
    """Return a canonical seller name ("rayxon abdullayeva" -> "Rayxona")."""
    text = str(raw or "").strip()
    if not text:
        return ""
    first = re.split(r"[\s_\-]+", text.lower())[0]
    return NAME_ALIASES.get(first, text.split()[0].capitalize())


def _tag_names(lead: Dict[str, Any]) -> List[str]:
    tags = (lead.get("_embedded") or {}).get("tags") or []
    return [str(t.get("name") or "") for t in tags if isinstance(t, dict)]


def owners_from_tags(tag_names: Iterable[str]) -> List[str]:
    """Extract seller names claimed via tags, in tag order, de-duplicated."""
    found: List[str] = []
    for tag in tag_names:
        t = tag.strip()
        low = t.lower()
        name = ""
        for prefix in MANAGER_TAG_PREFIXES:
            if low.startswith(prefix):
                name = canonical_name(t[len(prefix):])
                break
        else:
            first = re.split(r"[\s_\-]+", low)[0] if low else ""
            if first in NAME_ALIASES and len(low.split()) <= 2:
                name = NAME_ALIASES[first]
        if name and name not in found:
            found.append(name)
    return found


@dataclass
class OwnerVerdict:
    lead_id: int
    lead_name: str
    owner: Optional[str]
    basis: str  # "teg" | "birinchi qoʼngʼiroq" | "aniqlanmadi"
    disputed: bool
    tag_owners: List[str] = field(default_factory=list)
    first_caller: Optional[str] = None
    first_call_at: Optional[str] = None
    call_counts: Dict[str, int] = field(default_factory=dict)
    created_at: Optional[str] = None


def _fmt_ts(value: Any) -> Optional[str]:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return str(value)[:16].replace("T", " ")


def resolve_owner(lead: Dict[str, Any], calls: Iterable[Dict[str, Any]]) -> OwnerVerdict:
    """Decide who owns ``lead`` from its tags and call history (calls oldest first)."""
    tag_owners = owners_from_tags(_tag_names(lead))

    counts: Dict[str, int] = {}
    first_caller: Optional[str] = None
    first_call_at: Optional[str] = None
    for call in calls:
        name = canonical_name(call.get("manager_name") or "")
        if not name or name.lower() == "sotuvchi":
            continue
        if int(call.get("duration_seconds") or 0) < REAL_CALL_SECONDS:
            continue
        counts[name] = counts.get(name, 0) + 1
        if first_caller is None:
            first_caller, first_call_at = name, _fmt_ts(call.get("created_at"))

    if tag_owners:
        owner, basis = tag_owners[0], "teg"
        disputed = len(tag_owners) > 1 or (first_caller is not None and first_caller != owner)
    elif first_caller:
        owner, basis = first_caller, "birinchi qoʼngʼiroq"
        disputed = False
    else:
        owner, basis, disputed = None, "aniqlanmadi", False

    return OwnerVerdict(
        lead_id=int(lead.get("id") or 0),
        lead_name=str(lead.get("name") or ""),
        owner=owner,
        basis=basis,
        disputed=disputed,
        tag_owners=tag_owners,
        first_caller=first_caller,
        first_call_at=first_call_at,
        call_counts=counts,
        created_at=_fmt_ts(lead.get("created_at")),
    )


def format_verdict(v: OwnerVerdict, subdomain: str = "") -> str:
    link = f"https://{subdomain}.amocrm.ru/leads/detail/{v.lead_id}" if subdomain else f"#{v.lead_id}"
    e = html.escape
    lines = [f"🔎 <b>Lid:</b> {e(v.lead_name or '—')} ({e(link)})"]
    if v.owner:
        lines.append(f"👤 <b>Egasi:</b> {e(v.owner)} — asos: {v.basis}")
    else:
        lines.append("👤 <b>Egasi:</b> aniqlanmadi (teg ham, haqiqiy qoʼngʼiroq ham yoʼq)")
    if v.tag_owners:
        lines.append(f"🏷 Teglar: {e(', '.join(v.tag_owners))}")
    if v.first_caller:
        lines.append(f"📞 Birinchi haqiqiy qoʼngʼiroq: {v.first_caller} ({v.first_call_at or '—'})")
    if v.call_counts:
        stats = ", ".join(f"{k}: {n}" for k, n in sorted(v.call_counts.items(), key=lambda kv: -kv[1]))
        lines.append(f"📊 Qoʼngʼiroqlar (≥{REAL_CALL_SECONDS}s): {stats}")
    if v.created_at:
        lines.append(f"🕒 Lid yaratilgan: {v.created_at}")
    if v.disputed:
        lines.append("⚠️ <b>Nizo:</b> dalillar turli sotuvchini koʼrsatyapti — rahbar hal qilsin.")
    elif not v.owner:
        lines.append("💡 Egasi oʼziga <code>menejer:Ism</code> teg qoʼysin.")
    return "\n".join(lines)


_LEAD_URL_RE = re.compile(r"leads/detail/(\d+)")


async def find_leads(amocrm, query: str, limit: int = 3) -> List[Dict[str, Any]]:
    """Resolve a lead id, amoCRM link, phone or name into lead dicts (with tags)."""
    q = (query or "").strip()
    m = _LEAD_URL_RE.search(q)
    lead_id = m.group(1) if m else (q if q.isdigit() and len(q) <= 10 else None)
    if lead_id:
        lead = await amocrm.get_lead(int(lead_id))
        return [lead] if lead else []
    return await amocrm.search_leads(q, limit=limit)


async def who_owns(amocrm, db, query: str, subdomain: str = "") -> str:
    """Full answer text for "kimning lidi?" queries."""
    leads = await find_leads(amocrm, query)
    if not leads:
        return f"❌ <code>{html.escape(query)}</code> boʼyicha lid topilmadi."
    blocks = []
    for lead in leads:
        repo = getattr(db, "intelligence", None)
        calls = await repo.get_lead_calls(int(lead.get("id") or 0)) if repo else []
        blocks.append(format_verdict(resolve_owner(lead, calls), subdomain))
    return "\n\n".join(blocks)
