import json
import sys
import io
import re

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

utc_data = json.load(open('data/utc_cache/leads_with_recordings.json', 'r', encoding='utf-8'))
target_items = [x for x in utc_data if x.get('lead', {}).get('board') == 'target_leads']

# Load amocrm datasets
utc_pipe_leads = json.load(open('data/amocrm_utc_pipeline_leads.json', 'r', encoding='utf-8'))
contacts = json.load(open('data/amocrm_all_contacts.json', 'r', encoding='utf-8'))

# Map phone numbers in utc_pipe_leads
phone_to_utc_lead = {}
for l in utc_pipe_leads:
    name = l.get('name', '')
    digits = re.findall(r'\d+', name)
    for d in digits:
        if len(d) >= 9:
            phone_to_utc_lead[d[-9:]] = l

print(f"Total target leads in UTC CRM: {len(target_items)}")
print(f"Mappable leads in amoCRM UTC pipeline: {len(phone_to_utc_lead)}")

# Check each target lead
all_candidates = []
for item in target_items:
    l = item['lead']
    card_no = l.get('cardNo')
    name = l.get('name')
    phone = (l.get('phoneNormalized') or l.get('phoneNumber') or '').replace('+', '').replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
    st = l.get('status')
    notes = l.get('notes') or ''
    comments = [c.get('text', '') for c in item.get('comments', [])]
    
    # max duration
    durs = [r.get('duration', 0) for r in item.get('recordings', [])]
    max_dur = max(durs) if durs else 0
    total_dur = sum(durs)
    
    # Match with amoCRM lead in UTC pipeline
    amo_lead = phone_to_utc_lead.get(phone[-9:]) if len(phone) >= 9 else None
    
    all_candidates.append({
        'card_no': card_no,
        'name': name,
        'phone': phone,
        'status': st,
        'max_dur': max_dur,
        'total_dur': total_dur,
        'call_count': len(durs),
        'notes': notes,
        'comments': comments,
        'amo_lead_id': amo_lead.get('id') if amo_lead else None,
        'amo_pipeline_id': amo_lead.get('pipeline_id') if amo_lead else None,
        'amo_status_id': amo_lead.get('status_id') if amo_lead else None,
        'amo_name': amo_lead.get('name') if amo_lead else None
    })

# Score candidates closest to sale
def calc_score(c):
    score = 0
    st = c['status']
    if st == 'Sell':
        score += 100
    elif st == 'V_PROTSESSE':
        score += 70
    elif st == 'Perezvon':
        score += 50
    elif c['max_dur'] >= 300: # 5 mins+
        score += 40
    elif c['max_dur'] >= 120: # 2 mins+
        score += 20
        
    if c['max_dur'] >= 600: # 10 mins+
        score += 25
    elif c['max_dur'] >= 300:
        score += 15
        
    return score

for c in all_candidates:
    c['score'] = calc_score(c)

# Filter high score candidates (score >= 40)
top_candidates = [c for c in all_candidates if c['score'] >= 40]
top_candidates.sort(key=lambda x: (x['score'], x['max_dur']), reverse=True)

print(f"\nTotal Top Candidates Closest to Sale: {len(top_candidates)}")
for i, c in enumerate(top_candidates, 1):
    amo_str = f"amoID {c['amo_lead_id']} (pipe {c['amo_pipeline_id']}, st {c['amo_status_id']})" if c['amo_lead_id'] else "NO AMO MATCH"
    dur_str = f"{c['max_dur']//60}m {c['max_dur']%60}s"
    print(f"{i:2d}. Card #{c['card_no']:3d} | {c['name']:18s} | {c['phone']:12s} | UTC: {c['status']:12s} | Call: {dur_str:7s} | Score: {c['score']:3d} | {amo_str}")

with open('data/top_target_leads_to_move.json', 'w', encoding='utf-8') as f:
    json.dump(top_candidates, f, ensure_ascii=False, indent=2)
