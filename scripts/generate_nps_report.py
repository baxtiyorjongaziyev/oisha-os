"""
Generate Comprehensive NPS and Video Review Report from UTC 'Основная' Board.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

VAULT_DIR = Path(r"C:\Users\baxti\OneDrive\Документы\Obsidian Vault\20-CLIENTS")
REPORT_FILE = VAULT_DIR / "UTC_Основная_Voronka_NPS_va_Video_Otzivlar_Tahlili.md"

with open("data/utc_nps_full_analysis.json", "r", encoding="utf-8") as f:
    nps_data = json.load(f)

lines = [
    "---",
    'title: "UTC Основная Voronka — NPS va Video Otzivlar Tahlili"',
    "type: nps-audit-report",
    "tags: [jonbranding, nps, customer-satisfaction, video-reviews, utc-audit]",
    "total_clients_analyzed: " + str(len(nps_data)),
    "---",
    "",
    "# 🌟 UTC 'Основная' Voronkasi — NPS va Video Otzivlar Tahlili",
    "",
    "> **Muhim Xulosa:** UTC Outsource CRM dagi **\"Основная\" (`default`) voronkasi** — yangi sovuq lidlar emas, balki Jon Branding bilan **ishlari yakunlangan mavjud mijozlar bazasi** bo'lgan! Operatorlar (Orzuman, Dilnoza, Madina) ushbu mijozlarga **\"Sifat nazorati bo'limi\"** nomidan qo'ng'iroq qilib, 6 ta mezon bo'yicha NPS so'rovnomasi o'tkazgan va **Video Otziv (video sharh)** so'ragan.",
    "",
    "---",
    "",
    "## 📋 1. Sifat Nazorati So'rovnoma Standarti (6 ta Savol)",
    "Operatorlar qo'ng'iroqlarda quyidagi 6 ta standart savol bilan suhbatlashgan:",
    "1. **Baho (0-10):** Qilingan ish va xizmat sifatiga necha ball berasiz?",
    "2. **Tavsiya (NPS):** Bizni yaqinlaringiz va boshqa tadbirkorlarga tavsiya qilasizmi?",
    "3. **Nima yoqdi?** Aynan qaysi jihatlarimiz ma'qul keldi (tezlik, dizayn, konseptsiya, muomala)?",
    "4. **Manba:** Bizni kim tavsiya qildi yoki qayerdan topdingiz? *(Ko'pchilik Baxtiyor aka bilan shaxsan tanish)*",
    "5. **Natija:** Kutgan natijangizga erishdingizmi? *(Brend ishlayaptimi, sotuvlar bormi?)*",
    "6. **Kamchiliklar / Takliflar:** Qanday e'tiroz yoki kamchiliklar bo'ldi? *(Narx, aloqa tezligi va h.k.)*",
    "🎯 **Asosiy Maqsad:** Telegram orqali 30-60 soniyalik samimiy **Video Otziv** yuborishlarini kelishish.",
    "",
    "---",
    "",
    "## 📊 2. Mijozlar Bo'yicha NPS va Video Otziv Xulosalari",
    "",
    "| Karta | Mijoz Ismi | Brend / Loyiha | Xizmatlar | Baholar & Fikrlar | Video Otziv Holati |",
    "|---|---|---|---|---|---|"
]

for item in nps_data:
    cno = item.get("card_no") or 0
    name = item.get("client_name") or "Noma'lum"
    brand = item.get("brand") or "—"
    srv = item.get("services") or item.get("projects") or "Branding"
    vstat = item.get("video_status") or "Noma'lum"
    notes = item.get("survey_notes") or "Qayd mavjud emas"
    
    # Format notes cleanly
    clean_notes = notes.replace("Mijoz: " + name, "").replace("Brend: " + brand, "").strip(" |")
    if len(clean_notes) > 120:
        clean_notes = clean_notes[:117] + "..."
    if not clean_notes:
        clean_notes = "Qo'ng'iroq qilinmagan / Olingan ma'lumot yo'q"

    lines.append(f"| #{cno:3d} | **{name}** | {brand} | {srv[:30]} | {clean_notes} | `{vstat}` |")

lines.extend([
    "",
    "---",
    "",
    "## 💡 3. Muhim Insightlar va Tavsiyalar",
    "",
    "### 👍 Ijobiy jihatlar (Mijozlar nimani maqtadi?):",
    "- **Dizayn va kreativlik:** Boyarin, Climart, Evolur, Viton mijozlari qilingan brending va vizual yechimlarni yuqori baholagan (9-10 ball).",
    "- **Tezlik:** Climart control mijoziga ayniqsa loyihaning tez topshirilgani juda ma'qul kelgan.",
    "- **Shaxsiy ishonch:** Mijozlarning 80% dan ortig'i Baxtiyor aka bilan shaxsan tanish yoki tavsiya orqali kelgan.",
    "",
    "### ⚠️ Kamchilik va e'tirozlar (Mijozlar nimadan shikoyat qildi?):",
    "- **Narx darajasi:** Ayrim mijozlar (masalan, Sardor Hoshimov) \"narx qimmatroq\" ekanini aytgan.",
    "- **Muloqot chastotasi:** Odiljon Xamroyev (Enros) loyiha davomida \"tez-tez aloqada bo'lib turish kerak edi, muomala\" deb 5 ball qo'ygan.",
    "- **Video olishdagi qiyinchilik:** Ko'pchilik tadbirkorlar kameraga gapirishdan tortinishadi yoki \"vaqtim yo'q\" deb paysalga solishadi. Ularga tayyor 3 ta savol va namuna video yuborilsa, olish ehtimoli keskin oshadi.",
    "",
    "### 🎬 Video Otziv Olish Bo'yicha Keyingi Qadam:",
    "1. **Baxtiyorjon Nabiyev (Boyarin):** Video berishga rozi bo'lgan (\"bo'shab tashlab qo'yaman dedilar\"). Telegramdan yumshoq eslatma yuborish kerak.",
    "2. **Farhod Shaymardanov (Viton):** 10 ball bergan, munosabati juda yaxshi. Video so'ralsa, bajonidil beradi.",
    "3. **Azizbek aka (Azel shoes) & Hayot Abbosov (Fadak market):** Telegramda yozishmalar olib borilgan, qayta aloqa qilib videoni yopish mumkin."
])

REPORT_FILE.write_text("\n".join(lines), encoding="utf-8")
print(f"Report generated: {REPORT_FILE}")
