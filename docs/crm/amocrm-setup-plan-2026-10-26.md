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
- **4-kun:** Yangi 2 bosqich (KP, Avans) qo'shish, 3 ta bosqichni qayta nomlash (3-bo'lim).
  Yangi ID larni yozib olish → Oisha kodi va `META_CAPI_QUALIFIED_STATUS_IDS` PR (10-bo'lim) → deploy.
  Eski «Qayta aloqa» / «Uchrashuvga keldi» dan ko'chirish **faqat deploydan keyin**.
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

## 3. Voronka — «Sotuv Bo'limi» (id 11162698), 6 bosqich

Tamoyil: bosqich = **sotuvchi qiladigan bitta ish** va **marketolog o'lchaydigan bitta konversiya**.
Holat (keyinroq, sifat, menejer) — bosqich emas, maydon/teg.

| # | Bosqich (id saqlanadi) | Sotuvchi nima qiladi | Chiqish mezoni | Max | Marketolog/founder nimani o'lchaydi |
|---|---|---|---|---|---|
| 0 | Неразобранное | — (Salesbot / integratsiya) | Qabul | 15 daq | Kirgan lid soni, manba |
| 1 | **Yangi lid** (89067962) | 15 daqda bog'lanadi | Gaplashildi | 1 kun | Javob tezligi |
| 2 | **Kvalifikatsiya** (87609522) | Ehtiyoj, budjet, qaror qiluvchi | Uchrashuv kelishildi | 3 kun* | Lid sifati: kanal/kreativ bo'yicha maqsadli % |
| 3 | **Uchrashuv / Brif** (87609526) | Uchrashuv, brif, Drive papka | Brif to'liq | 7 kun | Qiziqish → uchrashuv % — **CAPI QualifiedLead** |
| 4 | **KP yuborildi** (yangi) | KP, follow-up | Mijoz «ha» dedi | 5 kun | KP soni, o'rtacha KP summasi |
| 5 | **Shartnoma** (88871066) | Shartnoma yuborish/imzolash | Imzolandi | 5 kun | KP → kelishuv %, chegirma |
| 6 | **Avans kutilmoqda** (yangi) | Hisob-faktura, to'lov nazorati | Avans tushdi | 5 kun | Kelishuv → pul %, tsikl uzunligi |
| ✓ | **Avans to'landi** (142) | → Farmer voronkasi | — | — | Tushum, CAC/ROMI — **CAPI Purchase** |
| ✗ | **Yopildi** (143) | Sabab majburiy | — | — | Yo'qotish sabablari kanal bo'yicha |

\* «Hozir emas, keyinroq» lid **2-bosqichda qoladi**: «Qayta aloqa sanasi» + shu kunga vazifa,
teg `keyinroq`. Max 30 kun (trigger 7). Konversiyani buzmaydi.

**Eski bosqichlar:**
- «Qayta aloqa» (87609518, 68 sdelka) → sdelkalar 2-bosqichga, sana maydonga, teg `keyinroq`.
- «Uchrashuvga keldi» (89380154) → 3-bosqichga.
- Ikkalasi bo'shagach, **Oisha kodi va CAPI env yangilangandan keyin** (10-bo'lim) o'chiriladi.

**Spam / «faqat narx» lidlar:** alohida voronka yo'q. Salesbot javob olmasa → 72 soatda
avto-yopish «Javob bermadi» (trigger 8).

**Bosqich o'zgartirish qoidasi:**
- Huquq — faqat asoschi. Menejerlar voronka sozlamasiga tegmaydi (yozma qoida).
- O'chirishdan oldin checklist: (1) bosqichda 0 sdelka, (2) Oisha kodida status ID qidirildi,
  (3) `META_CAPI_QUALIFIED_STATUS_IDS` tekshirildi, (4) Meta Lead Ads / sayt yo'nalishi,
  (5) bosqich triggerlari ko'chirildi.

### Sotuvchiga qulaylik

- **Kartochka tartibi** (Настройки полей → guruhlar, muhimi tepada):
  1. *Asosiy* — Menejer, Xizmat, Бюджет, Qaror qiluvchi, Keyingi qadam, Qayta aloqa sanasi
  2. *Brif va KP* — Brend nomi, Drive papka, KP summasi
  3. *Shartnoma va to'lov* — raqam, sana, Avans summasi, Qoldiq to'lov sanasi
  4. *Marketing* (alohida tab) — Lead manbasi, UTM, fbclid, Meta Lead ID — avtomatik to'ladi, sotuvchi tegmaydi
- **Bitta ochiq vazifa** — sotuvchi ertalab faqat «Задачи → Сегодня»ni ochadi.
- **Majburiy maydon kam**: bosqichga 1–3 ta yangi talab (4-bo'lim).
- **Tugmali javoblar**: Xizmat, Narxga moslik, Qaror qiluvchi — Список, matn yozish yo'q.
- **Shablon xabarlar** (Чат → Шаблоны): salom, KP yuborish, follow-up, to'lov eslatmasi — UZ/RU.
- **Mobil**: amoCRM ilovasida vazifa push'lari.

### Marketolog va founderga

| Kim | Nima kerak | Qayerdan |
|---|---|---|
| Marketolog | Kanal/kreativ bo'yicha: lid → kvalifikatsiya → uchrashuv → sotuv % | Lead manbasi + UTM (avtomatik), Oisha haftalik hisobot |
| Marketolog | Meta optimizatsiyasi | CAPI: Lead → QualifiedLead (3-bosqich) → Purchase (142, summa bilan) — 10-bo'lim |
| Marketolog | Nega yo'qotyapmiz | Yo'qotish sababi × manba |
| Founder | Kunlik: osilgan sdelkalar, 15 daqda javobsiz lidlar | Trigger 2, 15 → Telegram |
| Founder | Haftalik: har menejer konversiyasi, tushum, prognoz | «Menejer» maydoni → Sheets KPI / Oisha |
| Founder | Yirik sdelkalar (40 mln+) | Avtomatik Menejer = Baxtiyorjon |

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

| Maydon | 2. Kval | 3. Uchr/Brif | 4. KP | 5. Shartn. | 6. Avans | Kimga kerak |
|---|---|---|---|---|---|---|
| Menejer | ✅ | ✅ | ✅ | ✅ | ✅ | Founder |
| Lead manbasi | ✅ | ✅ | ✅ | ✅ | ✅ | Marketolog |
| Xizmat | ✅ | ✅ | ✅ | ✅ | ✅ | Hammasi |
| Qaror qiluvchi | | ✅ | ✅ | ✅ | ✅ | Sotuvchi |
| Brend / Biznes nomi | | ✅ | ✅ | ✅ | ✅ | Ishlab chiqarish |
| Бюджет (price) | | ✅ | ✅ | ✅ | ✅ | Marketolog (CAPI), founder (prognoz) |
| Google Drive papka | | ✅ | ✅ | ✅ | ✅ | Ishlab chiqarish |
| KP summasi | | | ✅ | ✅ | ✅ | Founder |
| Shartnoma raqami/sanasi | | | | ✅ | ✅ | Buxgalteriya |
| Avans summasi | | | | | ✅ | Moliya |

«Qaror qiluvchi» 3-bosqichdan majburiy — birinchi suhbatda har doim aniq emas, sotuvchini to'xtatmasin.
Salesbot baribir so'raydi (6-bo'lim).

### Yo'qotish sabablari (majburiy)
Javob bermadi · Spam / adashgan · Narx qimmat · Budjet yo'q · Raqobatchini tanladi ·
Muddat to'g'ri kelmadi · Xizmat bizda yo'q · Keyinga qoldirdi · Dublikat · Boshqa (izoh majburiy).

---

## 5. Triggerlar (jami / 100)

| # | Bosqich | Hodisa | Amal |
|---|---|---|---|
| 1 | 1. Yangi lid | Kirdi | Vazifa «Qo'ng'iroq/yozish», muddat 15 daq, mas'ul — Menejer maydoni |
| 2 | 1. Yangi lid | 15 daq ichida bosqich o'zgarmadi | Asoschiga xabar (Oisha speed-to-lead zaxirasi) |
| 3 | 1. Yangi lid | Kirdi, manba Telegram/Instagram | Salesbot «Kvalifikatsiya» ishga tushadi |
| 4 | 2. Kvalifikatsiya | Kirdi | Vazifa «Ehtiyoj aniqlash», 1 kun |
| 5 | 2. Kvalifikatsiya | 3 kun turdi, teg `keyinroq` yo'q | Vazifa + teg `eskalatsiya` |
| 6 | 2. Kvalifikatsiya | «Qayta aloqa sanasi» keldi | Vazifa «Qayta aloqa» shu kunga |
| 7 | 2. Kvalifikatsiya, teg `keyinroq` | 30 kun turdi | → 143, sabab «Keyinga qoldirdi» |
| 8 | 1. Yangi lid | 72 soat harakatsiz | → 143, sabab «Javob bermadi» |
| 9 | 3. Uchrashuv / Brif | Kirdi | Vazifa «Uchrashuv» + mijozga eslatma 1 kun oldin |
| 10 | 3. Uchrashuv / Brif | Drive papka to'ldi | Vazifa «KP tayyorlash», 2 kun |
| 11 | 4. KP | 3 kun javobsiz | Vazifa «KP bo'yicha qo'ng'iroq» |
| 12 | 5. Shartnoma | Kirdi | Hujjat: shartnoma shabloni |
| 13 | 6. Avans | Kirdi | Hujjat: hisob-faktura + vazifa «Avansni tekshirish», 3 kun |
| 14 | ✓ Avans to'landi | Kirdi | Webhook → Oisha/Make → Airtable loyiha; nusxa Farmer voronkasiga |
| 15 | Har qanday ochiq bosqich | 14 kun harakatsiz | Asoschiga xabar + teg `osilgan` |

Jami: **15 / 100**. Zaxira: 85.

**Vazifa qoidasi (bitta ochiq vazifa):** vazifani faqat trigger yaratadi (1, 4, 6, 9, 10, 13).
Bosqich o'zgarganda oldingi vazifa yakunlanadi — qo'lda o'tkazishda menejer, Salesbot
o'tkazganda bot (6-bo'lim, 9.3-qadam). Salesbot o'zi vazifa yaratmaydi.
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
| Uchrashuv / Brif | 35% | 168 |
| KP | 70% | 118 |
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
- `src/services/call_analytics/crm_automation_config.py`:
  - **Bug:** `STATUS_YANGI = 87609514` — bunday ID voronkada yo'q (o'chirilgan eski bosqich).
    To'g'risi 89067962. Hozir ham tuzatish kerak.
  - `STATUS_ALOQA` (87609518) — bosqich yo'qoladi, `pipeline_order`dan olib tashlanadi.
  - `OUTCOME_PROPOSAL` hozir 88871066 ga (endi «5. Shartnoma») suradi → yangi «4. KP yuborildi» ID siga.
  - `OUTCOME_PAYMENT` → yangi «6. Avans kutilmoqda» ID siga.
  - `pipeline_order` = Yangi lid → Kvalifikatsiya → Uchrashuv/Brif → KP → Shartnoma → Avans.
- `src/services/core/crm/amocrm_pipeline_config.py`: `SALES_CONTACT_STATUS_ID` (87609518) ishlatilgan joylar
  Kvalifikatsiyaga ko'chiriladi; KP va Avans konstantalari qo'shiladi.
- `src/services/core/crm/task_notifier/formatter.py`: bosqich nomlari xaritasi yangilanadi
  (88871066 hozir «Muzokara» deb yozilgan → «Shartnoma»).
- Yangi status ID lar bosqichlar yaratilgach API'dan olinadi (`/api/v4/leads/pipelines/11162698`).
- Testlar: har outcome → kutilgan status; KP/Avans bosqichidagi sdelkada `_plan_stage` stage avtomatikasini o'tkazib yubormaydi.
- CRM write-avtomatikasi migratsiya merge bo'lguncha o'chiq turadi.

### Meta CAPI (marketolog uchun)

Kod: `src/services/core/marketing/meta_capi_triggers.py`.

| Event | Qachon | Yangi voronkada |
|---|---|---|
| `Lead` | Lead Ads lidi amoCRM'ga tushganda | O'zgarmaydi (89067962 saqlanadi) |
| `QualifiedLead` | Sdelka `META_CAPI_QUALIFIED_STATUS_IDS` (env) bosqichiga kirganda | **Env = `87609526`** («3. Uchrashuv / Brif») |
| `Purchase` | Sdelka 142 ga kirganda, summa majburiy | 142 = «Avans to'landi» |

- **QualifiedLead nima uchun 3-bosqich:** Kvalifikatsiya juda erta va shovqinli — Meta «gaplashdi»
  emas, «haqiqiy qiziqdi» lidini o'rganishi kerak. Har hafta 50+ event bo'lishi uchun 3-bosqich yetarli
  (rejada ~168/oy).
- **Purchase summasi:** kod summasiz Purchase'ni rad etadi (`purchase_value_required`). Hozir 466/491
  ochiq sdelka summasiz → «Бюджет» 3-bosqichdan majburiy (4-bo'lim) buni tuzatadi.
  Purchase qiymati = **shartnoma summasi** (Бюджет), avans emas — Meta to'liq qiymatni optimallashtirsin.
- **Env tartibi:** yangi ID ni env'ga qo'shish → deploy → keyin eski bosqichdan ko'chirish.
  Eski ID (87609518, 89380154) env'da bo'lsa — faqat bosqich bo'shagandan keyin olib tashlanadi.
- **Tekshiruv:** test Lead Ads lidini 3-bosqichga, keyin 142 ga o'tkazish → Meta Events Manager'da
  `QualifiedLead` va `Purchase` (value bilan) ko'rinadi; Oisha `/capi` hisobotida ham.

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
