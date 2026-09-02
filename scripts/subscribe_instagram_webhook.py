#!/usr/bin/env python3
"""Subscribe the app to the Facebook Page's webhook fields (comments, messages).

This is the piece that makes new Instagram comments reach Oisha in real time
instead of waiting for the 20s backfill sweep. It calls
    POST /{page-id}/subscribed_apps?subscribed_fields=feed,comments,mentions,messages
with the Page access token, then reads it back to confirm.

Reads META_PAGE_ID + META_PAGE_ACCESS_TOKEN from the .env (auto-located the same
way as refresh_meta_token.py).

Usage:
    python scripts/subscribe_instagram_webhook.py
    python scripts/subscribe_instagram_webhook.py --check     # only read back
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import requests

GRAPH = "https://graph.facebook.com/v19.0"
_DEFAULT_FIELDS = "feed,comments,mentions,messages,message_reactions"

_CANDIDATE_ENV_PATHS = (
    Path("/home/baxti/oisha-os/.env"),
    Path("/home/ubuntu/oisha-os/.env"),
    Path(__file__).resolve().parents[1] / ".env",
)


def _locate_env(explicit: str | None) -> Path:
    import os

    if explicit:
        return Path(explicit).expanduser()
    if os.getenv("OISHA_ENV_FILE"):
        return Path(os.environ["OISHA_ENV_FILE"]).expanduser()
    for candidate in _CANDIDATE_ENV_PATHS:
        if candidate.exists():
            return candidate
    return _CANDIDATE_ENV_PATHS[-1]


def _read_env(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    if not path.exists():
        return data
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            data[k.strip()] = v.strip()
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file")
    parser.add_argument("--fields", default=_DEFAULT_FIELDS, help="Comma-separated webhook fields")
    parser.add_argument("--check", action="store_true", help="Only read the current subscription")
    args = parser.parse_args()

    env = _read_env(_locate_env(args.env_file))
    page_id = env.get("META_PAGE_ID")
    token = env.get("META_PAGE_ACCESS_TOKEN")
    if not page_id or not token:
        print("[ERROR] META_PAGE_ID / META_PAGE_ACCESS_TOKEN missing from .env", file=sys.stderr)
        return 1

    if not args.check:
        print(f"[*] Subscribing app to Page {page_id} fields: {args.fields}")
        resp = requests.post(
            f"{GRAPH}/{page_id}/subscribed_apps",
            params={"subscribed_fields": args.fields, "access_token": token},
            timeout=30,
        )
        if resp.status_code != 200:
            print(f"[ERROR] subscribe failed ({resp.status_code}): {resp.text}", file=sys.stderr)
            return 1
        print(f"[OK] subscribe response: {resp.json()}")

    read = requests.get(
        f"{GRAPH}/{page_id}/subscribed_apps",
        params={"access_token": token},
        timeout=30,
    )
    if read.status_code != 200:
        print(f"[ERROR] read-back failed ({read.status_code}): {read.text}", file=sys.stderr)
        return 1

    apps = read.json().get("data", [])
    if not apps:
        print("[!] No app is subscribed to this Page yet.")
        return 1
    for app in apps:
        print(f"[OK] app '{app.get('name', app.get('id'))}' subscribed to: "
              f"{', '.join(app.get('subscribed_fields', []))}")
    print()
    print("[*] Also confirm in the App Dashboard -> Webhooks -> Instagram that the "
          "'comments' field itself is subscribed at the product level, with the "
          "callback URL https://oisha.jonbranding.uz/api/instagram/webhook and the "
          "verify token from INSTAGRAM_VERIFY_TOKEN.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
