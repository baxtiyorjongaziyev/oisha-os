import json
import os
import sys
import io
from datetime import datetime

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

report_path = 'data/amocrm_transferred_sotuv_leads_report.json'
if not os.path.exists(report_path):
    print("Report file not ready yet.")
    sys.exit(1)

results = json.load(open(report_path, 'r', encoding='utf-8'))
print(f"Loaded {len(results)} transferred leads.")

# Group by target stage
stages_grouped = {}
for r in results:
    st_name = r['target_stage_name']
    if st_name not in stages_grouped:
        stages_grouped[st_name] = []
    stages_grouped[st_name].append(r)

md_content = """---
title: "Target Leads — amoCRM Sotuv Bo'limiga O'tkazilgan Lidlar va Belgilangan Vazifalar"
type: lead-migration-report
tags: [jonbranding, amocrm, target-leads, sales-pipeline, task-assignment]
transferred_date: 2026-10-19
target_pipeline: "Sotuv Bo'limi (ID: 11162698)"
responsible_user: "Sotuv bo'limi (ID: 13021974)"
total_leads_moved: {total_count}
---

# 🚀 Target Leads — amoCRM 'Sotuv Bo'limi' Voronkasiga O'tkazilgan Lidlar

> **Bajarilgan Operatsiya Xulosasi:** 
> UTC Outsource CRM va Meta Target kampaniyalaridan tushgan, ammo ilgari **"UTC" arxiv voronkasida (`11322658`, status 143)** unutilib yoki bekor qilingan deb belgilangan **eng issiq va sotuvga yaqin {total_count} ta lid** aniqlandi. 
> Barcha lidlar amoCRM da rasmiy **"Sotuv Bo'limi" voronkasiga (`11162698`)** ko'chirildi, ularning har biriga **ehtiyojlari (Brend nomi, soha, maqsad) bo'yicha aniq vazifalar (Zadacha)** qo'yildi va mas'ul etib **Sotuv bo'limi (`13021974`)** biriktirildi.

---

## 📊 1. Voronkalar va Bosqichlar Taqsimoti

| Bosqich Nomi | amoCRM Status ID | Lidlar Soni | Maqsad va Ko'rsatma |
|---|---|---|---|
| **Kelishuv / Yopish** | `88871066` | {count_closing} ta | **SHOSHILINCH YOPISH:** Mijoz sotuvga tayyor ('Sell' statusi), to'lov yoki shartnoma kutilmoqda. |
| **Kvalifikatsiya** | `87609522` | {count_qual} ta | **EHTIYOJ & TAKLIF:** Mijoz Meta formani to'ldirgan (Patent/Brending), portfolio va taklif yuborish. |
| **Qayta aloqa** | `87609518` | {count_followup} ta | **QAYTA BOG'LANISH:** Mijoz qayta qo'ng'iroq qilishni so'ragan yoki targetdan yangi qiziqish bildirgan. |

---

## 📋 2. O'tkazilgan Barcha Lidlar va Belgilangan Vazifalar Ro'yxati

| # | amoCRM Havolasi | Mijoz Ismi & Tel | UTC Karta | Brend & Soha | Bosqich | Belgilangan Vazifa (Zadacha) | Task ID |
|---|---|---|---|---|---|---|---|
""".format(
    total_count=len(results),
    count_closing=len(stages_grouped.get('Kelishuv / Yopish', [])),
    count_qual=len(stages_grouped.get('Kvalifikatsiya', [])),
    count_followup=len(stages_grouped.get('Qayta aloqa', []))
)

for i, r in enumerate(results, 1):
    lid = r['lead_id']
    name = r['name']
    phone = r['phone']
    c_no = r['card_no']
    utc_st = r['utc_status']
    brand = r.get('brand') or '—'
    ind = r.get('industry') or '—'
    stage = r['target_stage_name']
    task_id = r.get('task_id') or 'Mavjud'
    task_txt = r['task_text'].replace('|', '–')
    
    lead_link = f"[{name} (#{lid})](https://jonbranding.amocrm.ru/leads/detail/{lid})"
    brand_info = f"**{brand}** ({ind})" if brand != '—' else ind
    
    md_content += f"| {i} | {lead_link} | `+{phone}` | #{c_no} (`{utc_st}`) | {brand_info} | `{stage}` | {task_txt} | `{task_id}` |\n"

md_content += """
---

## 🎯 3. Sotuv Menejerlari Uchun Keyingi Qadamlar (SOP)

1. **Kelishuv / Yopish bosqichidagi mijozlar (Жасур, Mirzohidjon):**
   - Zudlik bilan mijoz bilan bog'lanib, shartnoma/schet-faktura ma'lumotlarini olish va to'lovni qabul qilish.
   - Mirzohidjon uchun ekspertiza to'lovi kelishilgan, karta raqami yoki hisob raqamni Telegramdan qayta eslatish.
2. **Kvalifikatsiya bosqichidagi mijozlar (Abdumalik, Olimjon, Davron, Begzod, Nafisa va b.):**
   - Har bir kartochkadagi ichki **"TARGET LEADS KVALIFIKATSIYA DOSYESI"** eslatmasini o'qib chiqish.
   - Mijozning brend nomi (masalan, *Sabo*, *Shaden*, *Ummon*, *Family cake*) bo'yicha patent tozaligi va logotip ehtiyojini muhokama qilish.
   - Portfoliodan o'xshash sohadagi keyslarni taqdim etib, zoom yoki ofis uchrashuviga taklif qilish.
3. **Qayta aloqa bosqichidagi mijozlar (Sofiya, Nazira, Asror, Hikmatjon va b.):**
   - Operator bilan gaplashib ulgurmagan yoki qayta qo'ng'iroq so'ragan tadbirkorlar.
   - Hurmat bilan qayta aloqaga chiqib, Jon Branding xizmatlari bo'yicha konsultatsiya berish.
"""

obsidian_target = r"C:\Users\baxti\OneDrive\Документы\Obsidian Vault\20-CLIENTS\Target_Leads_Sotuvga_Otkazilgan_Lidlar.md"
with open(obsidian_target, 'w', encoding='utf-8') as f_obs:
    f_obs.write(md_content)

print(f"Wrote Obsidian report to: {obsidian_target}")
