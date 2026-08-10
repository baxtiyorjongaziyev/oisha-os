# MetaSell konversiya sikli

> Maqsad: qo'ng'iroq tahlili **sotuvchi konversiyasini oshirishga** xizmat qilsin —
> hisobot uchun ball to'plash uchun emas.

## Muammo nima edi

`CallAnalyzer` har bir AmoCRM qo'ng'irog'ini 6 bosqichli rasmiy rubrik bo'yicha
baholardi va natijani AmoCRM notasiga chiroyli qilib yozardi. Lekin bazaga
**faqat matnli ustunlar** tushardi:

```
Yozilardi : call_id, lead_id, category, summary, client_mood, next_steps,
            transcript, audio_url, caller_phone, task_id, analyzed_at, source
Yozilmasdi: overall_score, manager_name, strengths, weaknesses, outcome,
            duration_seconds
```

Murabbiylik qatlami — `SalesQualityCoach` (kunlik 20:00 hisoboti, haftalik ideal
skript, playbook takliflari) va `/api/ai/metasell-dashboard` — **aynan shu
yozilmagan 6 ta ustunni** o'qiydi.

Natija: ballar hisoblanardi, AmoCRM notasida ko'rinardi va **yo'qolardi**.
Murabbiy bo'sh jadval ustida ishlardi, shuning uchun sotuvchi konversiyasiga
hech qanday ta'sir qila olmasdi.

## Yechim: uch qism

### 1. Sxema bir joyda — `call_analyses_schema.py`

`call_analyses` jadvali endi bitta joyda, to'liq ustunlar bilan e'lon qilinadi.
Mavjud bazaga yetishmayotgan ustunlar idempotent `ALTER TABLE` orqali qo'shiladi
(namuna: `hisobchi_schema.py`). Migratsiya "fail-soft": yiqilsa ham qo'ng'iroq
tahlili to'xtamaydi.

### 2. Ball bazaga yetib boradi — `call_analyzer.py`

Tahlil prompti endi murabbiy uchun kerakli maydonlarni ham so'raydi
(`kuchli_tomonlar`, `zaif_tomonlar`, `etirozlar`, `natija`), va `_log_call_analysis`
to'liq qatorni saqlaydi: `overall_score`, `manager_name`/`manager_id`,
`duration_seconds`, bosqich ballari (`scores`), `strengths`, `weaknesses`,
`objections`, `outcome`, `converted`.

Menejer ismi AmoCRM `responsible_user_id` orqali aniqlanadi — ismsiz qo'ng'iroqni
hech kimga bog'lab bo'lmaydi, shuning uchun u konversiya statistikasiga kirmaydi.

### 3. Konversiya dvigateli — `metasell_conversion.py`

Kunlik hisobot sotuvchilarni **ball** bo'yicha saflaydi. Lekin ball pul
keltirmaydi: menejer 88 ball olib ham bitta uchrashuv kelisha olmasligi mumkin.
Bu modul boshqa savolga javob beradi:

> **Aynan qaysi bosqich shu sotuvchida bitimni yo'qotmoqda?**

Metodologiya ataylab sodda va shaffof:

```
konversiya     = playbook CONVERTING_OUTCOMES bilan tugagan qo'ng'iroqlar ulushi
bosqich_farqi  = o'rtacha_ball(konvertirlangan) − o'rtacha_ball(konvertirlanmagan)
o'sish_nuqtasi = eng katta musbat farqli bosqich (playbook og'irligi hisobga olingan)
```

Ya'ni sotuvchining **o'z** yutgan va yutqazgan qo'ng'iroqlari solishtiriladi.
Bu taxmin emas — dalil.

**Namuna yetarli bo'lmasa modul jim turadi.** Yolg'on ishonch bilan noto'g'ri
maslahat berish konversiyani pasaytiradi, shuning uchun:

| Holat | Xatti-harakat |
|---|---|
| < 6 ta baholangan qo'ng'iroq | Diagnoz yo'q, sabab aytiladi |
| Bir guruh bo'sh (hammasi yutgan/yutqazgan) | Eng past bosqich, "bu dalil emas" izohi bilan |
| Bosqich farqi < 5 ball | "Muammo texnikada emas" deb rostini aytadi |

## Natija: sotuvchi nima ko'radi

Ballar ro'yxati emas, **shu hafta bitta vazifa**:

```
🎯 KONVERSIYA KARTOCHKASI — Aziz Karimov

Qo'ng'iroqlar: 8 ta
Konversiya: 50% (4 ta keyingi qadamga chiqdi)
O'rtacha ball: 75/100

📌 SHU HAFTA BITTA VAZIFA: Yakunlash va keyingi qadam

Nega aynan shu: Konvertirlangan qo'ng'iroqlarda 'Yakunlash va keyingi qadam'
bo'yicha o'rtacha 92 ball, konvertirlanmaganlarida 30 — farq 62 ball.

Mashq: Hech bir qo'ng'iroqni keyingi qadamsiz tugatmang. Yakunda aniq taklif
qiling: 'Kelasi seshanba soat 15:00 da uchrashamizmi?'

Mo'ljal: shu bosqich tuzatilsa konversiya ~16% ga oshishi mumkin.
```

Rahbariyat uchun eng qimmat signal — **ball yuqori, konversiya past**:

```
⚠️ Ball yuqori, konversiya past (skript bajarilyapti, bitim yopilmayapti):
  • Bek Yusupov — 88 ball, 0% konversiya
```

Ball bo'yicha Bek "kunning eng yaxshi sotuvchisi". Konversiya bo'yicha —
jamoaning eng qimmat muammosi. Aynan shu farqni ko'rsatish uchun bu modul yozildi.

## Natija taksonomiyasi

Konversiya mezoni `sales_playbook.py` da — baholashning yagona manbasida:

| Kalit | Konversiya? |
|---|---|
| `uchrashuv_kelishildi` | ✅ |
| `material_yuborish` | ✅ |
| `kp_yuborish` | ✅ |
| `tolov_kelishildi` | ✅ |
| `qayta_qongiroq`, `oylab_koradi`, `rad_etdi`, `aniqlanmadi` | ❌ |

Mezon o'zgarsa — faqat `sales_playbook.py` o'zgaradi.

## Reklamadagi qolgan va'dalar (2026-08-10, 2-bosqich)

Uchta Metasell reklamasidagi va'dalar kod bo'yicha tekshirilib, yopilmagan
to'rttasi shu bosqichda yopildi.

### 1. Vaqt belgisi — poydevor

STT endi transkripsiyani `[mm:ss] A: matn` ko'rinishida so'raydi. Bu ikkita
funksiyaning poydevori (uzilish lahzasi va pauza).

**Regressiya xavfi va uning yechimi:** `[01:42]` ICHIDA ikki nuqta bor.
`speaker_split` yorliqni `line.find(":")` bilan izlaydi — vaqt belgisi olib
tashlanmasa, `[01` yorliq deb o'qiladi va gapirish nisbati **0% ga tushadi**,
ya'ni sotuvchi asossiz jazolanadi. Shuning uchun `strip_timestamps` qo'shildi
va so'z sanaydigan barcha joylarda qo'llanildi:

| Joy | Nima buzilardi |
|---|---|
| `speaker_split` | gapirish nisbati 0% |
| `_transcript_impossible_for_duration` | haqiqiy matn "hallucination" deb rad etilardi |
| `_rubric_applies` | qisqa suhbat uzun ko'rinardi |

### 2. Uzilish lahzasi — "MIJOZ YO'QOLGAN JOY"

`uzilish_vaqti` + `uzilish_sababi` maydonlari. LLM qaytargan vaqt
**tekshiriladi**: qo'ng'iroq davomiyligidan tashqaridagi lahza rad etiladi
(to'qilgan raqam). Vaqtsiz sabab ham tashlanadi — rahbarga foydasiz.

AmoCRM notasida:
```
🔴 MIJOZ YO'QOLGAN LAHZA: 00:47 — E'tirozga javob berilmadi
⏸ Keraksiz pauza: 2 ta (eng uzuni 00:09 da 28.2s)
```

### 3. Keraksiz pauza

**Deterministik** hisoblanadi — LLM'dan so'ralmaydi, chunki vaqt belgilari
bor va buni o'lchash mumkin.

**Metodning chegarasi ochiq aytiladi:** bizda gapning boshlanish vaqti bor,
tugash vaqti yo'q. Shuning uchun gap davomiyligi so'z sonidan baholanadi
(`WORDS_PER_SECOND = 2.5`) va qolgan bo'shliq pauza deb olinadi. Bu —
**taxmin, sekundomer emas**. Chegara (`MAX_ACCEPTABLE_PAUSE_SECONDS = 4.0`)
ataylab saxiy: tabiiy tanaffusni xato deb ko'rsatish sotuvchini asossiz
ayblash bo'ladi.

### 4. Daromad — `metasell_revenue.py`

AmoCRM bitim narxi va yakuni (142=yutildi, 143=yutqazildi) `call_analyses`
ga ko'chiriladi.

**Ikki karra sanash xavfi:** bitta bitimga bir nechta qo'ng'iroq bo'ladi.
Pul qo'ng'iroq bo'yicha yig'ilsa, 3 marta qo'ng'iroq qilingan bitim 3
barobar ko'p daromad ko'rsatadi. Shuning uchun pul **har doim `lead_id`
bo'yicha yagonalanadi**. Bitim bir necha menejerga tegishli bo'lsa — eng
oxirgi qo'ng'iroq qilgani oladi.

Ochiq bitim `lead_won = NULL` bo'lib qoladi — yakunini **taxmin
qilmaymiz**, keyingi sinxronizatsiyada qayta tekshiriladi.

### 5. Trend — reklamadagi "+28% ↗"

Joriy davr oldingi shuncha kunlik davr bilan solishtiriladi. Farq **foiz
punktida (pp)** beriladi:

> 22% dan 50% ga o'sish — bu **+28 pp**.
> Nisbiy "+127%" deb yozish bir xil ma'lumotni kattaroq ko'rsatadi va chalg'itadi.

Har ikki davrda `MIN_CALLS_FOR_TREND = 5` dan kam qo'ng'iroq bo'lsa — trend
ko'rsatilmaydi, o'rniga sababi yoziladi.

## Ko'r nuqta: javobsiz qo'ng'iroqlar (3-bosqich)

To'rtinchi reklamaning sarlavhasi — *"Qaysi sotuvchingiz pul yo'qotyapti?"* —
va dashboard'ida `O'tkazib yuborilgan: 30` degan raqam bor. Bizda bu raqam
chiqmasdi, va sababi bitta qatorda edi:

```python
if not audio_url:
    continue
```

Javobsiz qo'ng'iroqda yozuv bo'lmaydi → qator bazaga umuman tushmasdi.

**Bu shunchaki yetishmayotgan raqam emas, teskari rag'bat edi:**

> Sotuvchi qancha ko'p qo'ng'iroqni ko'tarmasa, uning o'rtacha bali
> **shuncha yaxshi** ko'rinadi — chunki faqat javob berganlari baholanadi.

Ya'ni sarlavhadagi savolga eng to'g'ri javob ba'zan umuman telefon
ko'tarmayotgan odam bo'lishi mumkin, va u eski tizimda **eng yaxshi**
ko'rinardi.

### Nega alohida jadval (`call_events`)

Bu qatorlarni `call_analyses` ga qo'shish xavfli edi — u yerdan o'qiydigan
bir nechta joy ball bo'yicha **filtrlamaydi**:

| O'quvchi | Nima bo'lardi |
|---|---|
| `sales_quality._fetch_call_analysis_rows` | `SELECT *` — javobsiz qo'ng'iroq "0 ball" bo'lib ko'rinardi |
| `intelligence.get_latest_call_analysis` | oxirgi qator — javobsiz qo'ng'iroq "oxirgi tahlil" bo'lib qolardi |

Shuning uchun **sifat tahlili `call_analyses` da, qo'ng'iroq hajmi
`call_events` da**.

### Javob berilganini aniqlash

`duration > 0` — gaplashilgan vaqt bo'lsa, javob berilgan. Yozuv borligi
mezon **emas**: yozuv sozlamalari o'chirilgan bo'lishi mumkin, lekin suhbat
bo'lgan. AmoCRM `call_status` kodlari provayderga qarab farq qiladi,
shuning uchun xom holda saqlanadi, lekin mantiq ularga tayanmaydi.

### Umumiy samaradorlik ≠ konversiya

Ikkalasi ham foizda, lekin maxraji boshqa — va farq aynan ko'r nuqtani
o'lchaydi:

```
konversiya          = konvertirlangan / BAHOLANGAN qo'ng'iroqlar
umumiy samaradorlik = konvertirlangan / JAMI qo'ng'iroqlar (javobsizlar ham)
```

Misol: 25 ta qo'ng'iroq, 10 tasiga javob berilgan, 8 tasi konversiya.
**Konversiya 80%, umumiy samaradorlik 32%.** Birinchi raqamda 15 ta
javobsiz qo'ng'iroq umuman ko'rinmaydi.

### Panel

```
Qo'ng'iroqlar: 128 ta  |  Samarali: 98  |  O'tkazib yuborilgan: 30
O'rtacha davomiylik: 04:32  |  Javob berish: 77%
Umumiy samaradorlik: 25% (javobsizlar ham hisobda)

📵 Javob berish foizi past (bu qo'ng'iroqlar ballarda ko'rinmaydi):
  • Bek Yusupov — 20% (24 ta javobsiz / 30 ta)
```

O'rtacha davomiylik **faqat javob berilganlar** bo'yicha hisoblanadi —
javobsizlarni (0 soniya) qo'shsak, ko'rsatkich ikkita boshqa muammoni
bitta raqamga aralashtirib yuboradi.

## Vizual panel

`GET /dashboard/sales-quality` — ilgari bo'sh zagotovka edi ("Loading…"),
endi haqiqiy panel. Shablon: `src/api/templates/sales_quality_dashboard.html`.

Panel `GET /api/ai/conversion/overview` dan o'qiydi — ya'ni **panel va
Telegram hisoboti aynan bir manbadan** oziqlanadi, ikkita har xil raqam
paydo bo'lmaydi. So'rov yiqilsa xato ochiq ko'rsatiladi: bo'sh panel
"ma'lumot yo'q" degan yolg'on taassurot beradi.

## Interfeyslar

| Kanal | Manzil | Vaqt |
|---|---|---|
| Telegram — jamoa hisoboti | `BackgroundMonitor._job_conversion_weekly` | Dushanba 10:05 |
| Telegram — sotuvchi kartochkalari | shu job, rahbarga | Dushanba 10:05 |
| API — jamoa manzarasi | `GET /api/ai/conversion/overview?days=30` | — |
| API — bitta sotuvchi | `GET /api/ai/conversion/seller-card?manager=<ism>` | — |
| API — trend | `GET /api/ai/conversion/trend?days=30` | — |
| API — pulni sinxronlash | `POST /api/ai/conversion/sync-revenue?days=90` | haftalik avtomatik |
| API — qo'ng'iroq hajmi | `GET /api/ai/conversion/volume?days=30` | — |
| Vizual panel | `GET /dashboard/sales-quality` | — |

## Guardrail

Bu modul **hech narsani avtomatik o'zgartirmaydi**. Playbook (`sales_playbook.py`)
faqat odam qo'li bilan o'zgaradi — mavjud `SalesQualityCoach` qoidasi bilan bir xil.

## Testlar

```bash
SKIP_LIVE=1 python -m pytest tests/test_metasell_conversion.py \
                            tests/test_metasell_revenue.py \
                            tests/test_call_timestamps_and_pauses.py \
                            tests/test_call_analysis_persistence.py -q
```

`test_call_analysis_persistence.py` regressiya qo'riqchisi: murabbiy o'qiydigan
ustunlar ro'yxati qisqarsa test yiqiladi — ya'ni bu uzilish qaytib kelmaydi.
