import json
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

plan = json.load(open('data/target_leads_to_sotuv_final_plan.json', 'r', encoding='utf-8'))

for item in plan[:15]:
    c_no = item['card_no']
    name = item['client_name']
    phone = item['phone']
    st = item['utc_status']
    notes = item.get('notes', '')
    comments = item.get('comments', [])
    print(f"Card #{c_no} | {name} ({phone}) | UTC: {st}")
    if notes:
        print(f"   Notes: {notes}")
    if comments:
        print(f"   Comments: {comments[:2]}")
