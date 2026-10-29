import json
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

with open("data/utc_cache/leads_with_recordings.json", "r", encoding="utf-8") as f:
    cache = json.load(f)

default_leads = [item for item in cache if (item.get("lead", {}).get("board") or item.get("board")) == "default"]

nps_results = []

for item in default_leads:
    lead = item.get("lead", {})
    cno = lead.get("cardNo")
    name = lead.get("name")
    phone = lead.get("phone")
    comments = item.get("comments", [])
    recs = item.get("recordings", [])
    
    # Extract metadata from comments
    brand = ""
    services = ""
    projects = ""
    nps_score = ""
    survey_answers = ""
    video_status = "Noma'lum"
    
    for c in comments:
        t = c.get("text", "")
        if "Brend:" in t:
            m = re.search(r"Brend:\s*([^\n|]+)", t)
            if m: brand = m.group(1).strip()
        if "Xizmatlar:" in t:
            m = re.search(r"Xizmatlar:\s*([^\n|]+)", t)
            if m: services = m.group(1).strip()
        if "Loyihalar:" in t:
            m = re.search(r"Loyihalar:\s*([^\n|]+)", t)
            if m: projects = m.group(1).strip()
        if "Video otziv so‘raldi:" in t:
            m = re.search(r"Video otziv so‘raldi:\s*([^\n|]+)", t)
            if m: video_status = f"So'raldi: {m.group(1).strip()}"
        if "Video va’da qildi:" in t:
            m = re.search(r"Video va’da qildi:\s*([^\n|]+)", t)
            if m and m.group(1).strip().lower() in ["ha", "haqiqatdan"]:
                video_status = "Video va'da qildi (Kelishilgan)"
        if "Video olindi:" in t:
            m = re.search(r"Video olindi:\s*([^\n|]+)", t)
            if m and m.group(1).strip().lower() == "ha":
                video_status = "✅ Video olindi!"
        
        # Check manual survey responses (e.g. 1. 10 2. 10...)
        if re.search(r"1\.\s*\d+", t) or "vidio" in t.lower() or "video" in t.lower() or "yoqqan" in t.lower():
            survey_answers += " | " + t.strip().replace("\n", " ")
            if "video tashlaydilar" in t.lower() or "vidio tashlaydilar" in t.lower() or "tashab qo'yaman" in t.lower():
                video_status = "Video va'da qildi (Kutilmoqda)"
            elif "yubora olmas" in t.lower() or "vaqtlari yoq" in t.lower():
                video_status = "Vaqti yo'q (Rad etdi)"
                
    nps_results.append({
        "card_no": cno,
        "client_name": name,
        "phone": phone,
        "brand": brand,
        "services": services,
        "projects": projects,
        "recordings_count": len(recs),
        "video_status": video_status,
        "survey_notes": survey_answers.strip(" |")
    })

print(f"Total default board clients analyzed: {len(nps_results)}")
print(f"\n--- NPS & VIDEO OTZIV SUMMARY TABLE ---")
for r in nps_results:
    cno = r["card_no"] or 0
    name = str(r["client_name"] or "Noma'lum")
    brand = str(r["brand"] or "—")
    vstat = str(r["video_status"] or "Noma'lum")
    snotes = r["survey_notes"][:90] if r["survey_notes"] else "Qo'ng'iroq qaydlari yo'q"
    print(f"Card #{cno:3d} | {name:20s} | Brand: {brand:15s} | Video: {vstat:28s} | {snotes}...")

with open("data/utc_nps_full_analysis.json", "w", encoding="utf-8") as f:
    json.dump(nps_results, f, ensure_ascii=False, indent=2)
