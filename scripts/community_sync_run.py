"""Community sync qölda ishga tushirish — faqat Hetznerʼda, ishlayotgan Oisha jarayonidan tashqarida EMAS.

Lokal userbot ochilmaydi: bu skript faqat import/sintaksis tekshiruvi va
`--plan-only` rejimida store holatini köʻrsatadi. Haqiqiy sinxron oisha.service
ichidagi scheduled_job orqali ishlaydi (boot.py ulanishi Coordinator ishi).
"""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.services.core.community_sync.store import SyncStore  # noqa: E402


async def main() -> None:
    store = SyncStore()
    await store.ensure_schema()
    people = await store.load_people()
    conflicts = await store.open_conflicts()
    print(json.dumps({"people": len(people), "open_conflicts": len(conflicts)}))


if __name__ == "__main__":
    asyncio.run(main())
