#!/usr/bin/env python3
"""One-shot: upload a vertical video to YouTube as a Short.

Usage:
    python scripts/youtube_upload_short.py path/to/video.mp4 "Sarlavha" \
        --desc "Tavsif matni" --tags branding,logo,naming --privacy public

Requires YOUTUBE_CLIENT_ID / YOUTUBE_CLIENT_SECRET / YOUTUBE_REFRESH_TOKEN /
YOUTUBE_CHANNEL_ID in the .env (see src/services/core/youtube_agent.py).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(override=True)

from src.services.core.youtube_agent import YouTubeClient  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("video")
    p.add_argument("title")
    p.add_argument("--desc", default="")
    p.add_argument("--tags", default="branding,naming,logo,dizayn")
    p.add_argument("--privacy", default="public", choices=["public", "unlisted", "private"])
    args = p.parse_args()

    client = YouTubeClient()
    if not client.configured:
        print("[ERROR] YouTube not configured — set YOUTUBE_CLIENT_ID / "
              "YOUTUBE_CLIENT_SECRET / YOUTUBE_REFRESH_TOKEN / YOUTUBE_CHANNEL_ID in .env",
              file=sys.stderr)
        return 1

    res = client.upload_short(
        video_path=args.video,
        title=args.title,
        description=args.desc,
        tags=[t.strip() for t in args.tags.split(",") if t.strip()],
        privacy=args.privacy,
    )
    print(res)
    return 0 if res.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
