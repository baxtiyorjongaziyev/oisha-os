"""Bir martalik kampaniya: so'nggi N kunda faqat "+" yozgan odamlarni qamrab olish.

Meta qoidasi: kommentga Private Reply (DM) faqat komment yozilgandan keyin
7 kun ichida yuboriladi. Shuning uchun:
  * <= 7 kun   -> DM (PLUS_COMMENT_DM_TEMPLATE) + ochiq "DM'dan yozdik" javobi
  * 7..N kun   -> faqat ochiq javob: Direct'ga yozishga taklif

Manbalar: profil postlari + reklama postlari (dark post ham). Reklamalar uchun
META_AD_ACCOUNT_ID va token'da ads_read ruxsati kerak.

Ishlatish (Oracle VM, .env bilan):
    python -m scripts.instagram_plus_campaign            # dry-run, hech narsa yubormaydi
    python -m scripts.instagram_plus_campaign --live --confirm YUBORISH
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from typing import Callable, Dict, Iterable, List, Optional

import requests

GRAPH = "https://graph.facebook.com/v19.0"
CONFIRM_TEXT = "YUBORISH"
PRIVATE_REPLY_WINDOW = timedelta(days=7)

PUBLIC_INVITE_TEXT = (
    "Assalomu alaykum! 👋 Qiziqishingiz uchun rahmat. Sizga mos taklifni yuborishimiz "
    "uchun Direct'ga \"+\" deb yozib qo'ying 📩"
)


def _get_paged(url: str, params: Dict, max_pages: int = 50) -> Iterable[Dict]:
    pages = 0
    while url and pages < max_pages:
        resp = requests.get(url, params=params, timeout=20)
        try:
            body = resp.json()
        except ValueError:
            body = {}
        if resp.status_code != 200 or body.get("error"):
            err = (body.get("error") or {}).get("message") or f"HTTP {resp.status_code}"
            raise RuntimeError(err)
        yield from body.get("data", []) or []
        url = (body.get("paging") or {}).get("next", "")
        params = {}
        pages += 1


def _parse_ts(value: str) -> Optional[datetime]:
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%S%z")
    except (TypeError, ValueError):
        return None


def _get_field(node: str, field: str, token: str) -> Optional[Dict]:
    try:
        resp = requests.get(f"{GRAPH}/{node}", params={"fields": field, "access_token": token},
                            timeout=20)
        body = resp.json()
    except (requests.RequestException, ValueError):
        return None
    if resp.status_code != 200 or not isinstance(body, dict) or body.get("error"):
        return None
    value = body.get(field)
    return value if isinstance(value, dict) else None


def discover_ad_accounts(token: str, errors: List[str]) -> List[Dict]:
    """Reklama akkauntlarini topadi: /me/adaccounts (user token), aks holda sahifa
    egasi bo'lgan Business Manager'ning owned/client ad account'lari (page token)."""
    found: Dict[str, Dict] = {}
    edges = ["me/adaccounts"]
    for field in ("business", "owner_business"):
        biz = _get_field("me", field, token)
        if biz and biz.get("id"):
            edges += [f"{biz['id']}/owned_ad_accounts", f"{biz['id']}/client_ad_accounts"]
    for edge in dict.fromkeys(edges):
        try:
            for acc in _get_paged(f"{GRAPH}/{edge}",
                                  {"fields": "id,name", "limit": 50, "access_token": token}):
                if acc.get("id"):
                    found.setdefault(acc["id"], {"id": acc["id"], "name": acc.get("name")})
        except RuntimeError as exc:
            errors.append(f"{edge.split('/')[-1]}: {exc}")
    return list(found.values())


def collect_media_ids(token: str, ig_user_id: str, ad_account_id: str,
                      media_since: datetime, report: Dict) -> List[str]:
    """Profil postlari (media_since dan yangi) + reklama kreativlaridagi IG media."""
    ids: List[str] = []
    try:
        for media in _get_paged(f"{GRAPH}/{ig_user_id}/media",
                                {"fields": "id,timestamp", "limit": 100, "access_token": token}):
            ts = _parse_ts(media.get("timestamp", ""))
            if ts and ts < media_since:
                break
            ids.append(str(media["id"]))
    except RuntimeError as exc:
        report["errors"].append(f"profil postlari: {exc}")
    report["organic_media"] = len(ids)

    if ad_account_id:
        accounts = [ad_account_id if ad_account_id.startswith("act_") else f"act_{ad_account_id}"]
    else:
        accounts = [a["id"] for a in discover_ad_accounts(token, report["errors"])]
    report["ad_accounts"] = len(accounts)
    if not accounts:
        report["errors"].append("reklama akkaunti topilmadi — reklama postlari tekshirilmadi")
    ad_media = set()
    for act in accounts:
        try:
            for ad in _get_paged(f"{GRAPH}/{act}/ads",
                                 {"fields": "creative{effective_instagram_media_id}",
                                  "limit": 100, "access_token": token}):
                media_id = (ad.get("creative") or {}).get("effective_instagram_media_id")
                if media_id:
                    ad_media.add(str(media_id))
        except RuntimeError as exc:
            report["errors"].append(f"reklamalar: {exc}")
    report["ad_media"] = len(ad_media)
    return list(dict.fromkeys(ids + sorted(ad_media)))


def _already_handled(comment: Dict, own_id: str, markers: List[str]) -> bool:
    for reply in (comment.get("replies") or {}).get("data", []) or []:
        mine = str((reply.get("from") or {}).get("id") or "") == own_id
        if mine and any(m in (reply.get("text") or "") for m in markers):
            return True
    return False


def plan_actions(comments: Iterable[Dict], own_id: str, now: datetime,
                 since: datetime, markers: List[str],
                 is_plus: Callable[[str], bool]) -> List[Dict]:
    """Har bir "+" komment uchun 'dm' yoki 'invite' rejasini tuzadi."""
    plan: List[Dict] = []
    seen = set()
    for c in comments:
        cid = str(c.get("id") or "")
        author = str((c.get("from") or {}).get("id") or "")
        ts = _parse_ts(c.get("timestamp", ""))
        if not cid or cid in seen or not ts or ts < since or author == own_id:
            continue
        if not is_plus(c.get("text") or "") or _already_handled(c, own_id, markers):
            continue
        seen.add(cid)
        action = "dm" if now - ts <= PRIVATE_REPLY_WINDOW else "invite"
        plan.append({"comment_id": cid, "action": action})
    return plan


def fetch_comments(token: str, media_ids: List[str], report: Dict) -> List[Dict]:
    out: List[Dict] = []
    fields = "id,text,timestamp,from{id,username},replies{id,from,text}"
    for media_id in media_ids:
        try:
            out.extend(_get_paged(f"{GRAPH}/{media_id}/comments",
                                  {"fields": fields, "limit": 50, "access_token": token}))
        except RuntimeError as exc:
            report["errors"].append(f"media {media_id}: {exc}")
    report["comments_scanned"] = len(out)
    return out


def execute(plan: List[Dict], token: str, send_dm: Callable, reply: Callable,
            dm_text: str, ack_text: str, throttle: float = 3.0) -> Dict[str, int]:
    stats = {"dm_sent": 0, "invite_sent": 0, "failed": 0}
    for item in plan:
        cid = item["comment_id"]
        if item["action"] == "dm":
            ok = send_dm(cid, dm_text, token)
            if ok:
                reply(cid, ack_text, token)
                stats["dm_sent"] += 1
        else:
            ok = reply(cid, PUBLIC_INVITE_TEXT, token)
            if ok:
                stats["invite_sent"] += 1
        if not ok:
            stats["failed"] += 1
        if throttle:
            time.sleep(throttle)
    return stats


def check_token(token: str) -> Dict:
    """Token turi, ruxsatlari (ads_read bormi) va ko'rinadigan reklama akkauntlari."""
    out: Dict = {"valid": False, "type": None, "scopes": [], "ad_accounts": [], "errors": []}
    try:
        resp = requests.get(f"{GRAPH}/debug_token",
                            params={"input_token": token, "access_token": token}, timeout=20)
        data = (resp.json() or {}).get("data") or {}
        out.update(valid=bool(data.get("is_valid")), type=data.get("type"),
                   scopes=sorted(data.get("scopes") or []))
    except (requests.RequestException, ValueError) as exc:
        out["errors"].append(f"debug_token: {type(exc).__name__}")
    out["ad_accounts"] = discover_ad_accounts(token, out["errors"])
    out["ads_read"] = "ads_read" in out["scopes"] or "ads_management" in out["scopes"]
    return out


def _notify_owner(text: str) -> bool:
    """Maxfiy tafsilotlarni (akkaunt ID) public Actions logiga emas, Owner'ga yuboradi."""
    bot, owner = os.environ.get("BOT_TOKEN", "").strip(), os.environ.get("OWNER_ID", "").strip()
    if not bot or not owner:
        return False
    try:
        resp = requests.post(f"https://api.telegram.org/bot{bot}/sendMessage",
                             json={"chat_id": owner, "text": text}, timeout=15)
        return resp.status_code == 200
    except requests.RequestException:
        return False


def run_check(token: str) -> int:
    info = check_token(token)
    print(f"token_valid: {info['valid']}")
    print(f"token_type: {info['type']}")
    print(f"ads_read: {info['ads_read']}")
    print(f"scopes: {info['scopes']}")
    print(f"ad_accounts_found: {len(info['ad_accounts'])}")
    print(f"errors: {info['errors']}")
    lines = [f"{a['id']} — {a['name']}" for a in info["ad_accounts"]] or ["(topilmadi)"]
    sent = _notify_owner("Instagram '+' kampaniya: token tekshiruvi\n"
                         f"ads_read: {'bor' if info['ads_read'] else 'YO`Q'}\n"
                         "Reklama akkauntlari:\n" + "\n".join(lines))
    print(f"owner_notified: {sent}")
    return 0


def _load_env() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    for path in ("/home/ubuntu/oisha-os/.env", ".env"):
        if os.path.exists(path):
            load_dotenv(path)
            return


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--days", type=int, default=60)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--confirm", default="")
    parser.add_argument("--check", action="store_true", help="faqat token ruxsatlarini tekshiradi")
    args = parser.parse_args(argv)

    _load_env()
    from src.services.core.instagram.agent_constants import (
        KEYWORD_AUTOMATION_PUBLIC_ACK, PLUS_COMMENT_DM_TEMPLATE, is_plus_only_comment)
    from src.time_utils import get_local_now, is_quiet_hours

    token = os.environ.get("META_PAGE_ACCESS_TOKEN", "").strip()
    own_id = os.environ.get("META_INSTAGRAM_USER_ID", "").strip()
    ad_account = os.environ.get("META_AD_ACCOUNT_ID", "").strip()
    if not token or not own_id:
        print("XATO: META_PAGE_ACCESS_TOKEN yoki META_INSTAGRAM_USER_ID yo'q")
        return 2
    if args.check:
        return run_check(token)
    if args.live and args.confirm != CONFIRM_TEXT:
        print(f"XATO: live rejim uchun --confirm {CONFIRM_TEXT} kerak")
        return 2
    if args.live and is_quiet_hours(get_local_now()):
        print("XATO: quiet hours (23:00-07:00 Toshkent) — live yuborilmaydi")
        return 3

    now = datetime.now(timezone.utc)
    since = now - timedelta(days=args.days)
    report: Dict = {"errors": []}
    media_ids = collect_media_ids(token, own_id, ad_account, since - timedelta(days=120), report)
    comments = fetch_comments(token, media_ids, report)
    markers = [KEYWORD_AUTOMATION_PUBLIC_ACK, PUBLIC_INVITE_TEXT]
    plan = plan_actions(comments, own_id, now, since, markers, is_plus_only_comment)
    report["plus_dm"] = sum(1 for p in plan if p["action"] == "dm")
    report["plus_invite"] = sum(1 for p in plan if p["action"] == "invite")

    if args.live:
        from src.services.core.instagram.api_helpers import reply_to_comment
        from src.services.core.instagram_agent import send_ig_private_reply
        report.update(execute(plan, token, send_ig_private_reply, reply_to_comment,
                              PLUS_COMMENT_DM_TEMPLATE, KEYWORD_AUTOMATION_PUBLIC_ACK))
    report["mode"] = "live" if args.live else "dry-run"
    for key, value in report.items():
        print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
