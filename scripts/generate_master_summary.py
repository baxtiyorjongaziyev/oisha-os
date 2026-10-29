import json
import glob
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

deal_files = glob.glob('data/utc_analysis/deals/*.json')
deals = []
for f in deal_files:
    try:
        with open(f, 'r', encoding='utf-8') as fp:
            deals.append(json.load(fp))
    except Exception:
        pass

# Sort deals: Priority P1 first, then by duration or cardNo
def sort_key(d):
    strat = d.get('amocrm_strategy', {}) or {}
    prio = str(strat.get('priority', ''))
    score = 0
    if 'P1' in prio or 'Yuqori' in prio:
        score = 100
    elif 'P2' in prio or 'O\'rta' in prio:
        score = 50
    else:
        score = 10
    dur = d.get('total_duration_sec', 0)
    return (-score, -dur)

deals.sort(key=sort_key)

print(f'Total deals analyzed so far: {len(deals)}')

p1_deals = [d for d in deals if 'P1' in str((d.get('amocrm_strategy') or {}).get('priority', '')) or 'Yuqori' in str((d.get('amocrm_strategy') or {}).get('priority', ''))]
p2_deals = [d for d in deals if d not in p1_deals and ('P2' in str((d.get('amocrm_strategy') or {}).get('priority', '')) or 'O\'rta' in str((d.get('amocrm_strategy') or {}).get('priority', '')))]
other_deals = [d for d in deals if d not in p1_deals and d not in p2_deals]

print(f'P1 Deals: {len(p1_deals)}')
print(f'P2 Deals: {len(p2_deals)}')
print(f'Other Deals: {len(other_deals)}')

# Generate markdown table and detailed cards
lines = []
lines.append("# 📞 UTC CRM (Contact Pulse) — Sdelkalar Tahlili va AmoCRM Migratsiya Xaritasi")
lines.append("\n> **Manba:** `https://sales.kontaktmarkazi.com/admin/kanban` (Uztelecom Outsource Call-Center)")
lines.append(f"> **Tahlil qilingan sdelkalar soni:** {len(deals)} ta")
lines.append("> **Maqsad:** Har bir sdelkani chuqur o'rganib, Jon Branding ichki AmoCRM menejerlari (Closerlar) uchun tayyor taktik xarita yaratish.\n")

lines.append("## 🏆 1. Qisqacha Xulosa va Statistika")
lines.append("| Ko'rsatkich | Qiymat | Tavsif |")
lines.append("| :--- | :--- | :--- |")
lines.append(f"| **Jami tahlil qilingan sdelkalar** | **{len(deals)} ta** | Barcha audio yozuvlari bilan to'liq STT qilingan |")
lines.append(f"| 🔥 **P1: Yuqori Prioritet (Issiq / Zudlik bilan)** | **{len(p1_deals)} ta** | Byudjeti va aniq ehtiyoji bor, darhol bitim yopish mumkin |")
lines.append(f"| ⚡ **P2: Qayta Aloqa (Iliq / Muzokara)** | **{len(p2_deals)} ta** | Ikkilangan, e'tirozlari hal qilinsa xarid qiladi |")
lines.append(f"| 💤 **P3: Past / Boshqa** | **{len(other_deals)} ta** | Axborot olgan yoki uzoq muddatli mijozlar |")
lines.append("\n---\n")

lines.append("## 🎯 2. P1 — Zudlik Bilan Aloqaga Chiqish Va Yopish Kerak Bo'lgan Sdelkalar (Hot Deals)")
lines.append("| № | Karta | Mijoz | Telefon | UTC Status | Real Status | Byudjet / Ehtiyoj | Tavsiya Qadam (AmoCRM) | Fayl |")
lines.append("| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |")

for i, d in enumerate(p1_deals, 1):
    c_no = d.get('card_no')
    name = d.get('client_name')
    phone = d.get('phone')
    utc_st = d.get('utc_status')
    real_st = d.get('real_status')
    need = (d.get('need_and_context') or '')[:60] + '...'
    strat = d.get('amocrm_strategy') or {}
    stage = strat.get('target_stage', 'Maslahat')
    hook = (strat.get('call_opening_hook') or '')[:40] + '...'
    fn = f"{c_no}_{name}.md"
    lines.append(f"| {i} | `#{c_no}` | **{name}** | `+{phone}` | `{utc_st}` | **{real_st}** | {need} | `{stage}` | [{c_no} hujjati](data/utc_analysis/markdown/{fn}) |")

lines.append("\n---\n")

lines.append("## ⚡ 3. P2 — Qayta Aloqa Va E'tirozlarni Yengish Sdelkalari (Warm Deals)")
lines.append("| № | Karta | Mijoz | Telefon | UTC Status | Real Status | Asosiy E'tiroz | Yopish Taklifi (Pitch) | Fayl |")
lines.append("| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |")

for i, d in enumerate(p2_deals, 1):
    c_no = d.get('card_no')
    name = d.get('client_name')
    phone = d.get('phone')
    utc_st = d.get('utc_status')
    real_st = d.get('real_status')
    objs = '; '.join(d.get('client_objections', []))[:50]
    strat = d.get('amocrm_strategy') or {}
    pitch = (strat.get('closing_pitch') or '')[:50] + '...'
    fn = f"{c_no}_{name}.md"
    lines.append(f"| {i} | `#{c_no}` | **{name}** | `+{phone}` | `{utc_st}` | **{real_st}** | {objs} | {pitch} | [{c_no} hujjati](data/utc_analysis/markdown/{fn}) |")

lines.append("\n---\n")

lines.append("## 🔍 4. Outsource (UTC) Operatorlarining Eng Asosiy 5 Ta Xatosi (Nega Sotuv Bo'lmagan?)")
lines.append("Audio tahlillar shuni ko'rsatdiki, UTC operatorlari quyidagi tizimli xatoliklarga yo'l qo'ygan:")
lines.append("1. **Narxdan qo'rqish va yashirish:** Mijozlar bir necha bor 'Narxi qancha bo'ladi?' deb so'raganida, operatorlar narx aytishdan qochgan yoki 'buni mutaxassis aytadi' deb dialogdan chiqqan.")
lines.append("2. **Boshlang'ich kvalifikatsiya yo'qligi:** Mijoz kim, byudjeti qancha, qaror qabul qiluvchimi — bu savollar berilmasdan, 20-40 daqiqa umumiy mavzularda behuda gaplashilgan.")
lines.append("3. **Jon Branding qiymatini sotmaslik:** Agentlikning tajribasi, avvalgi muvaffaqiyatli keyslari yoki portfoliolari haqida deyarli ma'lumot berilmagan.")
lines.append("4. **Sun'iy ravishda 'Not interested' qilish:** Mijoz 'hali o'ylab ko'raman' yoki 'sherigim bilan maslahatlashaman' degan zahoti operator sdelkani 'Not interested' (Qiziqmadi)ga tashlab yuborgan.")
lines.append("5. **Keyingi aniq qadam (Next Action) belgilanmagan:** Qo'ng'iroq oxirida aniq vaqtga uchrashuv yoki prezentatsiya tayinlanmagan.")

lines.append("\n---\n")
lines.append("## 💼 5. AmoCRM Menejerlari (Closerlar) Uchun Standart Amaliy Qo'llanma (SOP)")
lines.append("Har bir sdelka bo'yicha to'liq fayllar `data/utc_analysis/markdown/` papkasida joylashgan. Ichki menejerlar quyidagi algoritm bilan ishlashi shart:")
lines.append("1. Mijoz kartochkasidagi **'To'liq Qo'ng'iroqlar Transkripti'**ni ko'zdan kechirish.")
lines.append("2. **📞 Kirish so'zlari (Opening Hook)** orqali qo'ng'iroqni boshlash:")
lines.append("   > *'Assalomu alaykum, [Mijoz ismi] aka! Men Jon Branding agentligining bosh mutaxassisi [Ismingiz]man. Call-markazimiz bilan gaplashganingizda siz aytgan brending va patent bo'yicha masalangizni mutaxassislarimiz bilan tahlil qilib chiqdik...'*")
lines.append("3. Mijozning e'tirozini operator xatosi deb emas, balki tabiiy bosqich deb qabul qilib, tayyor **Yopish taklifi (Closing Pitch)**ni berish.")

content = '\n'.join(lines)
with open('data/utc_analysis/UTC_TO_AMOCRM_MASTER_ANALYSIS.md', 'w', encoding='utf-8') as fp:
    fp.write(content)

print('Master summary written to data/utc_analysis/UTC_TO_AMOCRM_MASTER_ANALYSIS.md')
