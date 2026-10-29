import sys
import json

sys.stdout.reconfigure(encoding='utf-8')

with open('data/utc_cache/leads_with_recordings.json', 'r', encoding='utf-8') as f:
    leads = json.load(f)

not_int = [l for l in leads if l['lead'].get('status') == 'Not interested']
not_int.sort(key=lambda l: sum(r['duration_sec'] for r in l['recordings']), reverse=True)

print(f'\n=== Top 15 Longest "Not interested" Leads (Total: {len(not_int)}) ===')
for l in not_int[:15]:
    ld = l['lead']
    recs = l['recordings']
    tot_d = sum(r['duration_sec'] for r in recs)
    card_no = ld.get('cardNo')
    name = ld.get('name')
    phone = ld.get('phoneNumber')
    print(f'  #{card_no} {name} ({phone}) -> {len(recs)} recs, {tot_d}s ({tot_d/60:.1f}m)')
