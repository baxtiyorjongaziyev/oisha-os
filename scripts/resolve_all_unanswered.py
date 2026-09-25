"""Resolve all unanswered Instagram comments safely with AI context and Anti-Romance Emoji Guard.
Adheres to Rule 6 (<= 400 lines).
"""
import os
import sys
import re
import asyncio
import requests
from dotenv import load_dotenv

for env_path in ["/home/ubuntu/oisha-os/.env", ".env", "../.env"]:
    if os.path.exists(env_path):
        load_dotenv(env_path)
        break

sys.path.insert(0, "/home/ubuntu/oisha-os")
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

token = os.environ.get("META_PAGE_ACCESS_TOKEN", "").strip()
own_id = str(os.environ.get("META_INSTAGRAM_USER_ID", "17841404148272074")).strip()

if not token:
    print("[ERROR] META_PAGE_ACCESS_TOKEN not set!")
    sys.exit(1)

from src.services.core.instagram.emoji_utils import get_mirror_emoji_reply, strip_romantic_emojis
from src.services.core.instagram.api_helpers import like_comment, reply_to_comment
from src.services.core.instagram_agent import generate_comment_reply

def fetch_all_media():
    url = f"https://graph.facebook.com/v19.0/{own_id}/media"
    params = {
        "fields": "id,caption,permalink,timestamp,comments_count",
        "limit": 100,
        "access_token": token,
    }
    all_items = []
    while url:
        resp = requests.get(url, params=params, timeout=20)
        if resp.status_code != 200:
            print(f"[ERROR] Fetch media failed: {resp.status_code} {resp.text}")
            break
        data = resp.json()
        items = data.get("data", [])
        all_items.extend(items)
        url = (data.get("paging") or {}).get("next")
        params = {}
    return all_items

def fetch_media_comments(media_id):
    url = f"https://graph.facebook.com/v19.0/{media_id}/comments"
    params = {
        "fields": "id,text,from,timestamp,like_count,replies{id,from,text,timestamp}",
        "limit": 50,
        "access_token": token,
    }
    all_comments = []
    while url:
        try:
            resp = requests.get(url, params=params, timeout=20)
            if resp.status_code != 200:
                break
            data = resp.json()
            all_comments.extend(data.get("data", []) or [])
            url = (data.get("paging") or {}).get("next")
            params = {}
        except Exception as exc:
            print(f"[WARN] Error fetching comments for {media_id}: {exc}")
            break
    return all_comments

async def resolve_all():
    print(f"[START] Scanning Instagram for unanswered comments (own_id: {own_id})...")
    media_list = fetch_all_media()
    with_comments = [m for m in media_list if m.get("comments_count", 0) > 0]
    print(f"Total media: {len(media_list)}, with comments: {len(with_comments)}")

    unanswered = []
    for m in with_comments:
        mid = m.get("id")
        permalink = m.get("permalink") or ""
        caption = m.get("caption") or ""
        comments = fetch_media_comments(mid)
        for c in comments:
            cid = c.get("id")
            text = (c.get("text") or "").strip()
            frm = c.get("from") or {}
            c_user = frm.get("username") or frm.get("name") or frm.get("id") or "foydalanuvchi"
            c_id = str(frm.get("id") or "")
            if c_id == own_id or c_user.lower() == "baxtiyorjongaziyev":
                continue
            replies = (c.get("replies") or {}).get("data", []) or []
            already = any(
                str((r.get("from") or {}).get("id") or "") == own_id
                or str((r.get("from") or {}).get("username") or "").lower() == "baxtiyorjongaziyev"
                for r in replies
            )
            if not already:
                unanswered.append({
                    "media_id": mid,
                    "permalink": permalink,
                    "caption": caption,
                    "comment_id": cid,
                    "user": c_user,
                    "text": text,
                })

    print(f"\n[FOUND] {len(unanswered)} unanswered comments to resolve.\n")
    if not unanswered:
        print("[DONE] No unanswered comments found!")
        return

    success_count = 0
    for idx, item in enumerate(unanswered, 1):
        cid = item["comment_id"]
        c_user = item["user"]
        text = item["text"]
        caption = item["caption"]
        permalink = item["permalink"]

        print(f"[{idx}/{len(unanswered)}] Processing comment {cid} by @{c_user}: \"{text}\"")

        # 1. Like comment (optional / best effort)
        try:
            like_ok = like_comment(cid, token)
            print(f"   Like status: {like_ok}")
        except Exception as e:
            print(f"   Like err: {e}")

        # 2. Determine reply text
        if not text:
            reply_text = "Fikringiz uchun rahmat! 🤝"
        else:
            emoji_mirror = get_mirror_emoji_reply(text)
            if emoji_mirror:
                reply_text = emoji_mirror
                print(f"   Mirrored emojis: {reply_text}")
            else:
                try:
                    ai_reply = await generate_comment_reply(text, caption, c_user)
                    reply_text = re.sub(r"\[.*?\]", "", ai_reply).strip()
                    reply_text = strip_romantic_emojis(reply_text)
                    if not reply_text:
                        reply_text = "Fikringiz uchun rahmat! 🤝"
                    print(f"   AI reply: {reply_text}")
                except Exception as exc:
                    print(f"   AI err: {exc}")
                    reply_text = "Fikringiz uchun katta rahmat! 🤝"

        # 3. Send reply
        try:
            reply_ok = reply_to_comment(cid, reply_text, token)
            print(f"   Reply sent status: {reply_ok}")
            if reply_ok:
                success_count += 1
        except Exception as exc:
            print(f"   Reply err: {exc}")

        # Throttle 2s
        await asyncio.sleep(2)

    print(f"\n[COMPLETE] Successfully answered {success_count}/{len(unanswered)} comments.")

if __name__ == "__main__":
    asyncio.run(resolve_all())
