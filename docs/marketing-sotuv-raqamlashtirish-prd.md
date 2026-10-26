# Marketing → Sotuv zanjirini raqamlashtirish — PRD

**Holat:** Qoralama v0.1 (2026-10-26) · **Ega:** Baxtiyorjon · **Muallif:** Claude (ega bilan grilling sessiyasi)

## 1. Maqsad

Reklamadan to'lovgacha bo'lgan har bir lid **ko'rinadigan, o'lchanadigan va javobgari aniq** bo'lsin.
Qo'lda ish va "chatda qolib ketgan" lid bo'lmasin. Jamoa ritmi (kim nima qildi) ham shu
raqamlarga tayansin.

## 2. Kelishilgan qarorlar

| # | Qaror | Sabab |
|---|---|---|
| D1 | Uchala muammo hal qilinadi: ishlar ko'rinmaydi, bilim yo'qoladi, takroriy savollar | Ega tasdiqladi |
| D2 | Bosqichma-bosqich: 1) kundalik ritm → 2) haftalik retro → 3) savol-javob | Bir vaqtda hammasi = nima ishlamayotgani noma'lum |
| D3 | Oisha'dan tashqari **1 ta** jamoa boti (Hermes). 2 bot (Hamroh+Navbatchi) emas | Standart amaliyot (Geekbot/DailyBot), bot-bot aylanishi yo'q |
| D4 | Jamoa botida CRM/moliya/kalitlarga kirish **yo'q** | "Lethal trifecta": maxfiy ma'lumot + begona xabar + tashqi kanal bitta agentda bo'lmasin |
| D5 | Bot har bo'limning **o'z guruhida** ishlaydi, shaxsiy chatda emas | Ochiqlik va javobgarlik |
| D6 | Moliya guruhi bosqichlarga kiritilmaydi | Maxfiy ma'lumot |
| D7 | Asosiy fokus: **Marketing + Sotuv** to'liq zanjiri | Ega ustuvorligi |

## 3. Ochiq qarorlar

| # | Savol | Tavsiya |
|---|---|---|
| Q1 | Guruhda kim javob beradi: (A) Oisha ko'prik orqali (javobni Hermes yozadi) yoki (B) alohida Hermes bot | B bilan boshlash, 2 haftadan keyin A ga o'tish |
| Q2 | "Biznes asisstant" va "Patent agentligi" guruhlari nima? Rejaga kiradimi? | Ega aytadi |
| Q3 | Oisha mijoz DM'larini o'qiydi va CRM'ga ham kiradi — bu ham "trifecta". Alohida xavfsizlik ko'rigi | Alohida ish sifatida |

## 4. Zanjir va mavjud qismlar

Oisha'da ko'p narsa **yozilgan**. Lekin production'da ishlayaptimi — **tekshirilmagan**.

| # | Bosqich | Kodda bor | Hujjat | Holat |
|---|---|---|---|---|
| 1 | Reklama → lid manbasi (atributsiya) | `services/core/instagram/leadgen_*`, `api/routes/capi_platform.py` | [oisha-capi-platform-prd.md](oisha-capi-platform-prd.md) | ❓ tekshirish kerak |
| 2 | Lid → AmoCRM ga tushishi | `leadgen_router.py`, `leadgen_delivery.py`, `callback_widget.py` | [instagram-full-integration.md](instagram-full-integration.md) | ❓ |
| 3 | Birinchi aloqa tezligi | `call_analytics/missed_call_responder.py`, `incoming_call_card.py` | — | ❓ |
| 4 | Qo'ng'iroq sifati va konversiya | `call_analyzer`, `metasell_conversion.py` | [metasell-conversion-loop.md](metasell-conversion-loop.md) | ❓ (`oisha-calls-report.service` prod'da **failed**) |
| 5 | CRM gigiyenasi (statuslar) | `services/core/crm/` (guard, cleaner) | [CRM_CLEANER.md](CRM_CLEANER.md) | ❓ |
| 6 | Sotuv → Meta'ga qaytish (Purchase CAPI) | `meta_capi_triggers.py` | oisha-capi-platform-prd.md §5.2 | ❓ |
| 7 | Rahbar paneli (RNP) | Sales OS | [oisha-sales-os-suite.md](oisha-sales-os-suite.md) | ❓ |
| 8 | Jamoa ritmi | `reporter/plans.py`, `enforcer/routines.py` + yangi Hermes bot | — | ❓ / yangi |

## 4.1. 0-bosqich audit natijasi (2026-10-26, `journalctl -u oisha-os --since -7d`, faqat o'qish)

| # | Topilma | Belgisi (7 kun) | Zanjir qismi |
|---|---|---|---|
| A1 | Gemini API kaliti yaroqsiz | ~320 × `API key not valid` | 4 — STT va call tahlili to'xtagan |
| A2 | Moizvonki webhook 401 | 201 × | 3/4 — qo'ng'iroq hodisalari kelmayapti |
| A3 | `BOT_TOKEN` yaroqsiz | 26 × `InvalidToken`; `oisha-calls-report` 401 bilan failed | 4/7 — kunlik call hisoboti yo'q |
| A4 | Dialer API 401 | ~1100 × (`caller-id/active`, `dashboard`, `auth/login`) | 3 — sotuvchi paneli |
| A5 | Cloudflare AI token 401 | 114 × | free-AI router zaxirasi |
| A6 | Moizvonki webhook secret query-string'da logga tushadi | har so'rov | Xavfsizlik: rotatsiya + header'ga ko'chirish |
| OK | Leadgen faol (6738 log qator), CAPI 69 qator, IG comment skaner 0 xato | — | 1, 2, 6 |

### Lid ma'lumotlari (lokal SQLite, `mode=ro`, faqat agregat)

Manba: `data/leadgen_delivery.db` (deliveries), `data/meta_ad_attribution.db` (lead_attribution). Faqat Meta leadgen formalari.

| # | Ko'rsatkich | Qiymat | Xulosa |
|---|---|---|---|
| B1 | Leadgen → AmoCRM yetkazish | 584 lid, xato **0**, retry 0 | ✅ Lid CRM'ga tushadi |
| B2 | `campaign_id` to'ldirilgan | **0 / 607** | ❌ Qaysi kampaniya lid berganini bilmaymiz — ROI o'lchanmaydi |
| B3 | Birinchi aloqa qayd etilgan (`first_touch_ts`) | 286 / 607 (**47%**) | ⚠️ 321 lidda birinchi aloqa yo'q yoki qayd etilmagan |
| B4 | Birinchi javob, oxirgi 30 kun (n=286) | median **~20.6 soat**, p90 **~141 soat** | ❌ 276 tasi >15 daqiqa, 250 tasi >1 soat |
| B5 | Yutilgan (`lead_won`) | sentyabr 2, oktyabr 0 | ⚠️ Revenue sync ishlayaptimi — tekshirish kerak |

Eslatma: B4 tunni ham o'z ichiga oladi (ish vaqti filtri yo'q); `first_touch_ts` qanday hisoblanishini kodda tasdiqlash kerak.

Tekshirilmagan: Turso'dagi `call_events`/`call_analyses` (kalit kerak), Instagram DM va sayt lidlari.

## 5. Bosqichlar

### 0-bosqich — Haqiqiy holat auditi (1–2 kun, faqat o'qish)
Har bir zanjir qismi uchun: yoqilganmi (env flag), so'nggi 7 kunda ishlaganmi (log/DB),
qancha lid qayerda yo'qolgan. Natija: shu jadvaldagi ❓ → ✅/⚠️/❌.
**Production'da hech narsa o'zgartirilmaydi.** Prod DB/log'ni o'qish uchun ega ruxsati kerak.

### 1-bosqich — Uzilishlarni tuzatish (audit natijasiga qarab)
Tavsiya etilgan tartib: atributsiya (1, 6) → lid yo'qotish (2) → javob tezligi (3) →
CRM gigiyenasi (5) → panel (7). Har biri alohida PR, test va deploy.

### 2-bosqich — Jamoa boti, pilot
Bitta Hermes bot, **Sotuv** va **Loyihalar** guruhlarida, 2 hafta.
- Ertalab ≤3 savol, kechqurun natija; guruhga qisqa xulosa.
- Oisha guruhga tashlagan lid/call xabarlarini o'qib, "javobsiz lid" eslatmasi.
- Faqat @mention bo'lganda javob beradi; terminal/code_execution/cron tool'lari o'chiq.
- O'lchov: ritmga javob berganlar %, javobsiz lidlar soni (oldin/keyin).

### 3-bosqich — Retro va bilim
Juma 17:00 egaga hisobot; kelishuvlar jurnali — yozuv ega tasdig'idan keyin;
har javobda manba (asl xabar havolasi).

### 4-bosqich — Kengaytirish
Marketing va Team guruhlari; kerak bo'lsa Q1-A (bitta "Oisha" yuzi).

## 6. Xavfsizlik talablari

- Jamoa botida maxfiy ma'lumot yo'q (D4). Oisha → bot ma'lumot oqimi faqat guruhga chiqqan xabarlar orqali.
- Oisha tokeni boshqa dasturda ishlatilmaydi (409 → Oisha to'xtaydi). 2026-10-26 da o'rnatuvchi
  `@jonairobot` (Oisha) tokenini **taniy olmadi** — `ornatish.sh` dagi Oisha-token himoyasi
  qayta ko'rib chiqilishi kerak.
- Prod o'zgarishlari: quiet-hours, approval gate va `AGENTS.md` qoidalari bo'yicha.

## 7. Muvaffaqiyat o'lchovlari

| O'lchov | Hozir | Maqsad |
|---|---|---|
| Manbasi noma'lum lidlar % | audit | < 5% |
| Birinchi javobgacha median vaqt | audit | < 15 daqiqa (ish vaqtida) |
| CRM'ga tushmagan lidlar | audit | 0 |
| Reklama kanali bo'yicha to'lov (ROAS) ko'rinadimi | audit | Ha, haftalik |
| Kundalik ritmga javob berganlar | — | ≥ 80% |

## 8. Manbalar
- Simon Willison, [The lethal trifecta](https://simonw.substack.com/p/the-lethal-trifecta-for-ai-agents)
- DailyBot, [Async standups](https://v3.dailybot.com/blog/getting-started-async-standups)
- Slack, [Security for AI features](https://slack.com/intl/en-sg/help/articles/28310650165907-Security-for-AI-features-in-Slack)
- OpenAI Dots, Claude Duet, Grok-in-Telegram — sharh 2026-10-26 sessiyasida
