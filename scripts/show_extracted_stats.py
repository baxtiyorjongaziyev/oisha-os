import json
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

with open('data/telegram_2yr_extracted_knowledge.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

for cname, info in data.items():
    ins = info.get('insights', {})
    print(f"=== {cname} (Total: {info.get('total_messages')}) ===")
    print(f"  Finance signals: {len(ins.get('finance_signals', []))}")
    print(f"  Project milestones: {len(ins.get('project_milestones', []))}")
    print(f"  Client leads: {len(ins.get('client_leads', []))}")
    print(f"  Decisions & SOPs: {len(ins.get('decisions_and_sops', []))}")
    
    # Print sample 2 items each
    print("  Sample Project/Finance items:")
    for p in (ins.get('project_milestones', [])[:2] + ins.get('finance_signals', [])[:2]):
        print(f"    - [{p['date']}] {p['sender']}: {p['text'][:100]}")
    print()
