import os
import sys
from dotenv import load_dotenv

for env_path in ["/home/ubuntu/oisha-os/.env", ".env"]:
    if os.path.exists(env_path):
        load_dotenv(env_path)
        break

sys.path.insert(0, "/home/ubuntu/oisha-os")
from src.services.core.instagram.api_helpers import reply_to_comment

token = os.environ.get("META_PAGE_ACCESS_TOKEN", "").strip()
cid = "18147175738478768"
text = "😂😂😂😂😂😂"

res = reply_to_comment(cid, text, token)
print(f"Retry result for {cid}: {res}")
