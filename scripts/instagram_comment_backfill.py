"""One-shot backfill: find unanswered Instagram comments and reply to them.

Usage:
    python scripts/instagram_comment_backfill.py --dry-run
    python scripts/instagram_comment_backfill.py --media-limit 25 --max-replies 20
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

# Allow running as `python scripts/instagram_comment_backfill.py` from anywhere.
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(override=True)

from src.db import get_db  # noqa: E402
from src.services.core.instagram_agent import backfill_unanswered_comments  # noqa: E402


async def _run(args: argparse.Namespace) -> None:
    db = get_db()
    summary = await backfill_unanswered_comments(
        db,
        media_limit=args.media_limit,
        max_replies=args.max_replies,
        dry_run=args.dry_run,
    )
    print(summary)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--media-limit", type=int, default=25, help="How many recent posts to scan (max 25)")
    parser.add_argument("--max-replies", type=int, default=20, help="Cap on replies sent this run")
    parser.add_argument("--dry-run", action="store_true", help="Log what would be answered, send nothing")
    asyncio.run(_run(parser.parse_args()))


if __name__ == "__main__":
    main()
