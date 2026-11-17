"""Teg boʼyicha lidlarni "toʼlovga eng yaqin" tartibda ajratish.

amoCRMʼda maʼlum tegli (masalan "Shahnoza") ochiq lidlarni olib, bosqich
(voronkadagi oʼrni), toʼlov bosqichi, summa va yangilanish vaqtiga qarab
ball qoʼyadi. Faqat oʼqiydi, amoCRMʼga hech narsa yozmaydi.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional

import structlog

from src.services.core.crm.pipelines_catalog import PIPELINES_CATALOG

logger = structlog.get_logger()

CLOSED_STATUS_IDS = {142, 143}
# Mijoz toʼlovni allaqachon qilgan bosqichlar: "toʼlovga yaqin" emas, tugallangan.
PAID_STATUS_IDS = {86306518}
# Aynan toʼlov kutilayotgan bosqichlar.
PAYMENT_STATUS_IDS = {88871066, 86306514}

_STAGE_WEIGHT = 70.0
_PAYMENT_SCORE = 100.0
_PRICE_BONUS = 5.0
_MAX_PAGES = 8
_PAGE_LIMIT = 250


@dataclass(frozen=True)
class RankedLead:
    lead_id: int
    name: str
    score: float
    status_id: int
    stage_title: str
    price: int
    days_since_update: Optional[int]
    reason: str


def _build_stage_index() -> Dict[int, tuple[float, str]]:
    """status_id -> (0..1 voronkadagi nisbiy oʼrin, bosqich nomi)."""
    index: Dict[int, tuple[float, str]] = {}
    for pipeline in PIPELINES_CATALOG:
        active = [s for s in pipeline["statuses"] if s["id"] not in CLOSED_STATUS_IDS]
        denom = max(len(active) - 1, 1)
        for pos, status in enumerate(active):
            index[status["id"]] = (pos / denom, status["title"])
    return index


_STAGE_INDEX = _build_stage_index()


def lead_has_tag(lead: Dict[str, Any], tag: str) -> bool:
    wanted = tag.strip().casefold()
    tags = (lead.get("_embedded") or {}).get("tags") or lead.get("tags") or []
    for t in tags:
        name = t.get("name") if isinstance(t, dict) else str(t)
        if name and name.strip().casefold() == wanted:
            return True
    return False


def score_lead(lead: Dict[str, Any], now: Optional[float] = None) -> Optional[RankedLead]:
    """Bitta lidga ball qoʼyadi. Yopilgan yoki toʼlangan lid uchun None."""
    status_id = int(lead.get("status_id") or 0)
    if status_id in CLOSED_STATUS_IDS or status_id in PAID_STATUS_IDS:
        return None

    now = time.time() if now is None else now
    rel, title = _STAGE_INDEX.get(status_id, (0.0, "Nomaʼlum bosqich"))
    reasons: List[str] = []

    if status_id in PAYMENT_STATUS_IDS:
        score = _PAYMENT_SCORE
        reasons.append("toʼlov bosqichida")
    else:
        score = rel * _STAGE_WEIGHT
        reasons.append(f"bosqich: {title}")

    price = int(lead.get("price") or 0)
    if price > 0:
        score += _PRICE_BONUS
        reasons.append("summa kiritilgan")

    updated_at = lead.get("updated_at")
    days: Optional[int] = None
    if updated_at:
        days = max(int((now - int(updated_at)) // 86400), 0)
        if days <= 3:
            score += 10
            reasons.append("yaqinda yangilangan")
        elif days <= 7:
            score += 5
        elif days > 14:
            score -= 10
            reasons.append(f"{days} kun harakatsiz")

    return RankedLead(
        lead_id=int(lead.get("id") or 0),
        name=str(lead.get("name") or f"Lead {lead.get('id')}"),
        score=round(score, 1),
        status_id=status_id,
        stage_title=title,
        price=price,
        days_since_update=days,
        reason=", ".join(reasons),
    )


def rank_leads_by_payment_proximity(
    leads: Iterable[Dict[str, Any]],
    tag: str,
    limit: int = 10,
    now: Optional[float] = None,
) -> List[RankedLead]:
    ranked = []
    for lead in leads:
        if not lead_has_tag(lead, tag):
            continue
        item = score_lead(lead, now)
        if item:
            ranked.append(item)
    ranked.sort(key=lambda r: (-r.score, r.days_since_update if r.days_since_update is not None else 10**6))
    return ranked[: max(limit, 1)]


async def fetch_tagged_open_leads(amocrm: Any, tag: str) -> List[Dict[str, Any]]:
    """Ochiq lidlarni sahifalab olib, teg boʼyicha lokal filtrlaydi."""
    found: List[Dict[str, Any]] = []
    for page in range(1, _MAX_PAGES + 1):
        batch = await amocrm.get_leads(limit=_PAGE_LIMIT, page=page)
        if not batch:
            break
        found.extend(l for l in batch if lead_has_tag(l, tag))
        if len(batch) < _PAGE_LIMIT:
            break
    return found


def format_ranking(tag: str, ranked: List[RankedLead]) -> str:
    if not ranked:
        return f"«{tag}» tegli ochiq lid topilmadi."
    lines = [f"💰 «{tag}» tegli lidlar — toʼlovga eng yaqinlari:"]
    for i, r in enumerate(ranked, 1):
        price = ", " + f"{r.price:,}".replace(",", " ") + " soʼm" if r.price else ""
        lines.append(f"{i}. {r.name} — {r.stage_title}{price} ({r.reason})")
    return "\n".join(lines)
