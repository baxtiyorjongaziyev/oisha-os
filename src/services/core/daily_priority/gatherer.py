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


async def _default_fetch(pipeline_id: int, status_id: int) -> List[Dict[str, Any]]:
    from src.services.api_server.helpers import _get_amocrm_instance

    amo = _get_amocrm_instance()
    if amo is None:
        return []
    return await amo.get_leads(
        status_id=status_id,
        limit=250,
        **{"filter[statuses][0][pipeline_id]": pipeline_id},
    )


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


async def _collect(stages, fetch: FetchLeads, now_ts: float) -> List[Dict[str, Any]]:
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
            tasks.append(_to_task(lead, stage, now_ts))
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
        pool = await _collect(SALES_STAGES, fetch, now_ts)
        for index, task in enumerate(pool[: MAX_PER_MEMBER * len(sales)]):
            result[sales[index % len(sales)]["key"]].append(task)
    if finance:
        pool = await _collect(FINANCE_STAGES, fetch, now_ts)
        for index, task in enumerate(pool[: MAX_PER_MEMBER * len(finance)]):
            result[finance[index % len(finance)]["key"]].append(task)
    return result
