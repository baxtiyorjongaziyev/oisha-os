"""Audit all Instagram comments to find any unanswered comments across all posts/reels.
Adheres to Rule 6 (<= 400 lines).
"""
import os
import sys
import requests
from dotenv import load_dotenv

# Try multiple env locations
for env_path in ["/home/ubuntu/oisha-os/.env", ".env", "../.env"]:
    if os.path.exists(env_path):
        load_dotenv(env_path)
        break

# Create a requests session with retries and longer timeout
import urllib3
from requests.adapters import HTTPAdapter

session = requests.Session()
retry_strategy = urllib3.util.retry.Retry(
    total=5,
    backoff_factor=2,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["GET", "POST"]
)
adapter = HTTPAdapter(max_retries=retry_strategy)
session.mount("https://", adapter)
session.mount("http://", adapter)

token = os.environ.get("META_PAGE_ACCESS_TOKEN", "").strip()
own_id = str(os.environ.get("META_INSTAGRAM_USER_ID", "17841404148272074")).strip()

if not token:
    print("ERROR: META_PAGE_ACCESS_TOKEN not found in environment!")
    sys.exit(1)

print(f"[AUDIT START] Instagram User ID: {own_id}")

def fetch_all_media():
    url = f"https://graph.facebook.com/v19.0/{own_id}/media"
    params = {
        "fields": "id,caption,permalink,timestamp,comments_count",
        "limit": 100,
        "access_token": token,
    }
    all_items = []
    while url:
        resp = session.get(url, params=params, timeout=30)
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

def run_audit():
    print("[1/2] Fetching all media items...")
    media_list = fetch_all_media()
    print(f"Total media items found: {len(media_list)}")
    
    with_comments = [m for m in media_list if m.get("comments_count", 0) > 0]
    print(f"Media items with comments: {len(with_comments)}")
    
    print("\n[2/2] Scanning comments for answers...")
    total_comments_checked = 0
    unanswered_comments = []
    
    for idx, m in enumerate(with_comments):
        mid = m.get("id")
        permalink = m.get("permalink") or f"https://instagram.com/p/{mid}"
        caption = (m.get("caption") or "")[:60].replace("\n", " ")
        c_count = m.get("comments_count", 0)
        
        comments = fetch_media_comments(mid)
        for c in comments:
            total_comments_checked += 1
            cid = c.get("id")
            text = (c.get("text") or "").strip()
            c_time = c.get("timestamp") or ""
            frm = c.get("from") or {}
            c_user = frm.get("username") or frm.get("name") or frm.get("id") or "unknown"
            c_id = str(frm.get("id") or "")
            
            # Skip own comments
            if c_id == own_id or c_user.lower() == "baxtiyorjongaziyev":
                continue
            
            # Check replies
            replies = (c.get("replies") or {}).get("data", []) or []
            has_reply = any(
                str((r.get("from") or {}).get("id") or "") == own_id
                or str((r.get("from") or {}).get("username") or "").lower() == "baxtiyorjongaziyev"
                for r in replies
            )
            
            if not has_reply:
                unanswered_comments.append({
                    "media_id": mid,
                    "permalink": permalink,
                    "caption": caption,
                    "comment_id": cid,
                    "user": c_user,
                    "text": text,
                    "timestamp": c_time,
                })

    print("\n" + "="*60)
    print("INSTAGRAM AUDIT RESULTS")
    print("="*60)
    print(f"Total Media Inspected: {len(media_list)}")
    print(f"Media with Comments: {len(with_comments)}")
    print(f"Total Comments Checked: {total_comments_checked}")
    print(f"Answered Comments: {total_comments_checked - len(unanswered_comments)}")
    print(f"Unanswered Comments: {len(unanswered_comments)}")
    print("="*60)
    
    if unanswered_comments:
        print("\nUNANSWERED COMMENTS LIST:")
        for i, u in enumerate(unanswered_comments, 1):
            print(f"\n{i}. [{u['timestamp']}] @{u['user']}: \"{u['text']}\"")
            print(f"   Post: {u['permalink']}")
            print(f"   Caption: {u['caption']}...")
            print(f"   Comment ID: {u['comment_id']}")
    else:
        print("\nSUCCESS: All comments on all posts have been answered! Javobsiz comment yo'q.")

if __name__ == "__main__":
    run_audit()
