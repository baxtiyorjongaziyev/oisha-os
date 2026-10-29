import json
import sys
import datetime
import requests

sys.stdout.reconfigure(encoding='utf-8')

def main():
    with open('data/amocrm_token.json') as f:
        tok = json.load(f)['access_token']
    headers = {'Authorization': f'Bearer {tok}', 'Content-Type': 'application/json'}
    base = 'https://jonbranding.amocrm.ru'

    r = requests.get(f'{base}/api/v4/leads/unsorted', headers=headers)
    if r.status_code != 200:
        print("Error fetching unsorted:", r.status_code, r.text)
        return

    data = r.json()
    unsorted = data.get('_embedded', {}).get('unsorted', [])
    print(f"Total unsorted: {len(unsorted)}")

    for i, u in enumerate(unsorted):
        uid = u.get('uid')
        meta = u.get('metadata', {})
        client = meta.get('client', {})
        c_name = client.get('name')
        sender = meta.get('from')
        created = u.get('created_at')
        chat_id = meta.get('origin', {}).get('chat_id')
        dt = datetime.datetime.fromtimestamp(created, tz=datetime.timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
        
        # Check single item detail
        ru = requests.get(f'{base}/api/v4/leads/unsorted/{uid}', headers=headers)
        u_detail = ru.json() if ru.status_code == 200 else {}
        
        print(f"\n--- Item #{i+1} ---")
        print(f"UID: {uid}")
        print(f"Client Name: {c_name} (from: {sender})")
        print(f"Time: {dt}")
        print(f"Chat ID: {chat_id}")
        print(f"Metadata: {json.dumps(meta, ensure_ascii=False, indent=2)}")

if __name__ == '__main__':
    main()
