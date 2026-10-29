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

    r_pipe = requests.get(f'{base}/api/v4/leads/pipelines', headers=headers)
    statuses_map = {}
    if r_pipe.status_code == 200:
        for p in r_pipe.json().get('_embedded', {}).get('pipelines', []):
            for s in p.get('_embedded', {}).get('statuses', []):
                statuses_map[s.get('id')] = s.get('name')

    r = requests.get(f'{base}/api/v4/talks?limit=100', headers=headers)
    if r.status_code != 200:
        print("Talks error:", r.status_code)
        return
        
    talks = r.json().get('_embedded', {}).get('talks', [])
    print(f"Total talks fetched: {len(talks)}")

    talk_leads_with_phones = []
    talk_leads_without_phones = []

    for t in talks:
        tid = t.get('talk_id')
        cid = t.get('contact_id')
        lid = t.get('entity_id')
        t_status = t.get('status')
        origin = t.get('origin')
        c_at = datetime.datetime.fromtimestamp(t.get('created_at', 0), tz=datetime.timezone.utc).strftime('%Y-%m-%d %H:%M')
        
        # Get contact info
        c_name = "N/A"
        phone = None
        if cid:
            rc = requests.get(f'{base}/api/v4/contacts/{cid}', headers=headers)
            if rc.status_code == 200:
                cdata = rc.json()
                c_name = cdata.get('name')
                for fld in cdata.get('custom_fields_values') or []:
                    if fld.get('field_code') == 'PHONE':
                        phone = fld['values'][0]['value']
                        
        # Get lead info if exists
        l_name = "N/A"
        price = 0
        status_name = "N/A"
        notes = []
        if lid:
            rl = requests.get(f'{base}/api/v4/leads/{lid}', headers=headers)
            if rl.status_code == 200:
                ldata = rl.json()
                l_name = ldata.get('name')
                price = ldata.get('price') or 0
                sid = ldata.get('status_id')
                status_name = statuses_map.get(sid, f"Status_{sid}")
            
            rn = requests.get(f'{base}/api/v4/leads/{lid}/notes', headers=headers)
            if rn.status_code == 200:
                for n in rn.json().get('_embedded', {}).get('notes', []):
                    p = n.get('params', {})
                    txt = p.get('text') or p.get('message') or ''
                    if txt:
                        notes.append(txt[:100].replace('\n', ' '))

        item = {
            'talk_id': tid,
            'time': c_at,
            'origin': origin,
            'contact_id': cid,
            'contact_name': c_name,
            'phone': phone,
            'lead_id': lid,
            'lead_name': l_name,
            'price': price,
            'status': status_name,
            'talk_status': t_status,
            'notes': notes
        }
        
        if phone:
            talk_leads_with_phones.append(item)
        else:
            talk_leads_without_phones.append(item)

    print(f"\n==========================================")
    print(f"TALKS WITH PHONE NUMBERS: {len(talk_leads_with_phones)}")
    print(f"==========================================")
    for it in talk_leads_with_phones:
        print(f"\nTalk #{it['talk_id']} | Date: {it['time']} | Origin: {it['origin']}")
        print(f"  Contact: {it['contact_name']} (ID: {it['contact_id']}) | Phone: {it['phone']}")
        print(f"  Lead: #{it['lead_id']} - '{it['lead_name']}' | Budget: {it['price']:,} UZS | Status: {it['status']} (Talk: {it['talk_status']})")
        if it['notes']:
            print(f"  Notes/Call History: {' || '.join(it['notes'][:3])}")
        else:
            print("  Notes/Call History: [NO NOTES / NO CALL LOGGED]")

    print(f"\n==========================================")
    print(f"TALKS WITHOUT PHONE NUMBERS: {len(talk_leads_without_phones)}")
    print(f"==========================================")
    for it in talk_leads_without_phones[:15]:
        print(f"Talk #{it['talk_id']} ({it['time']}) | Contact: {it['contact_name']} | Lead: #{it['lead_id']} '{it['lead_name']}' | Status: {it['status']} ({it['talk_status']})")

if __name__ == '__main__':
    main()
