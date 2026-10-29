import json
import requests
import sys
import os
import time

sys.stdout.reconfigure(encoding='utf-8')

with open('data/utc_session.json', 'r', encoding='utf-8') as f:
    sess = json.load(f)

headers = {
    'Authorization': f'Bearer {sess["token"]}',
    'x-company-id': sess.get('company', 'company_default'),
    'Accept': 'application/json',
    'User-Agent': 'Mozilla/5.0'
}

# 1. Fetch all leads
print('Fetching all leads...')
r = requests.get('https://sales.kontaktmarkazi.com/api/leads?take=1000', headers=headers)
leads_data = r.json().get('data', {}).get('leads', [])
print(f'Total leads fetched: {len(leads_data)}')

# Save raw leads
os.makedirs('data/utc_cache', exist_ok=True)
with open('data/utc_cache/all_leads.json', 'w', encoding='utf-8') as f:
    json.dump(leads_data, f, ensure_ascii=False, indent=2)

# 2. Iterate through leads and collect events
all_calls = []
leads_with_recordings = []

start_time = time.time()
for idx, lead in enumerate(leads_data):
    lid = lead.get('id')
    ev_url = f'https://sales.kontaktmarkazi.com/api/leads/{lid}/events'
    try:
        ev_r = requests.get(ev_url, headers=headers, timeout=10)
        if ev_r.status_code == 200:
            events = ev_r.json().get('data', {}).get('events', [])
            lead_calls = []
            comments = []
            for ev in events:
                if ev.get('comment') and ev.get('type') != 'call':
                    comments.append({
                        'text': ev.get('comment'),
                        'by': ev.get('byLogin'),
                        'date': ev.get('createdAt')
                    })
                if ev.get('type') == 'call' or ev.get('recordingId') or ev.get('call'):
                    rec_id = ev.get('recordingId') or (ev.get('call', {}) or {}).get('recordingId')
                    duration = ev.get('recordingDurationSec') or (ev.get('call', {}) or {}).get('talkDurationSec') or 0
                    call_obj = {
                        'event_id': ev.get('id'),
                        'call_id': ev.get('callId'),
                        'lead_id': lid,
                        'card_no': lead.get('cardNo'),
                        'client_name': lead.get('name'),
                        'phone': lead.get('phoneNumber'),
                        'status': lead.get('status'),
                        'board': lead.get('board'),
                        'operator_login': ev.get('byLogin') or (ev.get('call', {}) or {}).get('operatorLogin'),
                        'operator_name': (lead.get('assignedToOperator') or {}).get('fullName'),
                        'recording_id': rec_id,
                        'duration_sec': duration,
                        'created_at': ev.get('createdAt'),
                        'call_meta': ev.get('call'),
                        'comment': ev.get('comment')
                    }
                    lead_calls.append(call_obj)
                    all_calls.append(call_obj)
            
            # Check if this lead has any calls with audio recording
            recs = [c for c in lead_calls if c['recording_id'] and c['duration_sec'] > 0]
            if recs:
                leads_with_recordings.append({
                    'lead': lead,
                    'recordings': recs,
                    'all_calls': lead_calls,
                    'comments': comments
                })
    except Exception as e:
        print(f'Error fetching lead {lid}: {e}')

    if (idx + 1) % 50 == 0 or (idx + 1) == len(leads_data):
        elapsed = time.time() - start_time
        print(f'Progress: {idx+1}/{len(leads_data)} leads scanned ({elapsed:.1f}s). Total calls: {len(all_calls)}, Leads with audio: {len(leads_with_recordings)}')

with open('data/utc_cache/leads_with_recordings.json', 'w', encoding='utf-8') as f:
    json.dump(leads_with_recordings, f, ensure_ascii=False, indent=2)

with open('data/utc_cache/all_calls.json', 'w', encoding='utf-8') as f:
    json.dump(all_calls, f, ensure_ascii=False, indent=2)

total_audio_calls = sum(len(l['recordings']) for l in leads_with_recordings)
total_audio_sec = sum(c['duration_sec'] for l in leads_with_recordings for c in l['recordings'])
print('\n=== SCAN COMPLETE ===')
print(f'Total leads: {len(leads_data)}')
print(f'Total call events: {len(all_calls)}')
print(f'Leads with actual audio recordings (duration > 0): {len(leads_with_recordings)}')
print(f'Total audio recordings: {total_audio_calls}')
print(f'Total audio duration: {total_audio_sec} seconds ({total_audio_sec/60:.1f} minutes, {total_audio_sec/3600:.2f} hours)')
