#!/usr/bin/env python3
"""One-shot: obtain a YouTube OAuth *refresh token* for the channel owner.

Run this LOCALLY (it opens a browser). You need an OAuth 2.0 Client of type
"Desktop app" from Google Cloud Console — pass its client id/secret via flags
or env (YOUTUBE_CLIENT_ID / YOUTUBE_CLIENT_SECRET).

Usage:
    python scripts/youtube_oauth_setup.py \
        --client-id XXX.apps.googleusercontent.com \
        --client-secret GOCSPX-xxxx

    # or, with the two vars already in your .env / shell:
    python scripts/youtube_oauth_setup.py

On success it prints the four .env lines to paste on the server:
    YOUTUBE_CLIENT_ID=...
    YOUTUBE_CLIENT_SECRET=...
    YOUTUBE_REFRESH_TOKEN=...
    YOUTUBE_CHANNEL_ID=UC...

Scopes requested: youtube.upload + youtube.force-ssl (read/write comments).
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

try:
    from dotenv import load_dotenv

    load_dotenv(override=False)
except Exception:  # noqa: BLE001
    pass

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.force-ssl",
]


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--client-id", default=os.getenv("YOUTUBE_CLIENT_ID", "").strip())
    p.add_argument("--client-secret", default=os.getenv("YOUTUBE_CLIENT_SECRET", "").strip())
    p.add_argument(
        "--port", type=int, default=8765,
        help="local redirect port (must be in the OAuth client's allowed redirects for a web client; ignored for Desktop clients)",
    )
    p.add_argument(
        "--no-browser", action="store_true",
        help="print the URL instead of opening a browser (console flow)",
    )
    args = p.parse_args()

    if not args.client_id or not args.client_secret:
        print(
            "[ERROR] client id/secret missing — pass --client-id/--client-secret "
            "or set YOUTUBE_CLIENT_ID / YOUTUBE_CLIENT_SECRET",
            file=sys.stderr,
        )
        return 1

    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
    except ImportError as exc:  # noqa: BLE001
        print(f"[ERROR] missing dependency: {exc}\n"
              "pip install google-auth-oauthlib google-api-python-client", file=sys.stderr)
        return 1

    client_config = {
        "installed": {
            "client_id": args.client_id,
            "client_secret": args.client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"],
        }
    }
    flow = InstalledAppFlow.from_client_config(client_config, scopes=SCOPES)

    if args.no_browser:
        creds = flow.run_console()
    else:
        # access_type=offline + prompt=consent guarantees a refresh_token
        creds = flow.run_local_server(
            port=args.port, open_browser=True, prompt="consent", access_type="offline"
        )

    if not creds.refresh_token:
        print("[ERROR] Google did not return a refresh_token. Revoke prior access at "
              "https://myaccount.google.com/permissions and rerun.", file=sys.stderr)
        return 1

    channel_id = ""
    try:
        yt = build("youtube", "v3", credentials=creds, cache_discovery=False)
        resp = yt.channels().list(part="id", mine=True).execute()
        items = resp.get("items", [])
        if items:
            channel_id = items[0]["id"]
    except Exception as exc:  # noqa: BLE001
        print(f"[WARN] could not auto-detect channel id: {exc}", file=sys.stderr)

    print("\n# ---- paste into the server .env ----")
    print(f"YOUTUBE_CLIENT_ID={args.client_id}")
    print(f"YOUTUBE_CLIENT_SECRET={args.client_secret}")
    print(f"YOUTUBE_REFRESH_TOKEN={creds.refresh_token}")
    if channel_id:
        print(f"YOUTUBE_CHANNEL_ID={channel_id}")
    else:
        print("YOUTUBE_CHANNEL_ID=UC...   # <-- fill in manually (channel could not be detected)")
    print("# ------------------------------------")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
