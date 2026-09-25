import subprocess
import sys

sys.stdout.reconfigure(encoding='utf-8')

cmd = [
    "ssh",
    "-i", "C:/Users/baxti/.ssh/oracle_free_tier_ed25519",
    "-o", "StrictHostKeyChecking=no",
    "ubuntu@163.192.10.104",
    """/home/ubuntu/oisha-os/venv/bin/python3 -c "
import os, requests
from dotenv import load_dotenv
load_dotenv('/home/ubuntu/oisha-os/.env')
token = os.getenv('META_PAGE_ACCESS_TOKEN', '')
for form_id in ['1973180183373812', '24790817803944095']:
    url = f'https://graph.facebook.com/v19.0/{form_id}/leads'
    r = requests.get(url, params={'access_token': token, 'fields': 'created_time,id', 'limit': 3}).json()
    print(f'Form {form_id}:', r.get('data', []))
" """
]

res = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=20)
print(res.stdout)
if res.stderr:
    print("STDERR:", res.stderr)
