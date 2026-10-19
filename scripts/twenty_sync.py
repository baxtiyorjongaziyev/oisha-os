"""amoCRM -> Twenty one-way sync (manual / cron entry point).

Usage:
  python scripts/twenty_sync.py --report-only     # counts only, no writes
  python scripts/twenty_sync.py --no-amo-pull     # project existing mirror
  python scripts/twenty_sync.py                   # pull amoCRM, then project

Requires TWENTY_SYNC_ENABLED=1 for any write. Safe to re-run: idempotent and
resumes from per-kind checkpoints.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.services.core.crm.twenty import runner  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report-only", action="store_true")
    parser.add_argument("--no-amo-pull", action="store_true")
    args = parser.parse_args()
    if not args.report_only and not runner.enabled():
        print("TWENTY_SYNC_ENABLED=1 emas; faqat --report-only ruxsat etiladi.")
        return 2
    result = asyncio.run(runner.run_once(
        pull_amo=not args.no_amo_pull and not args.report_only,
        dry_report=args.report_only))
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    state = (result.get("projection") or {}).get("state", "ready")
    return 0 if state == "ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
