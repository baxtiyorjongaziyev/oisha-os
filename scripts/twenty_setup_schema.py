"""Twenty CRM'da sotuv bo'limi maydonlarini yaratish.

    python scripts/twenty_setup_schema.py            # dry-run (default)
    python scripts/twenty_setup_schema.py --apply    # haqiqiy yaratish
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.services.core.crm.twenty_client import TwentyClient
from src.services.core.crm.twenty_schema import ensure_schema


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Maydonlarni haqiqatan yaratish")
    args = parser.parse_args()
    report = await ensure_schema(TwentyClient(), dry_run=not args.apply)
    for obj, field, status in report:
        print(f"{obj:12} {field:20} {status}")


if __name__ == "__main__":
    asyncio.run(main())
