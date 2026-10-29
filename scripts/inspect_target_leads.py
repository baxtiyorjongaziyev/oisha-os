import json
import sys
import io
import re

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

utc_data = json.load(open('data/utc_cache/leads_with_recordings.json', 'r', encoding='utf-8'))
target_items = [x for x in utc_data if x.get('lead', {}).get('board') == 'target_leads']
print(f"Total Target Leads: {len(target_items)}")

# Categorize target leads
statuses = {}
for item in target_items:
    st = item['lead'].get('status', 'None')
    statuses[st] = statuses.get(st, 0) + 1
print("Statuses in target_leads:", statuses)

# Check extCrmId or bitrixDealId on lead
with_crm = [x for x in target_items if x['lead'].get('extCrmId') or x['lead'].get('bitrixDealId')]
print(f"Target leads with CRM ID: {len(with_crm)}")

def get_max_duration(item):
    durs = [r.get('duration', 0) for r in item.get('recordings', [])]
    return max(durs) if durs else 0

for item in target_items:
    item['max_dur'] = get_max_duration(item)

# Let's inspect leads with duration >= 120s or positive status
high_intent = []
for item in target_items:
    l = item['lead']
    dur = item['max_dur']
    st = l.get('status', '')
    comments = item.get('comments', [])
    notes = l.get('notes', '')
    # High intent criteria: status is Sell, V_PROTSESSE, Perezvon, or long call >= 180s
    if st in ['Sell', 'V_PROTSESSE', 'Perezvon'] or dur >= 180:
        high_intent.append(item)

print(f"High intent target leads: {len(high_intent)}")
high_intent.sort(key=lambda x: (x['lead'].get('status') == 'Sell', x['lead'].get('status') == 'V_PROTSESSE', x['max_dur']), reverse=True)

for i, x in enumerate(high_intent, 1):
    l = x['lead']
    card_no = l.get('cardNo', '')
    name = l.get('name', '')
    phone = l.get('phoneNormalized') or l.get('phoneNumber')
    st = l.get('status', '')
    dur = x['max_dur']
    notes = l.get('notes') or ''
    ext_id = l.get('extCrmId') or l.get('bitrixDealId') or ''
    print(f"{i:2d}. Card #{card_no} | {name} | {phone} | Status: {st} | Call: {dur//60}m {dur%60}s | amoID: {ext_id}")
    if notes:
        print(f"    Notes: {notes[:100]}...")
