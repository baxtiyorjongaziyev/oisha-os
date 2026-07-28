import urllib.request
import urllib.error
import json
import base64
import os
from dotenv import load_dotenv

load_dotenv()
auth = base64.b64encode(b'oisha:oisha_safe_123').decode()
headers = {
    'Authorization': f'Basic {auth}',
    'X-Oisha-Internal-Secret': os.environ.get('OISHA_API_SECRET', '').strip()
}
req = urllib.request.Request('https://oisha.jonbranding.uz/api/internal/mcp/analyze_private_chats', headers=headers)
try:
    with urllib.request.urlopen(req) as resp:
        data = resp.read().decode('utf-8')
        with open('data/private_chats_analysis.json', 'w', encoding='utf-8') as f:
            f.write(data)
        print("Analysis written to data/private_chats_analysis.json")
except urllib.error.HTTPError as e:
    print(f"HTTP Error {e.code}: {e.read().decode('utf-8')}")
except Exception as e:
    print(e)
