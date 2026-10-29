import json
import requests
import sys

sys.stdout.reconfigure(encoding='utf-8')

with open('data/utc_session.json', 'r', encoding='utf-8') as f:
    sess = json.load(f)

headers = {
    'Authorization': f'Bearer {sess["token"]}',
    'x-company-id': sess.get('company', 'company_default'),
    'Accept': 'application/json',
    'User-Agent': 'Mozilla/5.0'
}

# Fetch all leads
url = 'https://sales.kontaktmarkazi.com/api/leads?take=500'
r = requests.get(url, headers=headers)
data = r.json()
leads = data.get('data', {}).get('leads', [])
print(f'Total leads fetched: {len(leads)}')

# Let's inspect events for the first 20 leads, looking for calls
calls_found = []
for idx, lead in enumerate(leads):
    lid = lead.get('id')
    ev_url = f'https://sales.kontaktmarkazi.com/api/leads/{lid}/events'
    ev_r = requests.get(ev_url, headers=headers)
    if ev_r.status_code == 200:
        ev_data = ev_r.json().get('data', {})
        events = ev_data.get('events', [])
        for ev in events:
            # Check if event is call or has recording
            if ev.get('type') == 'call' or ev.get('recordingId') or ev.get('call'):
                calls_found.append({
                    'lead_id': lid,
                    'card_no': lead.get('cardNo'),
                    'name': lead.get('name'),
                    'phone': lead.get('phoneNumber'),
                    'status': lead.get('status'),
                    'event': ev
                })
    if len(calls_found) >= 5 or idx >= 50:
        print(f'Checked {idx+1} leads, found {len(calls_found)} calls so far.')
        if len(calls_found) >= 5:
            break

print(f'Calls found: {len(calls_found)}')
if calls_found:
    first_call = calls_found[0]
    print('First call sample:', json.dumps(first_call, indent=2, ensure_ascii=False))
    rec_id = first_call['event'].get('recordingId') or (first_call['event'].get('call', {}) or {}).get('recordingId')
    print('Testing recording download for rec_id:', rec_id)
    if rec_id:
        rec_url = f'https://sales.kontaktmarkazi.com/api/recordings/{rec_id}/file'
        rec_r = requests.get(rec_url, headers=headers, stream=True)
        print('Recording download status:', rec_r.status_code)
        print('Content-Type:', rec_r.headers.get('content-type'))
        print('Content-Length:', rec_r.headers.get('content-length'))
