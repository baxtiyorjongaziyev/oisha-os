import json
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

path = r"C:\Users\baxti\.gemini\antigravity\brain\7c298b03-97ed-4a1e-bb82-599eacec831c\.system_generated\logs\transcript.jsonl"
imported_leads = []

with open(path, "r", encoding="utf-8") as f:
    for line in f:
        data = json.loads(line)
        content = data.get("content", "")
        if "AMOCRM'GA LIVE INTEGRATSIYA BOSHLANMOQDA" in content:
            # find all [idx/30] Ishlanmoqda: #card_no Name (+phone)... and (Created new lead|Updated existing lead) #id
            blocks = content.split("Ishlanmoqda: #")
            for block in blocks[1:]:
                # e.g. "135 Mirzohidjon (+998914797722)...\n... Created new lead #53259529"
                m_header = re.search(r"^(\d+)\s+([^\(]+)\s+\(\+([^\)]+)\)", block)
                m_action = re.search(r"(Created new lead|Updated existing lead)\s+#(\d+)", block)
                if m_header and m_action:
                    cno = int(m_header.group(1))
                    name = m_header.group(2).strip()
                    phone = m_header.group(3).strip()
                    action = m_action.group(1)
                    lead_id = int(m_action.group(2))
                    imported_leads.append({
                        "idx": len(imported_leads) + 1,
                        "card_no": cno,
                        "client_name": name,
                        "phone": phone,
                        "action": action,
                        "lead_id": lead_id
                    })

print(f"Total imported leads parsed: {len(imported_leads)}")
for item in imported_leads:
    print(f"{item['idx']:2d}. Card #{item['card_no']:3d} | {item['client_name']:20s} | +{item['phone']:12s} -> Lead #{item['lead_id']} ({item['action']})")

with open("data/amocrm_imported_leads.json", "w", encoding="utf-8") as f:
    json.dump(imported_leads, f, ensure_ascii=False, indent=2)
print("Saved data/amocrm_imported_leads.json successfully!")
