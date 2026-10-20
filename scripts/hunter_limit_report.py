"""Hunter kunlik limiti uchun o'lchov: amoCRM "Sotuv" voronkasiga kuniga nechta lid tushadi
va sotuvchilar ularni qanchalik tez "Yangi"dan olib chiqadi. FAQAT O'QISH.

Contabo'da (prod amoCRM tokeni bor joyda) ishga tushiriladi:

    python scripts/hunter_limit_report.py --days 30

Natija: kunlik yangi lidlar (jami / sotuvchi boshiga), median va p90, hali "Yangi"da
qolganlar ulushi. Shu raqamlar `HUNTER_DAILY_LIMIT` ni tanlash uchun dalil bo'ladi.
"""
from __future__ import annotations

import argparse
import asyncio
import statistics
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.services.core.crm.amocrm_pipeline_config import (  # noqa: E402
    SALES_NEW_STATUS_ID,
    SALES_PIPELINE_ID,
)
from src.time_utils import get_local_timezone  # noqa: E402


def _pct(values, q):
    if not values:
        return 0
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(round(q * (len(ordered) - 1))))]


async def collect(amocrm, days: int):
    since = int(time.time()) - days * 86400
    leads, page = [], 1
    while True:
        batch = await amocrm.get_leads(
            limit=250,
            page=page,
            **{
                "filter[pipeline_id][]": SALES_PIPELINE_ID,
                "filter[created_at][from]": since,
            },
        )
        if not batch:
            break
        leads.extend(batch)
        if len(batch) < 250:
            break
        page += 1
    return leads


def summarize(leads, days: int) -> str:
    tz = get_local_timezone()
    per_day = Counter()
    per_day_seller = defaultdict(Counter)
    still_new = 0
    for lead in leads:
        day = datetime.fromtimestamp(int(lead.get("created_at") or 0), tz).date().isoformat()
        per_day[day] += 1
        per_day_seller[day][lead.get("responsible_user_id")] += 1
        if lead.get("status_id") == SALES_NEW_STATUS_ID:
            still_new += 1
    totals = [per_day.get(d, 0) for d in sorted(per_day)]
    seller_loads = [n for counter in per_day_seller.values() for n in counter.values()]
    lines = [
        f"Davr: oxirgi {days} kun, Sotuv voronkasi, jami {len(leads)} lid",
        f"Kunlik lid (jami): median {statistics.median(totals) if totals else 0}, "
        f"p90 {_pct(totals, 0.9)}, maks {max(totals) if totals else 0}",
        f"Kunlik lid (bitta sotuvchiga): median {statistics.median(seller_loads) if seller_loads else 0}, "
        f"p90 {_pct(seller_loads, 0.9)}, maks {max(seller_loads) if seller_loads else 0}",
        f"Hali 'Yangi'da turganlar: {still_new} ({(100 * still_new / len(leads)) if leads else 0:.0f}%)",
        "",
        "Kun bo'yicha:",
    ]
    for day in sorted(per_day):
        sellers = ", ".join(f"{uid}:{n}" for uid, n in per_day_seller[day].most_common())
        lines.append(f"  {day}: {per_day[day]}  ({sellers})")
    if not leads:
        lines.append("  (lid topilmadi yoki amoCRM javob bermadi — tokenni tekshiring)")
    return "\n".join(lines)


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=30)
    args = parser.parse_args()
    from src.settings import settings

    # Lokal mashinada ishga tushirilsa, amoCRM token yangilanishi prod tokenini
    # aylantirib yuborishi mumkin. Faqat prod sozlamalari bor serverda ishlaydi.
    if not (settings.AMOCRM_SUBDOMAIN or "").strip():
        sys.exit("AMOCRM_SUBDOMAIN yo'q: bu skript faqat Contabo serverda ishga tushiriladi.")
    from src.services.core.crm.amocrm.sync import AmoCRMSync

    amocrm = AmoCRMSync()
    if not getattr(amocrm, "access_token", None):
        sys.exit("amoCRM access token yo'q: hisobot olinmadi (0 lid degani emas).")
    leads = await collect(amocrm, args.days)
    if not leads:
        sys.exit("amoCRM lid qaytarmadi: so'rov xatosi yoki voronka bo'sh. Hisobot ishonchsiz.")
    print(summarize(leads, args.days))


if __name__ == "__main__":
    asyncio.run(main())
