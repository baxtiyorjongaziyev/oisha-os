# Airtable "Jon Branding" base tozalash — HANDOFF

Base ID: `app8xoyx1XCumYFXV`
Sana: 2026-09-10
Sabab: 5 soatlik AI limit tugadi (15:10 UTC tiklanadi)

## Kontekst
Owner: Baxtiyorjon. Jamoa YO'Q — faqat 1 moliyachi + 1 biznes assistant.
Jamoa inbox / so'rov tizimlari keraksiz.
Brauzer (Claude in Chrome) orqali ishlanadi — Airtable'ga login bor (Browser 1).
mcp__airtable MCP schema bug bor. mcp__2f5712e3... MCP ishlaydi (list_tables_for_base — output katta, python bilan parse qiling).

## BAJARILGAN

### Jadvallar o'chirildi (trash'da, 7 kun tiklanadi):
- Tuzatish so'rovlari
- Moliya so'rovlari
- Moliya nazorati

### Fieldlar o'chirildi:
- Tranzaksiyalar: [ESKI] Oylik P&L (V1 Link), [ESKI] Tuzatish so'rovlari, Tuzatish so'rovlari, [ESKI] Moliya so'rovlari, Yuborgan xodim
- Loyihalar: Tuzatish so'rovlari, Moliya so'rovlari (ikkalasi orphan text)
- Jamoa: [ESKI] Moliya so'rovlari

### Boshqa:
- Tranzaksiyalar'ga `Oy nomi` formula field qo'shildi:
  `DATETIME_FORMAT({Sana},'YYYY-MM')&' — '&SWITCH(MONTH({Sana}),1,'Yanvar',2,'Fevral',3,'Mart',4,'Aprel',5,'May',6,'Iyun',7,'Iyul',8,'Avgust',9,'Sentabr',10,'Oktabr',11,'Noyabr',12,'Dekabr')&' '&DATETIME_FORMAT({Sana},'YYYY')`
  Natija: "2026-09 — Sentabr 2026"
- Tranzaksiyalar "Oy bo'yicha Kirim" + "Oy bo'yicha Chiqim" view'lar:
  guruh = `Oy nomi` (Z→A, hozirgi oy tepada), eski `[ESKI] Oylik P&L` guruh olib tashlandi, `Turi` guruh ham (ortiqcha — view allaqachon filtrlangan)
- Cashflow — oylik jadval: 2 bo'sh dublikat qator o'chirildi (5→3). Qolган 3: (2026-09 Naqd USD), (2026-08 P2P karta), (2026-09 P2P karta)

## QOLGAN ISH (limit tiklangach)

### 1. Orphan text fieldlar (bo'sh, xavfsiz — 0 dependency kutiladi):
- Moliya kategoriyalari jadval → `Moliya so'rovlari` field (singleLineText)
- Hisoblar jadval → `Moliya so'rovlari` field (singleLineText)
Har biri: field header ▾ → Delete field. "Keraksiz havola" description bilan.

### 2. NAF Stroy loyihasi sanasi (owner so'radi, javob berilmadi):
"naf stroy qachon boshlanib qachon yakunlangan"
Loyihalar jadvalida "NAF Stroy - Patent" record. Start sana / END sana ustunlari.

### 3. ARXIV jadvallar — QAROR KERAK (owner savol berdi):
"ARXIV — Kirim (Finance V1)" (20 field), "ARXIV — Chiqim (Finance V1)" (15 field) — hidden.
Owner xavotiri: mijoz-loyiha bog'lanishi, kelishilgan/to'langan/qoldiq.
TEKSHIRISH: ARXIV'da nechta record + Tranzaksiyalarga to'liq ko'chirilganmi.
CLAUDE.md tasdiqlaydi: "Eski Kirim/Chiqim jadvallaridagi barcha yozuvlar Tranzaksiyalarga ko'chirilgan. arxiv — maydonlar hisob-kitobda ishlatilmaydi."
Yangi hisob Loyihalar'da: `Jami to'langan (UZS)` (Tranzaksiyalardan rollup), `Qoldiq to'lov uzs` — bular ISHLAYDI, tegmang.
O'chirsangiz `arxiv —` rollup/link fieldlar buziladi (lekin baribir ishlatilmaydi).
Owner tasdiqlаса → ARXIV jadvallarni o'chirish, keyin Loyihalar/Mijozlar/Jamoa/KPI'dagi `arxiv —`/`[ESKI]` fieldlar.

### 4. Loyihalar jadval — 68 field (juda shishган). Keraksizlar:
- arxiv — eski Kirim (UZS), arxiv — eski Kirim (USD), arxiv — eski Chiqim (UZS), arxiv — chiqim USD (eski Chiqim) — rollup, ARXIV o'chgach o'chirish
- Kirim link (multipleRecordLinks — ARXIV Kirim'ga)
- F2 Tranzaksiyalar — Loyiha bor Tranzaksiyalar'da, dublikat bo'lishi mumkin — TEKSHIRISH
- Ovchi / Seller / Art Direktor / Bonus — singleLineText (Jamoa'ga link EMAS, faqat matn). QAROR: Jamoa link qilamizmi yoki o'chiramizmi?
- PM Ma'sul (singleCollaborator) VS PM (multipleRecordLinks) — dublikat, bittasi tanlanadi

### 5. Mijozlar jadval:
- [ESKI] To'lovlar (V1) — link (ARXIV Kirim'ga)
- [ESKI] LTV (V1 Kirim) — rollup

### 6. Jamoa jadval:
- [ESKI] Daromad (V1 Chiqim) — rollup
- [ESKI] Bog'langan xarajatlar (V1) — link
- [ESKI] Kirim (V1) — link

### 7. KPI Tracking jadval:
- arxiv — to'langan (eski Kirim) — rollup

## MUHIM — TEGMASLIK KERAK (tizim ishlashi uchun):
- Tranzaksiyalar: Oy (date formula), Kirim UZS, Chiqim UZS, Sof oqim UZS, Oylik P&L (Hisobot) link, Cashflow qatori link, Nazorat holati, Tekshiruv izohi
  (Nazorat holati/Tekshiruv izohi — Moliya nazorati JADVALIGA bog'liq EMAS, Tranzaksiyalar validatsiyasi, "Nazorat — FAIL" view ishlatadi)
- Automation "Cashflow qatorini bog'lash" (ON) — Oy (date) field'ni contains bilan ishlatadi
- Automation "Finance — yangi tranzaksiyani Reja qilish" (ON) — form submit
- Form "Jamoa — Kirim va chiqim yuborish" — Tranzaksiyalar'ga to'g'ridan yozadi
- Oylik P&L, Cashflow — oylik, Balans — avtomatik hisobot jadvallar

## Ish uslubi (owner feedback):
- Har o'chirishdan oldin "Show dependencies" yoki Delete dialogdagi "N dependencies" tekshirish
- Dependency bo'lsa — owner'ga ay't, qaror so'ra
- Jadval o'chirish: qaytariladi (trash 7 kun) — owner tasdiqlagan
- Brauzer sekin — browser_batch ishlatish, menu ochilmasa find bilan ref olish
