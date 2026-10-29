---
name: cross-platform-client-sync
description: Cross-platform client profile synchronization and reconciliation across Airtable, amoCRM, Obsidian Second Brain, and Meta CAPI.
---

# Cross-Platform Client Sync & Reconciliation SOP

Ushbu mahorat (skill) Jon Branding Agency va Oisha-OS ekotizimidagi barcha platformalar (**Airtable**, **amoCRM**, **Obsidian Second Brain**, **Meta CAPI**) bo'yicha mijozlar ma'lumotlarini (ism, telefon, LTV summasi, xarid va bitim holatlari) 100% bir xil (identik) holatda ushlab turish va avtomatik boyitish uchun xizmat qiladi.

---

## 🎯 1. Yagona Haqiqat Manbalari (Single Source of Truth)

1. **Moliyaviy Xaridlar va LTV (Kirim):**
   - Asosiy manba: **Airtable** (`app8xoyx1XCumYFXV`) dagi `Mijozlar` (`tblYeFpWhQIMmrWPZ`) va `Loyihalar` (`tblJbUobSlygSwYAI`).
   - Maydonlar: `LTV (real tushum)`, `Jami to'langan (UZS)`, `Telefon raqami`, `Brands`, `Xizmat turi`.
2. **Operatsion Sotuv va Voronka:**
   - Asosiy manba: **amoCRM** (`jonbranding.amocrm.ru`).
   - Voronka: `Sotuv` (`11162698`).
   - Muvaffaqiyatli xarid statusi: `142` (*Успешно реализовано* / Won).
   - Teg: `Airtable LTV`.
3. **Mijozlar Xotirasi va Kontekst:**
   - Asosiy manba: **Obsidian Second Brain** (`20-Areas/`, `20-CLIENTS/`, `10-Projects/`).
4. **Marketing Attributsiya va Reklama Optimizatsiyasi:**
   - Asosiy manba: **Meta CAPI (Conversions API)** — `Jon Branding | Sotuv` Dataset (`3093333297676078`).

---

## 🔄 2. Standart Ish Jarayoni (SOP — 4 Bosqich)

### Bosqich 1: Airtable Mijozlarini Filtrlash va LTV Hisoblash
- Airtable `Mijozlar` jadvalidan `LTV (real tushum) > 0` bo'lgan barcha to'lovchi mijozlar olinadi.
- Agar mijoz kartasida `Telefon raqami` bo'sh bo'lsa, u **Telefonsizlar navbati**ga qo'yiladi.

### Bosqich 2: Ko'p Manbali Telefon Boyitish (Cross-Platform Discovery)
Telefoni yetishmagan mijozlar quyidagi tartibda qidiriladi:
1. **amoCRM qidiruvi:**
   - Mijozning ismi, brendi yoki loyiha nomi bo'yicha `GET /api/v4/contacts?query=...` va `GET /api/v4/leads?query=...`.
   - Topilgan kontaktning telefon raqami (`field_code == "PHONE"`) tekshiriladi.
2. **Obsidian Second Brain qidiruvi:**
   - Vault ichidagi qatnashuvchilar bazalari (`Tez_Natija_*`, `Intensiv_*`, `VIP_Partners_*`) skaner qilinadi.
   - Mijoz ismi bilan bitta qatorda turgan `+998...` formatidagi raqam aniqlanadi.
3. **Airtable Tranzaksiyalar qidiruvi:**
   - Mijozga bog'langan `tblrqxqIzyrvg7XpQ` (Tranzaksiyalar) ichidagi to'lov cheklaridan raqam ajratib olinadi.
4. **Haqiqiylikni tasdiqlash:**
   - Raqam topilsa, Airtable `Mijozlar` jadvalidagi `Telefon raqami` maydoniga yoziladi (`update_records`).

### Bosqich 3: amoCRM ga Won (142) Sinxronizatsiyasi
1. Telefon orqali amoCRM da kontakt qidiriladi (`/api/v4/contacts?query=<oxirgi_9_raqam>`).
2. **Bitim qoidasi:**
   - Agar mijozda mavjud **Won (142)** bitimi bo'lsa: uning summasi (`price`) Airtable LTV ga tenglashtiriladi (nol qoldiqlar yangilanadi).
   - Agar mavjud **ochiq bitimi** (aloqa, muzokara, uchrashuv) bo'lsa: **ochiq bitimga tegilmaydi**! Eski yopilgan xaridlar uchun yangi alohida Won (142) bitim ochiladi.
   - Agar umumiy kontakt bo'lsa, lekin bitimi bo'lmasa: yangi Won (142) bitimi yaratiladi.
   - Agar kontakt umuman topilmasa: `complex` API orqali yangi kontakt va unga biriktirilgan Won (142) bitimi ochiladi.
3. **Audit va metadata:**
   - Voronka: `Sotuv` (`11162698`).
   - Teg: `Airtable LTV`.
   - Sana: `closed_at` va `created_at` loyihaning haqiqiy boshlangan va tugagan sanalariga o'rnatiladi (joriy kunlik statistika buzilmasligi uchun).
   - Izoh (Notes): Airtable ID, telefon raqami va loyihalar bo'yicha to'langan summalarning to'liq ro'yxati biriktiriladi.

### Bosqich 4: Meta CAPI Attributsiyasi
- Shakllangan to'lovlar Meta Conversions API ga `Purchase` hodisasi sifatida yuboriladi:
  - `event_name`: `Purchase`
  - `custom_data`: `{"value": float(ltv), "currency": "UZS"}`
  - `user_data`: SHA-256 xeshlangan E.164 telefon (`ph`) va email (`em`).
  - `event_id`: Deterministik formatda (`airtable-{rec_id}-purchase`).

---

## 🛡️ 3. Oltin Qoidalar va Xavfsizlik

1. **Nol Uydirma (Zero Hallucination):**
   - Agar telefon raqami hech qaysi bazadan topilmasa, o'zingizdan raqam to'qimang. Uni ochiq qoldirib, egasidan so'rang.
2. **Moliyaviy Butunlik:**
   - Barcha yangilanishlarda amoCRM bitim summalari yig'indisi har doim Airtable LTV summasiga teng bo'lishi shart.
3. **Mavjud ochiq bitimlarni o'ldirmaslik:**
   - Faol lidlar (muzokara, uchrashuv) hech qachon avtomatik ravishda Won statusiga tortib yuborilmaydi.
4. **Handoff jurnali:**
   - Barcha sinxronizatsiya partiyalari `docs/agents/handoff-log.md` fayliga aniq sonlar va summalar bilan muhrlanadi.
