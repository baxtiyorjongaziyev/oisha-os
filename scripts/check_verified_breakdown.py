import json
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

leads = json.load(open('data/amocrm_hot_leads_verified.json', 'r', encoding='utf-8'))
utc_pipe = [l for l in leads if l['pipeline_id'] == 11322658]
sotuv_pipe = [l for l in leads if l['pipeline_id'] == 11162698]

print(f"Total leads in file: {len(leads)}")
print(f"In UTC pipeline (11322658): {len(utc_pipe)}")
print(f"In Sotuv Bo'limi pipeline (11162698): {len(sotuv_pipe)}")

print("\n--- LEADS CURRENTLY IN UTC PIPELINE (11322658) THAT NEED TRANSFER ---")
for l in utc_pipe:
    print(f"Lead ID {l['lead_id']}: Card #{l['card_no']} {l['client_name']} ({l['phone']}) - status={l['status_id']}")

print("\n--- LEADS ALREADY IN SOTUV BO'LIMI PIPELINE (11162698) ---")
for l in sotuv_pipe:
    print(f"Lead ID {l['lead_id']}: Card #{l['card_no']} {l['client_name']} ({l['phone']}) - status={l['status_id']}")
