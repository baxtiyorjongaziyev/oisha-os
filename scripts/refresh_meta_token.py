#!/usr/bin/env python3
"""Exchange a short-lived Meta token for a NON-EXPIRING Instagram Page token.

Flow:
    short-lived user token
      -> long-lived user token   (60 days, via fb_exchange_token)
      -> Page access token       (never expires when derived from a
                                  long-lived user token)
    -> written back into the .env file

The .env is located automatically: --env-file, then $OISHA_ENV_FILE, then the
first of these that exists:
    /home/baxti/oisha-os/.env
    /home/ubuntu/oisha-os/.env
    <repo-root>/.env

Usage:
    python scripts/refresh_meta_token.py <SHORT_LIVED_USER_TOKEN>
    python scripts/refresh_meta_token.py            # reuse META_PAGE_ACCESS_TOKEN
    python scripts/refresh_meta_token.py --dry-run <TOKEN>   # print, don't write

Requires META_APP_ID and META_APP_SECRET in the .env (App Settings -> Basic on
developers.facebook.com). META_PAGE_ID is optional; if unset the script lists
every Page the token can manage and picks the one linked to
META_INSTAGRAM_USER_ID, else the first one, and prints what it chose.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import requests

GRAPH = "https://graph.facebook.com/v19.0"

_CANDIDATE_ENV_PATHS = (
    Path("/home/baxti/oisha-os/.env"),
    Path("/home/ubuntu/oisha-os/.env"),
    Path(__file__).resolve().parents[1] / ".env",
)


def _locate_env(explicit: str | None) -> Path:
    import os

    if explicit:
        return Path(explicit).expanduser()
    env_var = os.getenv("OISHA_ENV_FILE")
    if env_var:
        return Path(env_var).expanduser()
    for candidate in _CANDIDATE_ENV_PATHS:
        if candidate.exists():
            return candidate
    # Fall back to repo-root path even if it doesn't exist yet.
    return _CANDIDATE_ENV_PATHS[-1]


def _read_env(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    if not path.exists():
        return data
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            data[key.strip()] = value.strip()
    return data


def _write_env(path: Path, key: str, value: str) -> None:
    src = path.read_text(encoding="utf-8") if path.exists() else ""
    if re.search(rf"^{re.escape(key)}=", src, re.M):
        src = re.sub(rf"^{re.escape(key)}=.*$", f"{key}={value}", src, flags=re.M)
    else:
        src = (src.rstrip("\n") + "\n" if src else "") + f"{key}={value}\n"
    path.write_text(src, encoding="utf-8")


def _die(msg: str) -> "NoReturn":  # type: ignore[name-defined]
    print(f"[ERROR] {msg}", file=sys.stderr)
    raise SystemExit(1)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("token", nargs="?", help="Short-lived Meta USER token (EAA...)")
    parser.add_argument("--env-file", help="Path to the .env file to update")
    parser.add_argument("--dry-run", action="store_true", help="Print the result, do not write .env")
    args = parser.parse_args()

    env_path = _locate_env(args.env_file)
    env = _read_env(env_path)
    print(f"[*] .env: {env_path}")

    app_id = env.get("META_APP_ID")
    app_secret = env.get("META_APP_SECRET")
    if not app_id or not app_secret:
        _die("META_APP_ID / META_APP_SECRET not found in .env "
             "(developers.facebook.com -> App Settings -> Basic)")

    short_token = (args.token or env.get("META_PAGE_ACCESS_TOKEN") or "").strip()
    if not short_token:
        _die("No token given. Pass the short-lived USER token as the first argument.")

    # 1) short-lived user token -> long-lived user token (60 days)
    print("[*] Exchanging for a long-lived user token...")
    resp = requests.get(
        f"{GRAPH}/oauth/access_token",
        params={
            "grant_type": "fb_exchange_token",
            "client_id": app_id,
            "client_secret": app_secret,
            "fb_exchange_token": short_token,
        },
        timeout=30,
    )
    if resp.status_code != 200:
        _die(f"Long-lived exchange failed ({resp.status_code}): {resp.text}")
    long_user_token = resp.json().get("access_token")
    if not long_user_token:
        _die(f"No access_token in exchange response: {resp.text}")

    # 2) long-lived user token -> Page access token (non-expiring)
    print("[*] Fetching manageable Pages...")
    resp = requests.get(
        f"{GRAPH}/me/accounts",
        params={"access_token": long_user_token, "fields": "id,name,access_token,instagram_business_account"},
        timeout=30,
    )
    if resp.status_code != 200:
        _die(f"me/accounts failed ({resp.status_code}): {resp.text}")
    pages = resp.json().get("data", []) or []
    if not pages:
        _die("This user manages no Pages. Connect the Instagram account to a "
             "Facebook Page first, and grant pages_show_list / "
             "instagram_manage_comments to the token.")

    wanted_page_id = env.get("META_PAGE_ID", "").strip()
    wanted_ig_id = env.get("META_INSTAGRAM_USER_ID", "").strip()

    def _match(page: dict) -> bool:
        if wanted_page_id:
            return page.get("id") == wanted_page_id
        if wanted_ig_id:
            iba = page.get("instagram_business_account") or {}
            return iba.get("id") == wanted_ig_id
        return False

    page = next((p for p in pages if _match(p)), None)
    if page is None:
        page = pages[0]
        if wanted_page_id or wanted_ig_id:
            print(f"[!] No Page matched META_PAGE_ID={wanted_page_id or '-'} / "
                  f"META_INSTAGRAM_USER_ID={wanted_ig_id or '-'}. "
                  f"Falling back to the first Page.")
    print(f"[*] Available Pages: {[(p.get('id'), p.get('name')) for p in pages]}")

    page_token = page.get("access_token")
    if not page_token:
        _die(f"Page '{page.get('name')}' returned no access_token — check token scopes.")

    ig_linked = (page.get("instagram_business_account") or {}).get("id")

    # 3) verify the Page token really is non-expiring
    dbg = requests.get(
        f"{GRAPH}/debug_token",
        params={"input_token": page_token, "access_token": f"{app_id}|{app_secret}"},
        timeout=30,
    )
    expires_at = None
    scopes: list[str] = []
    if dbg.status_code == 200:
        dbg_data = dbg.json().get("data", {})
        expires_at = dbg_data.get("expires_at")
        scopes = dbg_data.get("scopes", []) or []

    print()
    print(f"    Page:   {page.get('name')} ({page.get('id')})")
    print(f"    IG:     {ig_linked or '(no instagram_business_account linked!)'}")
    if expires_at == 0 or expires_at is None:
        print("    Expiry: NEVER (non-expiring Page token)")
    else:
        print(f"    Expiry: {expires_at}  <-- still expires, check the flow")
    if scopes:
        print(f"    Scopes: {', '.join(scopes)}")
        for needed in ("instagram_basic", "instagram_manage_comments"):
            if needed not in scopes:
                print(f"    [!] MISSING scope: {needed}")

    if args.dry_run:
        print("\n[dry-run] .env not modified.")
        return 0

    _write_env(env_path, "META_PAGE_ACCESS_TOKEN", page_token)
    _write_env(env_path, "META_PAGE_ID", str(page.get("id")))
    if ig_linked:
        _write_env(env_path, "META_INSTAGRAM_USER_ID", str(ig_linked))
    print(f"\n[OK] Wrote META_PAGE_ACCESS_TOKEN + META_PAGE_ID"
          f"{' + META_INSTAGRAM_USER_ID' if ig_linked else ''} to {env_path}")
    print("[OK] Now restart the service:  sudo systemctl restart oisha-os")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
