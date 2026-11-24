"""CLI tool to audit or apply Telegram <-> Phone auto-merge on existing amoCRM deals.

Usage:
    python -m src.services.core.crm.tg_amo_bridge.automerge_cli --limit 150
    python -m src.services.core.crm.tg_amo_bridge.automerge_cli --limit 150 --apply
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from dataclasses import asdict
from typing import Optional

from . import config
from .automerge import TelegramDealAutoMerger
from .reconciler import scan_and_merge_existing
from .store import MessageStore

logger = logging.getLogger("TgAmoBridge.cli")


def _build_crm():
    from src.services.core.crm.amocrm_sync import AmoCRMSync

    return AmoCRMSync()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="amoCRM Telegram <-> Telefon sdelkalarni tahlil qilish va birlashtirish"
    )
    parser.add_argument("--limit", type=int, default=150, help="Tekshiriladigan faol sdelkalar soni")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="Faqat tahlil va hisobot (CRM oʻzgartirilmaydi; standart rejim)",
    )
    mode.add_argument(
        "--apply",
        action="store_true",
        help="Haqiqiy birlashtirishni bajarish (default = dry-run)",
    )
    return parser


async def _run(args: argparse.Namespace) -> int:
    crm = _build_crm()
    amojo = config.build_amojo_client()
    store = MessageStore()
    merger = TelegramDealAutoMerger(
        crm=crm,
        amojo=amojo,
        store=store,
        dry_run=not args.apply,
        loss_reason_id=config.automerge_loss_reason_id(),
    )
    report = await scan_and_merge_existing(merger, limit=args.limit)
    print(json.dumps(asdict(report), ensure_ascii=False, indent=2))
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s :: %(message)s")
    args = build_parser().parse_args(argv)
    try:
        return asyncio.run(_run(args))
    except KeyboardInterrupt:
        return 130
    except Exception as exc:
        logger.exception("[TG-MERGE CLI] Xatolik")
        print(f"XATO: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
