"""amoCRMʼdan "pul keltiradigan" ishlarni yigʻadi va jamoa aʼzolariga taqsimlaydi.

Bosqichlar joriy amoCRM voronkalaridan olingan (2026-11-16):
- Sotuv: "Kelishuv / Yopish", Closer "Shartnoma tayyorlanmoqda".
- Moliya (toʻlov kutilmoqda): Closer "Avans kutilmoqda",
  Farmer "Yakuniy 50% toʻlov kutilmoqda".

Uchala sotuv menejeri bitta amoCRM foydalanuvchisida ishlaydi, shuning uchun
bitimlar ular orasida navbatma-navbat (eng qimmati birinchi) boʻlinadi —
bitta bitim ikki kishiga tushmaydi.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple

from src.services.core.daily_priority.team import ROLE_FINANCE, ROLE_SALES
from src.services.core.daily_priority.ownership import resolve_seller_key

logger = logging.getLogger("DailyPriority")

# (pipeline_id, status_id, bosqich nomi)
SALES_STAGES: List[Tuple[int, int, str]] = [
    (11162698, 88871066, "Kelishuv / Yopish"),
    (11162702, 87609546, "Shartnoma tayyorlanmoqda"),
]
FINANCE_STAGES: List[Tuple[int, int, str]] = [
    (11162702, 87609550, "Avans kutilmoqda"),
    (10123318, 86306514, "Yakuniy 50% toʻlov kutilmoqda"),
]

MAX_PER_MEMBER = 3

FetchLeads = Callable[[int, int], Awaitable[List[Dict[str, Any]]]]


PAGE_SIZE = 250
MAX_PAGES = 20  # 5000 ta bitim — bosqich uchun yetarli chegara


async def _default_fetch(pipeline_id: int, status_id: int) -> List[Dict[str, Any]]:
    """Bosqichdagi barcha bitimlarni sahifama-sahifa oladi (saralashdan oldin)."""
    from src.services.api_server.helpers import _get_amocrm_instance

    amo = _get_amocrm_instance()
    if amo is None:
        return []
    leads: List[Dict[str, Any]] = []
    for page in range(1, MAX_PAGES + 1):
        batch = await amo.get_leads(
            status_id=status_id,
            limit=PAGE_SIZE,
            page=page,
            **{"filter[statuses][0][pipeline_id]": pipeline_id},
        )
        leads.extend(batch or [])
        if len(batch or []) < PAGE_SIZE:
            break
    else:
        logger.warning("[DAILY] Bosqich %s: %s sahifadan koʻp, qolgani olinmadi.", status_id, MAX_PAGES)
    return leads


def _to_task(lead: Dict[str, Any], stage: str, now_ts: float) -> Dict[str, Any]:
    updated = int(lead.get("updated_at") or 0)
    idle_days = int((now_ts - updated) // 86400) if updated else None
    return {
        "lead_id": lead.get("id"),
        "name": (lead.get("name") or f"Bitim #{lead.get('id')}").strip(),
        "price": int(lead.get("price") or 0),
        "stage": stage,
        "idle_days": idle_days,
    }


def _rank(tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    # Avval eng katta summa, keyin eng uzoq eʼtiborsiz qolgani.
    return sorted(tasks, key=lambda t: (-t["price"], -(t["idle_days"] or 0)))


async def _collect(
    stages, fetch: FetchLeads, now_ts: float,
    *, sellers: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    tasks: List[Dict[str, Any]] = []
    seen = set()
    for pipeline_id, status_id, stage in stages:
        try:
            leads = await fetch(pipeline_id, status_id)
        except Exception as exc:
            logger.warning("[DAILY] %s bosqichini olib boʻlmadi: %s", stage, exc)
            continue
        for lead in leads or []:
            if lead.get("id") in seen or int(lead.get("status_id") or status_id) != status_id:
                continue
            seen.add(lead.get("id"))
            task = _to_task(lead, stage, now_ts)
            if sellers is not None:
                task["seller_key"] = resolve_seller_key(lead, sellers)
            tasks.append(task)
    return _rank(tasks)


async def gather_tasks(
    team: List[Dict[str, Any]],
    *,
    fetch: Optional[FetchLeads] = None,
    now_ts: Optional[float] = None,
) -> Dict[str, List[Dict[str, Any]]]:
    """Har bir aʼzo uchun eng muhim (pul keltiradigan) ishlar roʻyxati."""
    fetch = fetch or _default_fetch
    now_ts = now_ts or time.time()
    result: Dict[str, List[Dict[str, Any]]] = {m["key"]: [] for m in team}

    sales = [m for m in team if m.get("role") == ROLE_SALES]
    finance = [m for m in team if m.get("role") == ROLE_FINANCE]

    if sales:
        pool = await _collect(SALES_STAGES, fetch, now_ts, sellers=sales)
        unassigned = 0
        for task in pool:
            owner = task.get("seller_key")
            if owner is None:
                unassigned += 1
                continue
            if len(result[owner]) < MAX_PER_MEMBER:
                result[owner].append(task)
        if unassigned:
            logger.warning("[DAILY] %s ta bitimda Sotuvchi tasdiqlanmadi; shaxsiy vazifa berilmadi.", unassigned)
    if finance:
        pool = await _collect(FINANCE_STAGES, fetch, now_ts)
        for index, task in enumerate(pool[: MAX_PER_MEMBER * len(finance)]):
            result[finance[index % len(finance)]["key"]].append(task)
    return result
