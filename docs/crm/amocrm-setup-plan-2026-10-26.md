# amoCRM sozlash rejasi — Jon Branding (jonbranding.amocrm.ru)

Asos: 2026-10-26 jonli audit (API, faqat o'qish). Tarif «Расширенный», sotuvda 4 kishi bitta
akkauntda: Mumtozmaxal, Shahnoza, Rayxon + Baxtiyorjon (asoschi). Asoschi lid navbatiga
kirmaydi — faqat yirik/eskalatsiya sdelkalar. 1 200 lid/oy ÷ 3 menejer = har biriga ~400, kuniga ~18.
«Oydin» tegi (6 sdelka) sotuvchi emas — sdelkalar 3 menejerga qayta taqsimlanadi.
Triggerlar va Salesbotlar API orqali ko'rinmadi — 0-kun ularni qo'lda ro'yxatga olish kerak.

---

## 1. Xulosa

Lidlar oqimi bor (30 kunda 878), lekin nazorat yo'q: 92% ochiq sdelkada keyingi qadam yo'q,
95% da summa yo'q, majburiy maydon 0, menejer 71% sdelkada noma'lum, konversiya ~4%.
Reja: bitta toza voronka + majburiy maydonlar + «Menejer» maydoni + Salesbot saralash +
avto-yopish. Maqsad 8 haftada: konversiya 4% → 8%, «keyingi qadamsiz» sdelka 0 ga yaqin.

### Hozirgi holat (audit raqamlari)

| Ko'rsatkich | Qiymat |
|---|---|
| Jami sdelka / ochiq | 2 590 / 491 |
| 30 kunda yangi | 878 |
| 90 kun: yutildi / yo'qotildi | 70 / 1 623 (~4%) |
| 90 kun tushum, o'rtacha chek | 275,9 mln / ~3,94 mln so'm |
| Ochiq: vazifasiz / muddati o'tgan | 237 / 214 |
| Ochiq: summasiz | 466 |
| Yo'qotish sababi bor | 961 / 1 925 |
| Majburiy maydon | 0 |
| Menejer tegi bor (ochiq) | 141 / 491 |
| «Yangi LEads»da turgan | 223 |
| Voronkalar | 9 (amalda 1 ishlaydi) |
| Sdelka maydonlari | 42 / 200 |

---

## 2. Ijro rejasi (4 hafta)

**Oltin qoida: bosqichlarni O'CHIRMA, faqat NOMINI O'ZGARTIR.** Oisha-OS va Meta Lead Ads
status ID bilan ishlaydi (masalan, «Yangi LEads» = 89067962). O'chirish = lid yo'qotish (#786).

### 1-hafta — Zaxira va asos
- **1-kun:** Eksport: sdelkalar, kontaktlar, kompaniyalar (Сделки → ⋯ → Экспорт). Triggerlar va
  Salesbotlar ro'yxatini skrinshot qilib saqlash (har voronka → Автоматизация).
  Integratsiyalar ro'yxati: amoМаркет → Установленные.
- **2-kun:** «Menejer» maydonini yaratish (3-bo'lim). Teglardan to'ldirish:
  Mumtozmaxal/Shahnoza/Rayxon tegi bor 141 sdelka → maydon. «Oydin» tegli 6 ta va tegsiz 350 tasi
  3 menejerga bo'linadi (~119 tadan, 2 kun muddat). Asoschi faqat o'zi olib borayotganlarini belgilaydi.
- **3-kun:** Yo'qotish sabablari ro'yxati (Настройки → Причины отказа) — 4-bo'lim.
  Yo'qotish sababi majburiy.
- **4-kun:** Voronka bosqichlarini nomlash va yangi 2 bosqich qo'shish (3-bo'lim).
- **5-kun:** «Yangi LEads»dagi 223 ta va muddati o'tgan 214 ta sdelkani tozalash sprinti:
  har biriga — vazifa qo'yish YOKI sabab bilan yopish. Natija: «keyingi qadamsiz» = 0.

### 2-hafta — Majburiy maydonlar va voronkalar
- **6-kun:** Majburiy maydonlar matritsasini yoqish (4-bo'lim).
- **7-kun:** Arxiv voronkalar: «[ARXIV] 2. CLOSER», «[ARXIV] Target LEADs», «UTC» —
  ochiq sdelka bormi tekshirish → asosiyga ko'chirish → Неразобранное o'chirish →
  voronkani arxivlash. «Target LEADs»ga lid tushayotgan integratsiya bo'lsa — avval uni qayta yo'naltirish.
- **8-kun:** HR voronkasini (Vacancy) alohida joyga ko'chirish masalasi: Airtable yoki
  alohida bepul vosita. Hozircha 1 ochiq sdelka — shoshilinch emas, lekin limitdan joy yeydi.
- **9-kun:** Teg taksonomiyasi (8-bo'lim) — eski teglarni guruhlash.
- **10-kun:** Telefon formati +998XXXXXXXXX (8-bo'lim), dublikatlarni birlashtirish.

### 3-hafta — Avtomatlashtirish
- **11–12-kun:** Triggerlar 1–14 (5-bo'lim).
- **13–14-kun:** Salesbot kvalifikatsiyasi (6-bo'lim): avval Telegram, test, keyin Instagram.
- **15-kun:** Hujjat shablonlari: shartnoma, hisob-faktura (7-bo'lim).

### 4-hafta — Nazorat va integratsiya
- **16-kun:** Saqlangan filtrlar har menejerga (9-bo'lim).
- **17-kun:** Webhook → Oisha/Make → Airtable va Sheets KPI (10-bo'lim).
- **18-kun:** Oisha bilan to'qnashuv jadvali: qaysi avtomatika qayerda (10-bo'lim).
- **19-kun:** Qabul testlari (12-bo'lim).
- **20-kun:** Menejerlarga 1 soatlik o'quv + qoidalar varag'i.

---

## 3. Voronka — «Sotuv Bo'limi» (id 11162698)

| # | Hozirgi nom (id) | Yangi nom | Maqsad | Chiqish mezoni | Max muddat |
|---|---|---|---|---|---|
| 0 | Неразобранное | — | Kirish | Qabul qilindi | 15 daq |
| 1 | Yangi LEads (89067962) | **1. Yangi lid** | Birinchi aloqa | Gaplashildi | 1 kun |
| 2 | Kvalifikatsiya (87609522) | **2. Kvalifikatsiya** | Ehtiyoj, budjet, qaror qiluvchi | Maydonlar to'ldi | 3 kun |
| 3 | Qayta aloqa (87609518) | **3. Keyinroq (sana bor)** | Hozir emas, sanasi aniq | Sana keldi | 30 kun |
| 4 | Uchrashuv (87609526) | **4. Uchrashuv belgilandi** | Uchrashuv sanasi bor | Uchrashuv bo'ldi | 7 kun |
| 5 | Uchrashuvga keldi (89380154) | **5. Brif olindi** | Brif, Drive papka | Brif to'liq | 3 kun |
| 6 | — yangi | **6. KP yuborildi** | Taklif summasi bilan | Mijoz javob berdi | 5 kun |
| 7 | Kelishuv / Yopish (88871066) | **7. Shartnoma** | Shartnoma yuborildi | Imzolandi | 5 kun |
| 8 | — yangi | **8. Avans kutilmoqda** | Hisob-faktura chiqdi | Avans tushdi | 5 kun |
| ✓ | Sotuv bo'ldi (142) | **Avans to'landi** | → Farmer voronkasiga | — | — |
| ✗ | Yopildi / Bekor qilindi (143) | o'zgarmaydi | Sabab majburiy | — | — |

«Keyinroq» bosqichi tartib bo'yicha 2 va 4 orasida turadi — voronkani pastga emas, chetga «parkovka» qiladi.

**Spam / «faqat narx» lidlar:** alohida voronka KERAK EMAS. Salesbot javob olmasa → 72 soatda
avto-yopish «Javob bermadi» sababi bilan (5-bo'lim, trigger 8).

**Bosqich o'zgartirish qoidasi:**
- O'zgartirish huquqi — faqat 1 kishi (asoschi). Menejerlar voronka sozlamasiga tegmaydi
  (bitta akkaunt bo'lgani uchun texnik cheklab bo'lmaydi → yozma qoida).
- O'chirishdan oldin checklist: (1) bosqichda 0 sdelka, (2) Oisha-OS kodida status ID qidirildi,
  (3) Meta Lead Ads / sayt forma yo'nalishi tekshirildi, (4) bosqichdagi triggerlar ko'chirildi.

---

## 4. Maydonlar matritsasi

### Yangi maydonlar (+5)

| Maydon | Turi | Qiymatlar |
|---|---|---|
| Menejer | Список | Mumtozmaxal, Shahnoza, Rayxon, Baxtiyorjon (asoschi) |
| KP summasi | Число | so'm |
| Shartnoma raqami | Текст | JB-2026-001 formati |
| Shartnoma sanasi | Дата | — |
| Yo'qotish izohi | Текст | erkin matn |

Mavjud maydonlardan foydalaniladi: Lead manbasi, Xizmat, Qaror qiluvchi, Narxga moslik,
Boshlash vaqti, Keyingi qadam, Qayta aloqa sanasi, Brend / Biznes nomi, Google Drive papka,
Avans summasi, Qoldiq to'lov sanasi. Budjet uchun standart «Бюджет» (price) maydoni.

**O'chirish nomzodlari** (bo'sh bo'lsa): openstat_service, openstat_campaign, openstat_ad,
openstat_source, roistat, yclid, _ym_counter — 7 ta. *(Avval to'ldirilganini tekshirish.)*

Jami: 42 + 5 − 7 = **40 / 200**.

### Majburiy maydonlar (Настройки полей → maydon → «Обязательное на этапе»)

| Maydon | 2. Kval | 3. Keyinroq | 4. Uchr. | 5. Brif | 6. KP | 7. Shartn. | 8. Avans |
|---|---|---|---|---|---|---|---|
| Menejer | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Lead manbasi | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Xizmat | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Qaror qiluvchi | ✅ | | ✅ | ✅ | ✅ | ✅ | ✅ |
| Qayta aloqa sanasi | | ✅ | | | | | |
| Uchrashuv formati | | | ✅ | | | | |
| Brend / Biznes nomi | | | | ✅ | ✅ | ✅ | ✅ |
| Бюджет (price) | | | | ✅ | ✅ | ✅ | ✅ |
| Google Drive papka | | | | ✅ | ✅ | ✅ | ✅ |
| KP summasi | | | | | ✅ | ✅ | ✅ |
| Shartnoma raqami/sanasi | | | | | | ✅ | ✅ |
| Avans summasi | | | | | | | ✅ |

### Yo'qotish sabablari (majburiy)
Javob bermadi · Spam / adashgan · Narx qimmat · Budjet yo'q · Raqobatchini tanladi ·
Muddat to'g'ri kelmadi · Xizmat bizda yo'q · Keyinga qoldirdi · Dublikat · Boshqa (izoh majburiy).

---

## 5. Triggerlar (jami / 100)

| # | Bosqich | Hodisa | Amal |
|---|---|---|---|
| 1 | 1. Yangi lid | Kirdi | Vazifa «Qo'ng'iroq/yozish», muddat 5 daq, mas'ul — Menejer maydoni |
| 2 | 1. Yangi lid | 15 daq ichida bosqich o'zgarmadi | Asoschiga xabar (Oisha speed-to-lead zaxirasi) |
| 3 | 1. Yangi lid | Kirdi, manba Telegram/Instagram | Salesbot «Kvalifikatsiya» ishga tushadi |
| 4 | 2. Kvalifikatsiya | Kirdi | Vazifa «Ehtiyoj aniqlash», 1 kun |
| 5 | 2. Kvalifikatsiya | 3 kun turdi | Vazifa + teg `eskalatsiya` |
| 6 | 3. Keyinroq | «Qayta aloqa sanasi» keldi | Vazifa «Qayta aloqa» shu kunga |
| 7 | 3. Keyinroq | 30 kun turdi | → 143, sabab «Keyinga qoldirdi» |
| 8 | 1. Yangi lid | 72 soat harakatsiz | → 143, sabab «Javob bermadi» |
| 9 | 4. Uchrashuv | Kirdi | Vazifa «Uchrashuv» uchrashuv sanasiga + mijozga eslatma (SMS/messenjer) 1 kun oldin |
| 10 | 5. Brif | Kirdi | Vazifa «KP tayyorlash», 2 kun |
| 11 | 6. KP | 3 kun javobsiz | Vazifa «KP bo'yicha qo'ng'iroq» |
| 12 | 7. Shartnoma | Kirdi | Hujjat yaratish: shartnoma shabloni |
| 13 | 8. Avans | Kirdi | Hujjat yaratish: hisob-faktura + vazifa «Avansni tekshirish», 3 kun |
| 14 | ✓ Avans to'landi | Kirdi | Webhook → Oisha/Make → Airtable loyiha; sdelka nusxasi Farmer voronkasiga |
| 15 | Har qanday ochiq bosqich | 14 kun harakatsiz | Asoschiga xabar + teg `osilgan` |

Jami: **15 / 100**. Zaxira: 85.

**Vazifa qoidasi (bitta ochiq vazifa):** bosqichga kirishda vazifani faqat trigger yaratadi
(1, 4, 9, 10, 13). Bosqich o'zgarganda oldingi bosqich vazifasi yakunlanadi — qo'lda
o'tkazishda menejer, Salesbot o'tkazganda bot (6-bo'lim, 9.3-qadam). Salesbot hech qachon
o'zi vazifa yaratmaydi.
*Tekshirish kerak:* 2 va 15-triggerdagi «N vaqt bosqich o'zgarmadi» sharti «Расширенный»da
Salesbot orqali qilinadi (Digital Pipeline'siz triggerlar) — interfeysda tasdiqlash.

---

## 6. Salesbot — kvalifikatsiya (Telegram + Instagram)

1. **Salom:** «Assalomu alaykum! Jon Branding'ga xush kelibsiz. Sizga to'g'ri yechim tanlash
   uchun 4 ta qisqa savol beraman.» / RU: «Здравствуйте! …»
2. **Til tanlash:** [O'zbekcha] [Русский]
3. **Xizmat** (tugmalar → «Xizmat»): Logo/brending · Qadoq · Nomlash · Marketing/SMM · Boshqa
4. **Budjet** (→ «Narxga moslik»): 5 mln gacha · 5–15 mln · 15–40 mln · 40 mln+
5. **Muddat** (→ «Boshlash vaqti»): Shu oy · 1–3 oy · Hali aniq emas
6. **Brend / biznes nomi** (erkin matn)
7. **Qaror qiluvchi** (→ «Qaror qiluvchi»): [Men o'zim] [Hamkor/rahbar bilan] [Boshqa odam]
8. **Telefon:** +998 bilan 12 raqam tekshiruvi; noto'g'ri bo'lsa 1 marta qayta so'rash
9. **Yakun** (tartib muhim — majburiy maydonlar bosqich o'tishidan OLDIN to'ladi):
   1. «Lead manbasi» = Telegram / Instagram.
   2. «Menejer» bo'sh bo'lsa navbat bo'yicha (round-robin: Mumtozmaxal → Shahnoza → Rayxon);
      budjet «40 mln+» → Baxtiyorjon.
   3. Trigger 1 dagi «Qo'ng'iroq/yozish» vazifasini **yakunlash** (natija: «Bot kvalifikatsiya qildi»).
   4. Bosqich → 2. Kvalifikatsiya (vazifani trigger 4 yaratadi — bot o'zi vazifa yaratmaydi).
   5. Mijozga: «Rahmat! Menejerimiz 15 daqiqa ichida bog'lanadi.»
10. **Javob bermasa:** 24 soatda 1 eslatma → 72 soatda trigger 8 yopadi.

**Saralash qoidasi:** budjet «5 mln gacha» + muddat «Hali aniq emas» → teg `sifat:past`,
vazifa muddati 1 kun (tezkor emas). Qolganlar — 15 daqiqa.

**Token:** amoCRM tokenni qaysi amal uchun yechishi (bot xabari, SMS) — *tekshirish kerak*
(Настройки → Тарифы → Токены). Hisob: 1 200 lid × ~8 bot xabari = ~9 600 xabar/oy. Agar 1 xabar = 1
token bo'lsa — 10 000 limitning chegarasida. Shuning uchun 1-hafta testida real sarfni o'lchash.

---

## 7. Hujjat shablonlari (Настройки → Шаблоны документов)

| O'zgaruvchi | Manba |
|---|---|
| `{{lead.name}}` | Sdelka nomi |
| `{{lead.price}}` | Бюджет |
| Shartnoma raqami / sanasi | Maxsus maydonlar |
| Brend / Biznes nomi | Maxsus maydon |
| Xizmat | Maxsus maydon |
| Avans summasi, Qoldiq to'lov sanasi | Maxsus maydon |
| `{{contact.name}}`, telefon | Kontakt |
| Kompaniya nomi, STIR, bank rekvizitlari | Kompaniya maydonlari — **hozir 4 ta, rekvizit maydonlarini qo'shish kerak** |

Aniq o'zgaruvchi sintaksisi shablon muharririda ko'rsatiladi — o'sha yerdan nusxa olish.
Shartnoma — 7-bosqichda, hisob-faktura — 8-bosqichda yaratiladi.

---

## 8. Ma'lumot gigiyenasi

**Teg taksonomiyasi** (prefiks majburiy):
- `manba:` — target, facebook-lead-ads, telegram, instagram, sayt, tavsiya, outgoing
- `sifat:` — A, B, past (hozirgi TOIFA_B → `sifat:B`)
- `kampaniya:` — PCG_TOSHKENT7, METASELL_RANO_REFERRAL
- `tizim:` — oisha, eskalatsiya, osilgan
- Menejer tegi — saqlanadi (Oisha tekshiruvi uchun), lekin manba — «Menejer» maydoni.
- «SIM not set» (93), «Mijoz» — ma'nosi aniqlanib o'chiriladi yoki birlashtiriladi.

**Telefonlar:** +998XXXXXXXXX. Repodagi `scripts/amocrm_normalize_deal_phones.py` — avval
dry-run, keyin qo'llash. Undan keyin Сделки → Дубли → birlashtirish.

**Vazifalar:** muddati o'tgan 214 ta — 5-kun sprintida. Keyin qoida: har ochiq sdelkada
bitta ochiq vazifa.

**Arxiv:** 6 oydan eski yopilgan sdelkalar → oyma-oy eksport (6 oylik tarix limiti).
Kontaktlar: 10 000 ga yaqinlashganda sdelkasiz 12 oylik kontaktlarni eksport + o'chirish.

---

## 9. Menejer nazorati (bitta akkaunt)

- **Filtrlar** (Сделки → Фильтр → Сохранить): «Mumtozmaxal — ochiq», «Shahnoza — ochiq»,
  «Rayxon — ochiq», «Baxtiyorjon — ochiq», «Menejer bo'sh», «Vazifasiz», «Muddati o'tgan», «14 kun harakatsiz».
- **Izoh qoidasi:** har izoh `[Ism]` bilan boshlanadi.
- **Sheets KPI** (Oisha har kecha to'ldiradi), ustunlar: sana · menejer · yangi lid ·
  1-javob vaqti (median) · bosqich konversiyalari 1→2→4→5→6→7→8→✓ · yutilgan soni/summa ·
  yo'qotish sabablari · vazifasiz soni.
- **Qo'ng'iroqlar:** Moizvonki ichki raqami → menejer jadvali, Oisha qo'ng'iroqni maydon bo'yicha bog'laydi.

**Oylik reja (1 200 lid):**

| Bosqich | Konversiya | Soni |
|---|---|---|
| Lid | — | 1 200 |
| Kvalifikatsiya | 40% | 480 |
| Uchrashuv | 35% | 168 |
| Brif / KP | 70% | 118 |
| Shartnoma | 50% | 59 |
| Avans | 85% | **~50** (hozir ~23/oy) |

O'rtacha chek ~3,94 mln → ~197 mln so'm/oy. Konversiya foizlari — maqsad, amaldagi bosqich
statistikasi 4 hafta to'plangach qayta hisoblanadi.

---

## 10. Integratsiyalar va Oisha bilan bo'linish

| Ish | Qayerda | Zaxira |
|---|---|---|
| Lid qabul (Meta, sayt) | Mavjud integratsiya → «1. Yangi lid» (89067962) | Oisha solishtirma alert (#787) |
| Speed-to-lead | Oisha (#960) | amoCRM trigger 1–2 |
| Menejer tegi ↔ maydon | Oisha (#956) solishtiradi | Filtr «Menejer bo'sh» |
| Kvalifikatsiya | amoCRM Salesbot | — |
| Avto-yopish | amoCRM trigger 7, 8 | — |
| Shartnoma / hisob-faktura | amoCRM shablon | — |
| Avans → loyiha | Webhook (trigger 14) → Oisha yoki Make → Airtable | qo'lda |
| Haftalik hisobot, qo'ng'iroq tahlili | Oisha | — |

Qoida: bitta ishni ikki tizim qilmaydi. Oisha o'z kodida status ID ishlatadi — ID saqlash
o'chirishdan himoya qiladi, lekin **bosqich MA'NOSI o'zgarsa Oisha kodini ham yangilash shart**.

**Oisha kodi migratsiyasi (yangi voronkani yoqishdan OLDIN):**
- `src/services/call_analytics/crm_automation_config.py` → `STAGE_RULES`:
  - `OUTCOME_PROPOSAL` hozir 88871066 ga (endi «7. Shartnoma») suradi → yangi «6. KP yuborildi» ID siga.
  - `OUTCOME_PAYMENT` → yangi «8. Avans kutilmoqda» ID siga.
  - `pipeline_order` ga yangi 2 bosqich (KP, Avans) va «5. Brif olindi» (89380154) qo'shilsin, tartib 3-bo'limdagidek.
- Yangi status ID lar bosqichlar yaratilgach API'dan olinadi (`/api/v4/leads/pipelines/11162698`).
- Testlar: har outcome → kutilgan status; KP/Avans bosqichidagi sdelkada `_plan_stage` stage avtomatikasini o'tkazib yubormaydi.
- CRM write-avtomatikasi migratsiya merge bo'lguncha o'chiq turadi.

**Webhook** (Настройки → API → Webhooks): hodisa «Сделка изменила статус» → URL Oisha.
Payload `application/x-www-form-urlencoded` — Make/Oisha shu formatni qabul qilishini tekshirish.

---

## 11. Limit balansi (sozlashdan keyin)

| Resurs | Ishlatiladi | Limit |
|---|---|---|
| Triggerlar | 15 + mavjudlar *(0-kun hisoblanadi)* | 100 |
| Sdelka maydonlari | ~40 | 200 |
| Ochiq sdelka | 491 → maqsad < 400 | 1 000 |
| Kontakt | *tekshirish kerak* | 10 000 |
| Token | ~9 600/oy *(taxmin)* | 10 000 |
| Voronkalar | 9 → 5 (Sotuv, Farmer, Sifat, Reactivation, Partnership) | — |

---

## 12. Qabul mezonlari

**Voronka**
- Test lid (sayt formasidan) «1. Yangi lid»ga tushadi.
- Meta test lid shu bosqichga tushadi; Oisha alert jim turadi.
- Arxiv voronkalarga yangi lid tushmaydi (1 hafta kuzatish).

**Majburiy maydonlar**
- «Xizmat»siz sdelkani 2-bosqichga surib bo'lmaydi.
- Budjetsiz sdelka 5-bosqichga o'tmaydi.
- Sababsiz yopib bo'lmaydi.

**Triggerlar**
- Yangi lid → 5 daqiqada vazifa paydo bo'ladi.
- 15 daqiqa harakatsiz test lid → asoschiga xabar keladi.
- 72 soat harakatsiz test lid → «Javob bermadi» bilan yopiladi.

**Salesbot**
- Telegram test: 4 savol → maydonlar to'ldi → bosqich 2 → menejer tayinlandi.
- Noto'g'ri telefon → qayta so'raydi.
- RU varianti ishlaydi.

**Nazorat**
- Har filtr to'g'ri sonni ko'rsatadi (qo'lda 5 ta sdelka bilan solishtirish).
- Sheets KPI ertasi kuni to'ldi.
- «Menejer bo'sh» = 0, «Vazifasiz» = 0.

**Hujjatlar**
- 7-bosqichga o'tkazilgan test sdelkada shartnoma barcha maydonlari to'g'ri chiqadi.

---

## 13. Xavflar va orqaga qaytarish

| Xavf | Oldini olish | Qaytarish |
|---|---|---|
| Bosqich o'chirilib lid yo'qoladi | Faqat nomlash, ID saqlanadi | 1-kun eksportidan import |
| Majburiy maydon ish oqimini to'xtatadi | Avval 2 kun «ogohlantirish» rejimida o'quv, keyin yoqish | Maydonda «Обязательное» belgisini olib tashlash |
| Avto-yopish tirik lidni yopadi | 72 soat + 24 soatdagi eslatma | 143 dan qaytarish, sabab «Javob bermadi» filtri |
| Token tugaydi | 1-hafta real sarfni o'lchash | Eslatmani o'chirish yoki paket (139 000 so'm) |
| Arxiv voronkaga integratsiya lid yuboradi | Неразобранное o'chirishdan oldin manbalarni tekshirish | Неразобранное qayta yoqish |
| Menejerlar maydonni to'ldirmaydi | Majburiy + Oisha kunlik «Menejer bo'sh» alert | — |
| Telefon normalizatsiya xato birlashtiradi | Dry-run, 20 ta qo'lda tekshirish | Eksportdan tiklash |

---

## Tasdiqlash kerak (taxmin, faktga aylantirilmagan)

- Mavjud triggerlar va Salesbotlar soni.
- Token qaysi amallarga yechiladi.
- Bosqich konversiya maqsadlari — tarixiy bosqich statistikasi yo'q, taxmin.
- Openstat/roistat maydonlari bo'shmi.
