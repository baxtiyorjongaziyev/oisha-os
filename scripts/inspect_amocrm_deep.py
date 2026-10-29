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

    print("=== 1. CHECKING AMOCRM TALKS / CHATS API ===")
    r_talks = requests.get(f'{base}/api/v4/talks?limit=50', headers=headers)
    print(f"Talks status: {r_talks.status_code}")
    if r_talks.status_code == 200:
        talks = r_talks.json().get('_embedded', {}).get('talks', [])
        print(f"Total talks: {len(talks)}")
        for t in talks[:10]:
            print("Talk:", t)

    print("\n=== 2. CHECKING AMOCRM EVENTS (INCOMING CHATS, CALLS, STATUS CHANGES) ===")
    r_events = requests.get(f'{base}/api/v4/events?limit=100', headers=headers)
    print(f"Events status: {r_events.status_code}")
    if r_events.status_code == 200:
        events = r_events.json().get('_embedded', {}).get('events', [])
        print(f"Retrieved {len(events)} events")
        for e in events[:20]:
            etype = e.get('type')
            entity = e.get('entity_type')
            eid = e.get('entity_id')
            c_at = datetime.datetime.fromtimestamp(e.get('created_at', 0), tz=datetime.timezone.utc).strftime('%Y-%m-%d %H:%M')
            val = e.get('value_after')
            print(f"  [{c_at}] Type: {etype} | {entity} #{eid} | Val: {val}")

    print("\n=== 3. CALLS IN AMOCRM (CHECKING IF MANAGERS ACTUALLY CALLED CLIENTS) ===")
    r_calls = requests.get(f'{base}/api/v4/calls?limit=50', headers=headers)
    print(f"Calls status: {r_calls.status_code}")
    if r_calls.status_code == 200:
        calls = r_calls.json().get('_embedded', {}).get('calls', [])
        print(f"Total calls logged: {len(calls)}")
        for c in calls[:15]:
            c_phone = c.get('phone')
            c_dur = c.get('duration')
            c_src = c.get('source')
            c_status = c.get('call_status')
            c_time = datetime.datetime.fromtimestamp(c.get('created_at', 0), tz=datetime.timezone.utc).strftime('%Y-%m-%d %H:%M')
            print(f"  [{c_time}] Call to: {c_phone} | Duration: {c_dur}s | Status: {c_status} | Source: {c_src}")

    print("\n=== 4. LEADS WITH BUYING/PAYMENT SIGNALS IN PIPELINE ===")
    # Let's inspect leads in status "Kelishuv / Yopish" (88871066), "Uchrashuv" (87609526), "Topshirishga tayyor", "Yakuniy 50% to'lov kutilmoqda"
    target_statuses = [88871066, 87609526, 89380154, 80215438, 86306514, 87609546, 87609550]
    
    for sid in target_statuses:
        r_lead = requests.get(f'{base}/api/v4/leads?filter[statuses][0][status_id]={sid}&with=contacts', headers=headers)
        if r_lead.status_code == 200:
            leads = r_lead.json().get('_embedded', {}).get('leads', [])
            if leads:
                print(f"\n--- Status ID {sid} (Count: {len(leads)}) ---")
                for ld in leads:
                    lid = ld.get('id')
                    lname = ld.get('name')
                    price = ld.get('price')
                    up_at = datetime.datetime.fromtimestamp(ld.get('updated_at', 0), tz=datetime.timezone.utc).strftime('%Y-%m-%d')
                    contacts = ld.get('_embedded', {}).get('contacts', [])
                    c_ids = [str(c.get('id')) for c in contacts]
                    
                    # fetch notes for this lead
                    r_notes = requests.get(f'{base}/api/v4/leads/{lid}/notes', headers=headers)
                    notes_summary = []
                    if r_notes.status_code == 200:
                        for n in r_notes.json().get('_embedded', {}).get('notes', []):
                            p = n.get('params', {})
                            txt = p.get('text') or p.get('message') or ''
                            if txt:
                                notes_summary.append(txt[:80].replace('\n', ' '))
                    
                    print(f"  Lead #{lid}: {lname} | Price: {price:,} UZS | Updated: {up_at} | Contacts: {c_ids}")
                    if notes_summary:
                        print(f"    Notes: {' || '.join(notes_summary[:3])}")

if __name__ == '__main__':
    main()
