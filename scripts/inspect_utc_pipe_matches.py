import json
import sys
import io
import re

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

utc_pipe_leads = json.load(open('data/amocrm_utc_pipeline_leads.json', 'r', encoding='utf-8'))
utc_cache = json.load(open('data/utc_cache/leads_with_recordings.json', 'r', encoding='utf-8'))
contacts = json.load(open('data/amocrm_all_contacts.json', 'r', encoding='utf-8'))

# Map contact ID to phone
contact_phones = {}
for c in contacts:
    cid = c['id']
    for f in c.get('custom_fields_values', []) or []:
        if f.get('field_code') == 'PHONE':
            for v in f.get('values', []):
                val = v.get('value', '').replace('+', '').replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
                if len(val) >= 9:
                    contact_phones[cid] = val[-9:]

# Map UTC cache by phone
utc_by_phone = {}
for item in utc_cache:
    l = item['lead']
    p = (l.get('phoneNormalized') or l.get('phoneNumber') or '').replace('+', '').replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
    if len(p) >= 9:
        utc_by_phone[p[-9:]] = item

matched = []
for ld in utc_pipe_leads:
    ld_id = ld['id']
    ld_name = ld['name']
    
    # Try phone from name
    phone = None
    digits = re.findall(r'\d+', ld_name)
    for d in digits:
        if len(d) >= 9:
            phone = d[-9:]
            break
            
    # Try phone from embedded contact
    if not phone:
        cnts = ld.get('_embedded', {}).get('contacts', [])
        for c_ref in cnts:
            cid = c_ref.get('id')
            if cid in contact_phones:
                phone = contact_phones[cid]
                break
                
    utc_item = utc_by_phone.get(phone) if phone else None
    if utc_item:
        l = utc_item['lead']
        durs = [r.get('duration', 0) for r in utc_item.get('recordings', [])]
        max_dur = max(durs) if durs else 0
        matched.append({
            'amo_id': ld_id,
            'amo_name': ld_name,
            'amo_status': ld['status_id'],
            'card_no': l.get('cardNo'),
            'board': l.get('board'),
            'utc_name': l.get('name'),
            'utc_status': l.get('status'),
            'phone': phone,
            'max_dur': max_dur,
            'notes': l.get('notes') or '',
            'recordings_count': len(durs)
        })

print(f"Total leads in amoCRM UTC pipeline: {len(utc_pipe_leads)}")
print(f"Matched by Name + Contact ID to UTC: {len(matched)}")

# Check high intent
high_intent = [m for m in matched if m['utc_status'] in ['Sell', 'V_PROTSESSE', 'Perezvon'] or m['max_dur'] >= 180]
print(f"Total High Intent leads in amoCRM UTC pipeline: {len(high_intent)}")
for i, h in enumerate(high_intent, 1):
    dur_str = f"{h['max_dur']//60}m {h['max_dur']%60}s"
    print(f"{i:2d}. amoID {h['amo_id']} | Card #{h['card_no']:3d} | {h['utc_name']:20s} | {h['phone']} | UTC: {h['utc_status']:12s} | Call: {dur_str} | amoStatus: {h['amo_status']}")

with open('data/matched_high_intent_utc_pipeline.json', 'w', encoding='utf-8') as f:
    json.dump(high_intent, f, ensure_ascii=False, indent=2)
