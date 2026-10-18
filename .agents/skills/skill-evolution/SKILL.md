---
name: skill-evolution
description: Protocol for creating, updating, and evolving operational agent skills in Oisha-OS. Use whenever a repeatable workflow (Telegram scraping, CRM enrichment, tax reporting, marketing automation, or error recovery) is discovered, verified, or improved.
---

# Skill Evolution Protocol (Oisha-OS)

> **Asosiy qoida (`AGENTS.md` 9-qoida):** Barcha AI agentlar (Antigravity, Codex, Claude) takrorlanadigan operatsiyalar uchun `.agents/skills/` katalogidagi mos skillni o'qiydi. Yangi tasdiqlangan workflow paydo bo'lsa yoki eski skillda kamchilik aniqlansa, ish yakunida skill avtonom tarzda yangilanadi.

---

## 1. Qachon yangi skill yaratiladi yoki yangilanadi?

1. **Yangi operatsion jarayon:** Tizimda 2 martadan ko'p takrorlanadigan yangi vazifa (masalan, yangi Telegram guruhidan lidlarni tortish, yangi soliq shakli, yangi CRM statusi bilan ishlash) paydo bo'lsa.
2. **Xatolikdan saboq olish (Hermes Learning Loop):** Ish davomida kutilmagan API xatosi, rate limit yoki format o'zgarishi bartaraf etilsa, uning yechimi darhol tegishli skillga kiritiladi.
3. **Optimallashtirish:** Jarayonni token yoki vaqt jihatidan 50%+ tezlashtiruvchi yangi skript yoki usul tasdiqlansa.

---

## 2. Skill Tuzilishi va Standartlari

Har bir skill quyidagi qat'iy formatda bo'lishi shart:

```markdown
---
name: <kebab-case-nom>
description: <Agent qachon va nima maqsadda ushbu skillni ishga tushirishi kerakligini aniq ko'rsatuvchi 1-2 jumlali tavsif>
---

# <Skill Nomi>

## 1. Maqsad va Qo'llanilish doirasi
- Qaysi vazifalar uchun mo'ljallangan?
- Qachon ishlatilmaydi?

## 2. Kiruvchi ma'lumotlar va Talablar
- Kerakli fayllar, muhit o'zgaruvchilari (sirlarni yozmasdan!) va huquqlar.

## 3. Qadamma-qadam Amallar (Step-by-step Execution)
- Aniq buyruqlar va skriptlar (masalan: `python scripts/...`).

## 4. Xatolar va Bartaraf etish (Troubleshooting & Edge Cases)
- Keng tarqalgan xatolar va ularning yechimlari.

## 5. Tekshiruv va Dalil (Verification Gate)
- Ish muvaffaqiyatli yakunlanganini qanday isbotlash mumkin?
```

---

## 3. Taqiqlangan Amallar (Guardrails)

- ❌ **Soxta ma'lumot kiritish taqiqlanadi (`AGENTS.md` 10-qoida):** Tekshirilmagan, ishlamaydigan yoki xayoliy API endpointlarni skillga yozmang.
- ❌ **Sirlarni kiritish taqiqlanadi:** API kalitlar, Telegram bot tokenlari, sessiya stringlari hech qachon skill ichida saqlanmaydi (faqat `.env` yoki settings orqali murojaat qilinadi).
- ❌ **Eskirgan usullarni qoldirish:** Yangi yechim kiritilganda, eskirgan va xato keltirib chiqaradigan instruksiyalar o'chirib tashlanadi.

---

## 4. Avtonom Generator bilan integratsiya

Oisha-OS da skill yaratishni avtomatlashtirish uchun `scripts/harness/skill_generator.py` yordamchi skriptidan foydalanish mumkin:

```powershell
python scripts/harness/skill_generator.py --task "AmoCRM Dublikat Tozalash" --output ".agents/skills/amocrm-dedup"
```
