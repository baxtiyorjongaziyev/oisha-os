# Hunter oqimi — reja (kod yo'q)

Sana: 2026-10-20. Holat: taklif, owner tasdig'ini kutadi.

Maqsad: hamma manbadan kelgan potensial mijoz **bitta yo'l** bilan amoCRM
"Sotuv" voronkasi → "Yangi LEads" (`SALES_PIPELINE_ID` / `SALES_NEW_STATUS_ID`)
bosqichiga tushsin. Takrorsiz, boyitilgan, kimdan kelgani yozilgan holda.

## 1. Hozirgi holat (kod o'qib tekshirildi, prod log ko'rilmadi)

| Manba | Fayl | Holat |
|---|---|---|
| Meta/Instagram Lead Ads | `services/core/instagram/leadgen_*`, `schedulers/meta_leadgen_scheduler.py` | **Ishlaydi.** Dedup (`leadgen_dedup`), router, watchdog, CAPI bor |
| Telegram DM / guruh xabari | `handlers/msg_pipeline/lead_intake.py` → `auto_lead_agent` | Ulangan (xabar keladi → lid) |
| Callback vidjet / telefoniya | `leads/callback_request.py`, `leads/call_tracking.py` | Ulangan |
| Telegram kanal scout | `channel_scout.py` + `channel_scout_loop` | Loop ishlaydi, lekin **faqat tahlil**, amoCRM'ga yozmaydi |
| Kanal lid ekstraktori | `channel_lead_extractor.py` (`create_lead` bor) | Faqat `channel_scheduler.setup_channel_scout_scheduler` chaqiradi; uni chaqiruvchi topilmadi |
| Tadbirkorlar skreperi | `uzbek_entrepreneurs_scraper.py` | O'z jadvaliga (`uzbek_entrepreneurs`) yozadi, amoCRM'ga emas |
| LinkedIn / Telegram / Instagram skreperlari | `uzbek_linkedin_scraper.py`, `uzbek_telegram_scraper.py`, `uzbek_instagram_scraper.py` | Hech kim import qilmaydi |
| Apollo boyitish | `apollo_enrich.py` | Hech kim import qilmaydi |
| Guruh a'zolari / dialog sinxroni | `leads/scraper/group_sync.py`, `dialog_sync.py` | Bitta joydan import, ishga tushishi tekshirilmadi |
| Telefon → Telegram boyitish | `telegram/phone_enricher/` | Bor, oqimga ulanmagan |

amoCRM'ga yozish yo'llari hozir **kamida 4 xil** (`create_lead`, `create_standalone_lead`,
`ensure_lead`, leadgen router). Faqat `ensure_lead` telefon bo'yicha mavjud aktiv bitimni tekshiradi.

## 2. Arxitektura

```
Manba adapterlari ──▶ hunter_candidates (DB navbat) ──▶ Normalize ──▶ Dedup ──▶ Boyitish
                                                                              │
                                     amoCRM Sotuv/Yangi ◀── Yozuvchi (bitta) ◀┘
                                     + izoh: manba, dalil, ball
```

Qoidalar:
- **Bitta yozuvchi.** amoCRM'ga faqat `HunterWriter` yozadi, ichida `ensure_lead`. Boshqa
  manbalar to'g'ridan-to'g'ri `create_lead` chaqirmaydi.
- **Navbat DB'da**, `database_pool` orqali. Jarayon qayta ishga tushsa, nomzod yo'qolmaydi.
- Har nomzodda `source`, `source_ref` (xabar havolasi, leadgen_id va hokazo), `seen_at` bo'ladi.

### 2.1 Manbalar (ustuvorlik bo'yicha)

1. **Kiruvchi (issiq):** Meta Lead Ads, Telegram DM, callback, qo'ng'iroq. Hozir ishlaydi,
   faqat yozuvchini almashtirish kerak.
2. **Signal (iliq):** Telegram guruh/kanalda "logo kerak", "brend", "dizayner qidiryapman"
   kabi so'rov yozgan odam. `channel_lead_extractor` asos bo'ladi.
3. **Sovuq (baza):** 2GIS/Yandex katalog, tadbirkorlar skreperi, Instagram bizneslari.
   Faqat ICP filtridan o'tgani olinadi (soha, shahar, kontakt bor).

Har adapter `HunterCandidate` qaytaradi: name, phone?, telegram_username?, instagram?,
company?, source, source_ref, evidence (matn parchasi).

### 2.2 Normalize va dedup

- Telefon: raqamlar, `+998` formatiga keltiriladi, 12 raqam bo'lishi shart.
- Kalitlar: `phone_e164`, `telegram_user_id` yoki `username`, `instagram_handle`, `company_inn`.
- **Dedup 3 qatlam:**
  1. Navbat ichida bitta kalit = bitta nomzod. Manbalar birlashadi, `sources[]`.
  2. Lokal `hunter_seen` jadvali: kalit → amo_lead_id, oxirgi ko'rilgan vaqt.
  3. amoCRM: `find_active_lead_by_phone`, ya'ni `ensure_lead`. Aktiv bitim topilsa, yangi
     bitim ochilmaydi, faqat izoh qo'shiladi: "yana X manbadan keldi".
- Yopilgan bitim (142/143) 90 kun ichida bo'lsa, yangisi ochilmaydi, owner'ga signal ketadi.
- Telefon xeshi `lead_source.py` dagi SHA-256 yondashuviga mos keladi.

### 2.3 Boyitish (faqat dedupdan o'tganlar, arzondan qimmatga)

1. Bepul: telefon → Telegram profil (`phone_enricher`), kanal/bio matnidan soha.
2. Katalog: 2GIS/Yandex'dan kompaniya nomi, manzil, sayt.
3. AI qisqa xulosa (free_ai_router): soha, ehtiyoj, ICP ball 0–100. Natija lid **izohiga**
   yoziladi, custom field'ga emas. Field'lar hali sozlanmagan.
4. Apollo: faqat xalqaro yoki katta B2B uchun, kalit bo'lsa. UZ kompaniyalarida qamrovi past.

Ball chegarasidan past nomzod amoCRM'ga yozilmaydi, navbatda `rejected` bo'lib qoladi.

### 2.4 amoCRM'ga yozish

- `ensure_lead(pipeline=SALES, status=SALES_NEW)`, teg: `hunter:<source>`.
- Izoh shabloni: manba, dalil (havola yoki matn), ball, boyitish natijasi.
- Kunlik limit: `HUNTER_DAILY_LIMIT`, default 20. Sovuq manbalar avval `HUNTER_MODE=shadow`
  rejimida ishlaydi: hech narsa yozilmaydi, owner'ga kunlik ro'yxat ketadi.
- Quiet-hours (`agent_policy`) amoCRM yozuviga to'g'ridan-to'g'ri ta'sir qilmaydi, lekin
  sotuvchiga bildirishnoma 07:00 dan keyin ketadi.

## 3. Xavflar (oldindan hal qilish kerak)

- **amoCRM 500 bitim limiti.** `/crm` sahifasida eslatilgan, `crm_capacity_archiver` bor.
  Sovuq baza tez to'ldiradi. Shuning uchun kunlik limit, ball chegarasi va arxivator bilan
  muvofiqlashtirish kerak.
- **Shaxsiy ma'lumot qonuni** (O'zbekiston, ZRU-547, mahalliylashtirish talabi).
  Guruhdan telefon yig'ish va sovuq qo'ng'iroq huquqiy savol. Yuridik tekshiruvsiz sovuq
  manba yoqilmaydi. *Taxmin: talablarni yurist tasdiqlashi kerak.*
- **Telegram sessiyasi.** Skreperlar userbot sessiyasidan foydalansa, ban xavfi bor va
  Contabo sessiyasini buzish mumkin. Alohida sessiya va qat'iy rate limit kerak.
- **Sotuvchi yuklamasi.** 18 yoshli operator kuniga 20 tadan ortiq lidni ishlay olmaydi.
  Limitni sotuv tezligiga bog'lash kerak.

## 4. Bosqichlar (har biri alohida PR)

1. **Yagona yozuvchi + navbat jadvali.** Meta va Telegram DM shu yozuvchiga o'tadi.
   Natija: hozirgi oqim o'zgarmaydi, lekin bitta yo'ldan yuradi va dedup ishlaydi.
2. **Dedup hisoboti.** Mavjud amoCRM'dagi takrorlarni sanash, faqat o'qish.
3. **Signal manbasi** (`channel_lead_extractor`) shadow rejimda, 2 hafta.
4. **Boyitish:** phone_enricher va AI ball.
5. **Sovuq manba** (2GIS/katalog). Faqat yuridik "ha" va owner tasdig'idan keyin.
6. Ishlatilmaydigan skreperlarni o'chirish (LinkedIn/Telegram/Instagram `uzbek_*`, Apollo
   kerak bo'lmasa).

## 5. Muvaffaqiyat o'lchovi

- Takror bitimlar: 0. Haftalik dedup hisoboti tekshiradi.
- Har lidda manba yozilgan: 100%.
- Hunter lidlaridan "Gaplashdik" bosqichiga o'tish ≥ 30%. Pastroq bo'lsa, ball chegarasi ko'tariladi.
- Kunlik limit oshmaydi, 500 bitim chegarasiga yaqinlashilmaydi.

## Owner qarori kerak

1. Sovuq manbalar (guruh a'zolari, katalog) umuman kerakmi, yoki faqat kiruvchi + signal?
2. Kunlik limit nechta?
3. Apollo pullik kaliti olinadimi?
