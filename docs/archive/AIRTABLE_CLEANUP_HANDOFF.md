# Airtable "Jon Branding" base tozalash — HANDOFF

Base ID: `app8xoyx1XCumYFXV`
Sana: 2026-09-10/11
Sabab: sessiya limitlari tufayli bo'linib ketgan, boshqa AI agent davom ettirsin

## TAYYOR PROMPT (boshqa AI agentga to'g'ridan-to'g'ri berish uchun)

```
Airtable "Jon Branding" moliya bazasini (app8xoyx1XCumYFXV) tozalash ishini
davom ettir. To'liq kontekst shu faylda: AIRTABLE_CLEANUP_HANDOFF.md
(repo root). O'qib chiq, "QOLGAN ISH" bo'limidagi band 1 dan boshla.

Muhim qoidalar:
- Brauzer orqali ishla (Claude in Chrome / mcp__claude-in-chrome), Airtable
  login bor.
- Har field/jadval o'chirishdan oldin Airtable'ning "Delete field/table"
  dialogidagi "N dependencies" ogohlantirishini albatta ko'r. Dependency
  bo'lsa — owner'ga ayt, mendan qaror so'ra, o'zing hal qilma.
- "MUHIM — TEGMASLIK KERAK" bo'limidagi field/automation/form/jadvallarga
  ASLO tegmang — ular ishlaydigan tizim (P&L, Cashflow, avtomatlashtirish).
- ARXIV jadvallarni (band 3) O'CHIRMA — owner hali tasdiqlamagan, avval
  record-parity tekshirilishi kerak.
- Har ish tugagach yoki to'xtaganda shu faylni yangilab qo'y (BAJARILGAN /
  QOLGAN ISH bo'limlari) — keyingi agent davom ettirsin.
```

## Bu sessiyada aniqlangan qo'shimcha topilma (2026-09-11)

**Band 1 (orphan `Moliya so'rovlari` fieldlar) — tugadi:**
- `Moliya kategoriyalari` jadvalida bu field allaqachon avtomatik o'chgan
  edi (jadval o'chirilganda link field ham to'liq ketgan) — tekshirib
  ko'rildi, hech narsa qilish shart emas.
- `Hisoblar` jadvalida field nomi `[O'CHIRISH] Moliya so'rovlari` edi
  (avvalgi sessiyada shunday belgilangan, description: "0 ta qiymatli
  orphan field. Dependency tugagach o'chiriladi.") — 0 dependency bilan
  o'chirildi. ✅ TASDIQLANDI, band 1 to'liq bajarildi.

**Band 2 (NAF Stroy sanasi) — qisman javob topildi, lekin ziddiyat bor:**
- Airtable'da "NAF Stroy - Patent" record: Mijoz "Boybori Castle
  Surhondaryo TN Gr", Loyiha bosqichi = **Brief (Kelishuv)**,
  Start sana = **July 2, 2026**, END sana = **bo'sh**.
- Telegramdan ("Loyihalar | Jon.Branding" guruhi, chat_id
  -1003114662117) tekshirildi — "Boybori" bilan bog'liq xabarlar
  2026-03-04 dan (Naming taqdimoti) va 2026-03/04/05/06 oylarida davom
  etyapti — bu Airtable'dagi "July 2, 2026" start sanasidan MUAMMOLI
  ERTAROQ. Aniq matnli xabarlar ko'pi rasm/media (`[empty]`), aniq NAF
  Stroy Patent yakunlanish sanasi topilmadi.
- **ZIDDIYAT:** Telegram faoliyati Airtable start sanasidan oldinroq
  ko'rinadi va loyiha bosqichi "Brief" (endigina boshlanяпti) real
  faollik bilan mos kelmayapti — Airtable statusi eskirgan/yangilanmagan
  bo'lishi mumkin.
- **QOLGAN ISH:** Owner'dan aniqlashtirish so'ralди — loyiha hozir qaysi
  real holatda (tugaganmi, davom etyaptimi)? Javob kelganda Airtable'dagi
  `Loyiha bosqichi` va `END sana` ni to'g'irlash kerak. Owner javobini
  kutish kerak, keyingi agent davom ettirsin.

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

## QOLGAN ISH

### 1. ✅ BAJARILDI — Orphan text fieldlar (yuqoridagi "Bu sessiyada aniqlangan" bo'limiga qarang)

### 2. ⏳ Owner javobini kutish kerak — NAF Stroy loyihasi holati
Airtable/Telegram ziddiyati tafsilotlari yuqorida. Owner javob berganda:
Loyihalar jadvalida "NAF Stroy - Patent" record → `Loyiha bosqichi` va
`END sana` ni real holatga moslashtirish.

### 3. ARXIV jadvallar — QAROR KERAK (owner savol berdi):
"ARXIV — Kirim (Finance V1)" (20 field), "ARXIV — Chiqim (Finance V1)" (15 field) — hidden.
Owner xavotiri: mijoz-loyiha bog'lanishi, kelishilgan/to'langan/qoldiq.
TEKSHIRISH (HALI TASDIQLANMAGAN — bu bosqich bajarilmagan): ARXIV'da nechta
record bor va ular Tranzaksiyalarga to'liq ko'chirilganmi — canlı
record-parity solishtiruv qilinmagan. Loyihalar jadvalidagi field
izohida (Airtable field description) "arxiv — bilan boshlanadigan
maydonlar hisob-kitobda ishlatilmaydi, eski yozuvlar Tranzaksiyalarga
ko'chirilgan" deyilgan — bu Airtable ichidagi field-level izoh, CLAUDE.md
matnida so'zma-so'z tasdiq YO'Q va mustaqil tekshirilmagan.
Yangi hisob Loyihalar'da: `Jami to'langan (UZS)` (Tranzaksiyalardan rollup), `Qoldiq to'lov uzs` — bular ISHLAYDI, tegmang.
O'chirsangiz `arxiv —` rollup/link fieldlar buziladi (lekin baribir ishlatilmaydi — bu izohga asoslanadi, tasdiqlanmagan).
QOIDA: ARXIV jadvallarni yoki `arxiv —`/`[ESKI]` fieldlarni O'CHIRMANG toki
ARXIV record'lari va Tranzaksiyalar'dagi mos yozuvlar qo'lda yoki
skript bilan solishtirilib, to'liq migratsiya tasdiqlanmaguncha. Shundan
keyingina owner tasdig'i bilan o'chirish.

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
