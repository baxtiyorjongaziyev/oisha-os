import os
import requests
import json
from dotenv import load_dotenv

load_dotenv()

tok = os.getenv("META_PAGE_ACCESS_TOKEN")
ig_id = os.getenv("META_INSTAGRAM_USER_ID", "17841404148272074")

media_list = []
url = f"https://graph.facebook.com/v21.0/{ig_id}/media?fields=id,caption,comments_count,permalink,timestamp&limit=50&access_token={tok}"
while url:
    r = requests.get(url).json()
    media_list.extend(r.get("data", []))
    url = r.get("paging", {}).get("next")

posts_with_comments = [m for m in media_list if m.get("comments_count", 0) > 0]

total_comments = 0
answered_count = 0
unanswered = []

for m in posts_with_comments:
    m_id = m["id"]
    c_url = f"https://graph.facebook.com/v21.0/{m_id}/comments?fields=id,text,from,timestamp,replies{{id,from,text}}&limit=50&access_token={tok}"
    while c_url:
        res = requests.get(c_url).json()
        comments = res.get("data", [])
        for c in comments:
            author = (c.get("from") or {}).get("username", "")
            if author == "baxtiyorjongaziyev":
                continue
            total_comments += 1
            replies = (c.get("replies") or {}).get("data", [])
            has_my_reply = any(
                (r.get("from") or {}).get("username") == "baxtiyorjongaziyev"
                for r in replies
            )
            if has_my_reply:
                answered_count += 1
            else:
                unanswered.append({
                    "author": author,
                    "text": c.get("text", "").replace("\n", " "),
                    "post": (m.get("caption") or "")[:50].replace("\n", " "),
                    "permalink": m.get("permalink"),
                    "id": c.get("id"),
                    "time": c.get("timestamp")
                })
        c_url = res.get("paging", {}).get("next")

print(f"TOTAL_POSTS={len(media_list)}")
print(f"POSTS_WITH_COMMENTS={len(posts_with_comments)}")
print(f"TOTAL_USER_COMMENTS={total_comments}")
print(f"ANSWERED_COMMENTS={answered_count}")
print(f"UNANSWERED_COMMENTS={len(unanswered)}")

with open("audit_comments.json", "w", encoding="utf-8") as f:
    json.dump({"total": total_comments, "answered": answered_count, "unanswered": unanswered}, f, ensure_ascii=False, indent=2)

target_reel = None
for m in media_list:
    cap = (m.get("caption") or "").lower()
    if any(w in cap for w in ["qo'ng'iroq", "qongiroq", "davomiyligi", "telefon", "dadam", "soniya"]):
        target_reel = m
        break

if not target_reel and media_list:
    target_reel = media_list[0]

print(f"\nTARGET REEL: {target_reel.get('permalink')} | Caption: {target_reel.get('caption')[:80]}")
m_id = target_reel["id"]
c_url = f"https://graph.facebook.com/v21.0/{m_id}/comments?fields=id,text,from,timestamp,replies{{id,from,text}}&limit=50&access_token={tok}"
res = requests.get(c_url).json()
comments = res.get("data", [])
print(f"Total top-level comments on this reel: {len(comments)}")
from src.services.core.instagram_agent import like_comment

print(f"\n--- TESTING LIKE ON FIRST COMMENT ---")
if comments:
    first_c_id = comments[0]["id"]
    print(f"Liking comment {first_c_id}...")
    like_ok = like_comment(first_c_id, tok)
    print(f"Like result: {like_ok}")



