import json
import sys
import io
import time
import requests

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

token = json.load(open('data/amocrm_token.json', 'r', encoding='utf-8'))
headers = {'Authorization': f"Bearer {token['access_token']}"}

# Load UTC target leads
utc_data = json.load(open('data/utc_cache/leads_with_recordings.json', 'r', encoding='utf-8'))
target_items = [x for x in utc_data if x.get('lead', {}).get('board') == 'target_leads']

# Identify all high-intent leads: status in ['Sell', 'V_PROTSESSE', 'Perezvon']
high_intent_cards = []
for x in target_items:
    l = x['lead']
    st = l.get('status')
    if st in ['Sell', 'V_PROTSESSE', 'Perezvon']:
        high_intent_cards.append(x)

print(f"Total High Intent leads in target_leads: {len(high_intent_cards)}")

# Check each one in amoCRM
found_leads = []
for item in high_intent_cards:
    l = item['lead']
    card_no = l.get('cardNo')
    name = l.get('name')
    phone = (l.get('phoneNormalized') or l.get('phoneNumber') or '').replace('+', '').replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
    st = l.get('status')
    notes = l.get('notes') or ''
    
    # search lead in amoCRM
    query = phone[-9:] if len(phone) >= 9 else phone
    r = requests.get(f'https://jonbranding.amocrm.ru/api/v4/leads?query={query}', headers=headers, timeout=10)
    lead_obj = None
    if r.status_code == 200:
        data = r.json()
        leads = data.get('_embedded', {}).get('leads', [])
        if leads:
            lead_obj = leads[0]
            
    found_leads.append({
        'card_no': card_no,
        'name': name,
        'phone': phone,
        'utc_status': st,
        'notes': notes,
        'amo_lead': {
            'id': lead_obj['id'],
            'pipeline_id': lead_obj['pipeline_id'],
            'status_id': lead_obj['status_id'],
            'name': lead_obj['name']
        } if lead_obj else None
    })
    time.sleep(0.2)

print("\n--- HIGH INTENT UTC TARGET LEADS AUDIT ---")
for f in found_leads:
    amo = f['amo_lead']
    if amo:
        p_name = "Sotuv Bo'limi" if amo['pipeline_id'] == 11162698 else ("UTC" if amo['pipeline_id'] == 11322658 else f"Other({amo['pipeline_id']})")
        print(f"Card #{f['card_no']:3d} | {f['name']:20s} | {f['phone']:12s} | UTC: {f['utc_status']:12s} -> amoID: {amo['id']} | {p_name:15s} (status {amo['status_id']})")
    else:
        print(f"Card #{f['card_no']:3d} | {f['name']:20s} | {f['phone']:12s} | UTC: {f['utc_status']:12s} -> NOT IN AMOCRM")

with open('data/utc_target_leads_amo_status.json', 'w', encoding='utf-8') as f_out:
    json.dump(found_leads, f_out, ensure_ascii=False, indent=2)
