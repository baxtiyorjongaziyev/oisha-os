import json
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

with open("data/utc_cache/leads_with_recordings.json", "r", encoding="utf-8") as f:
    cache = json.load(f)

nps_cards = []

for item in cache:
    lead = item.get("lead", {})
    cno = lead.get("cardNo")
    name = lead.get("name")
    board = lead.get("board") or item.get("board")
    comments = item.get("comments", [])
    recs = item.get("recordings", [])
    
    is_nps = False
    nps_notes = []
    
    for c in comments:
        text = c.get("text", "")
        if "Video otziv" in text or "Loyihalar:" in text or re.search(r"1\.\s*\d+", text) or "Vidio" in text or "otziv" in text.lower():
            is_nps = True
            nps_notes.append(text)
            
    if is_nps:
        nps_cards.append({
            "card_no": cno,
            "name": name,
            "board": board,
            "recordings_count": len(recs),
            "recordings": recs,
            "comments": comments,
            "nps_notes": nps_notes
        })

print(f"Total cards with NPS / Video Otziv data: {len(nps_cards)}")
print(f"Cards breakdown by board:")
boards = {}
for c in nps_cards:
    b = c["board"] or "unknown"
    boards[b] = boards.get(b, 0) + 1
for b, count in boards.items():
    print(f"  - {b}: {count} cards")

with_calls = [c for c in nps_cards if c["recordings_count"] > 0]
print(f"\nOf these {len(nps_cards)} NPS cards, {len(with_calls)} have actual audio recordings!")

print("\n--- DETAILED INSPECTION OF CARDS WITH ACTUAL CALL RECORDINGS ---")
for c in with_calls[:15]:
    cno = c["card_no"]
    name = c["name"]
    print(f"\nCard #{cno} - {name} ({c['recordings_count']} calls):")
    for note in c["nps_notes"]:
        print("  [NPS Qayd]:", note.replace("\n", " | ")[:160])

with open("data/utc_nps_cards.json", "w", encoding="utf-8") as f:
    json.dump(nps_cards, f, ensure_ascii=False, indent=2)
