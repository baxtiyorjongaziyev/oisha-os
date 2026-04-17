#!/usr/bin/env python3
"""
Haftalik hisobot namunasi (06.04.2026 - 12.04.2026)
Oisha-OS tomonidan taqdim etiladi
"""

# Ma'lumotlar (AmoCRM dan)
period_start = "06.04.2026"
period_end = "12.04.2026"
active_deals = 473
active_value = 217244000
completed_deals = 0
completed_value = 0
lost_deals = 1
lost_value = 0
new_deals = 193
new_companies = 1
new_contacts = 174

# Formatlash funksiyasi
def format_money(amount: int) -> str:
    if amount == 0:
        return "0"
    return f"{amount:,}".replace(",", " ")

# Hisobot yaratish
report = []

# Sarlavha
report.append(f"📊 *HAFTALIK HISOBOT*")
report.append(f"📅 *Davri: {period_start} - {period_end}*\n")

# Aktiv bitimlar
report.append(f"💼 *AKTIV BITIMLAR (davr oxirida):*")
report.append(f"• Jami: *{active_deals} ta*")
report.append(f"• Qiymati: *{format_money(active_value)} soʻm*\n")

# Yopilgan bitimlar
report.append(f"✅ *YOPILGAN BITIMLAR:*")
if completed_deals > 0:
    report.append(f"• Muvaffaqiyatli: *{completed_deals} ta* ({format_money(completed_value)} soʻm)")
else:
    report.append(f"• Muvaffaqiyatli: *0 ta* ⚠️")

if lost_deals > 0:
    report.append(f"• Bekor qilingan: *{lost_deals} ta* ({format_money(lost_value)} soʻm)")
report.append("")

# Yangi yaratilgan
report.append(f"🆕 *YANGI YARATILGAN:*")
report.append(f"• Bitimlar: *{new_deals} ta* 📈")
report.append(f"• Kompaniyalar: *{new_companies} ta* 🏢")
report.append(f"• Kontaktlar: *{new_contacts} ta* 👥\n")

# Tahlili
report.append(f"📈 *OISHA TAHLILI:*")

if new_deals > 100:
    report.append(f"_✅ Ajoyib! Haftada {new_deals} ta yangi bitim - aktiv sotuv jarayoni._")
elif new_deals > 50:
    report.append(f"_🟡 O'rtacha. Yangi bitimlar oqimi yaxshi, lekin yanada kuchaytirish mumkin._")
else:
    report.append(f"_🔴 Diqqat! Yangi leadlar kam. Marketing kanallarini ko'rib chiqish vaqt._")

if completed_deals == 0 and active_deals > 100:
    report.append(f"_⚠️ {active_deals} ta aktiv bitim ichida yopilgan yo'q - menejerlar nazoratini kuchaytiring._")

report.append(f"\n📊 *Davom ettirish uchun @baxtiyorjong_gaziyev nazoratida* 👑")

# Natija
print("\n".join(report))
