"""
CLI and background runner to scan Instagram comments on the Brend/Patent video.
Analyzes comments, sends DM to qualified leads, and resumes seamlessly without duplicates.

Usage:
    python scripts/scan_brend_comments.py --dry-run
    python scripts/scan_brend_comments.py --max-dms 15
    python scripts/scan_brend_comments.py --stats
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from dotenv import load_dotenv

load_dotenv(override=True)

from src.db import get_db
from src.services.core.instagram.comment_store import InstagramCommentStore
from src.services.core.instagram.brend_comment_scanner import (
    scan_and_process_brend_comments,
    DEFAULT_BREND_MEDIA_ID,
)


async def _run(args: argparse.Namespace) -> None:
    store = InstagramCommentStore()

    if args.stats:
        stats = store.get_stats(args.media_id)
        cp = store.get_checkpoint(args.media_id)
        print("=== Instagram Comment Store Stats ===")
        print(f"Media ID: {args.media_id}")
        print(f"Total processed/recorded: {stats.get('total_records', 0)}")
        print(f"Breakdown: {stats.get('breakdown', {})}")
        if cp:
            print(f"Last sync: {cp.get('last_synced_at')}")
            print(f"Last comment ID: {cp.get('last_comment_id')}")
            print(f"Total scanned: {cp.get('total_scanned')}")
            print(f"Total DMs: {cp.get('total_dms')}")
        return

    db = get_db()
    print(f"Starting Brend comment analysis for media {args.media_id} (dry_run={args.dry_run})...")
    summary = await scan_and_process_brend_comments(
        media_id=args.media_id,
        access_token=args.access_token or None,
        store=store,
        db=db,
        dry_run=args.dry_run,
        throttle_seconds=args.throttle,
        max_dms=args.max_dms,
    )
    print("=== Scan Results ===")
    for k, v in summary.items():
        print(f"  {k}: {v}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--media-id", type=str, default=DEFAULT_BREND_MEDIA_ID, help="Instagram media ID")
    parser.add_argument("--access-token", type=str, default="", help="Optional Meta Page Access Token override")
    parser.add_argument("--max-dms", type=int, default=20, help="Max DMs to send in this batch")
    parser.add_argument("--throttle", type=float, default=3.5, help="Base throttle delay between actions (seconds)")
    parser.add_argument("--dry-run", action="store_true", help="Analyze and match without sending actual DMs/replies")
    parser.add_argument("--stats", action="store_true", help="Print current deduplication store statistics")
    args = parser.parse_args()
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
