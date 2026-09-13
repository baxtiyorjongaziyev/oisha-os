# Analitika sahifasini real ma'lumotga ulash — dizayn

**Sana**: 2026-09-14
**Muallif**: Baxtiyorjon + Claude

## Maqsad

`apps/web/src/app/(dashboard)/analytics/page.tsx` sahifasidagi 7 tabdan 2 tasi
(Umumiy ko'rinish, CRM Hisobot) real backend'ga ulangan, qolgan 5 tasi hardcoded
fake son ko'rsatadi. Bu "o'lchash mumkin bo'lgan narsani o'stirish" maqsadiga
zid — noto'g'ri raqamga qarab qaror qabul qilib bo'lmaydi.

Ushbu loyiha 4 tabni real qiladi va 1 ta yangi tab qo'shadi:

1. Sifat nazorati — real
2. Jamoa malakasi — real
3. Mijoz tahlili — real
4. Lid analitikasi — real
5. **Marketing ROI (yangi tab)** — CAC va marketing xarajat

**Scope'dan tashqarida**: "Faoliyat tahlili" (qo'ng'iroq ulangan/ulanmagan soni)
— Moizvonki integratsiyasi hali kodda yo'q, alohida keyingi loyiha.

## Mavjud infratuzilma (o'zgarmaydi, qayta ishlatiladi)

- `src/services/sales_quality/` — `_fetch_call_analysis_rows()`,
  `_build_sales_quality_payload()`, `_fetch_manager_card_rows()`,
  `_build_manager_cards_payload()`, `RADAR_AXES` (A1-E3 mezonlar)
- `call_analyses` jadvali: `scores` (JSON, mezon bo'yicha ball),
  `objections_raised` (JSON list), `manager_id`, `manager_name`, `overall_score`
- `src/services/core/crm/daily_report/` — `CRMPeriodReporter` (won_count,
  pipeline_value va h.k.)
- `src/services/core/finance/finance_engine.py` — kategoriyalar
  (`"marketing"` allaqachon mavjud kategoriya)
- RBAC: `Permission.DASHBOARD_READ`, `Permission.FINANCE_READ` (`src/api/rbac.py`)
- Frontend pattern: `fetch` → `loading`/`available: false` holatlari
  (`dashboard_overview.py` va uning frontend qismidagi kabi)

## 1. Sifat nazorati tab

**Haqiqiy ma'lumot shakli** (`sales_playbook.py` — yagona haqiqat manbai):
`call_analyses.scores` — JSON dict `{stage: ball}`, 6 ta bosqich:
`salomlashish`, `ehtiyojlar`, `qiymat`, `etirozlar`, `yakunlash`,
`muloqot_sifati` (0-100 ball). Har bosqichning og'irligi `STAGE_WEIGHTS`da.
Frontendda hozir ko'rsatilayotgan "A1/E1" kodlar mavjud emas — bosqich
nomlari real tizim tili.

**Backend**: yangi endpoint `GET /api/sales-quality/weak-stages`
(`src/services/sales_quality/router.py` ga qo'shiladi, `Permission.DASHBOARD_READ`).

- `_fetch_call_analysis_rows()` orqali barcha qatorlarni oladi
- Har bir qatordagi `scores` JSON dict'ini parse qiladi (`_safe_json_dict`
  mavjud helper)
- Har bir bosqich (`STAGE_WEIGHTS` kalitlari) bo'yicha: `rate = shu bosqich
  ballarining o'rtachasi`, `count = shu bosqich 60 balldan past bo'lgan
  qo'ng'iroqlar soni` (`sales_playbook.SCORE_AVERAGE` chegarasi)
- Eng past `rate`ga ega 4 ta bosqichni qaytaradi (o'zbekcha nom uchun kichik
  lookup: `salomlashish` → "Salomlashish" va h.k., `RADAR_AXES`dagi bilan bir
  xil uslubda)
- Har biri uchun misol xato — shu bosqich past ball olgan qo'ng'iroqlardan
  birining `weaknesses` (JSON list) ichidagi birinchi matn, bo'lmasa bo'sh
- Ma'lumot yo'q bo'lsa `{"available": false}`

**Frontend**: `activeTab === "quality"` bloki `useEffect` bilan shu endpointdan
fetch qiladi, hozirgi 4 ta hardcoded card massivini natija bilan almashtiradi.
`available: false` bo'lsa "Ma'lumot yetarli emas" holati.

## 2. Jamoa malakasi tab

**Backend**:
- Mavjud `GET /api/sales-quality/manager-cards` dan foydalaniladi (o'zgarishsiz)
  — eng past `average_score`li menejerni frontend tanlaydi
- Yangi: shu menejerning eng zaif bosqichi — `weak-stages` endpoint'ga
  `manager_id` query parametr qo'shiladi (ixtiyoriy filter)
- **AI tavsiya matni**: yangi jadval `training_advice` (manager_id, advice_text,
  generated_at). Yangi kunlik scheduler
  `src/schedulers/training_advice_scheduler.py` — har kuni bir marta eng past
  ballli menejer(lar) uchun `OishaBrain` orqali tavsiya generatsiya qilib DB'ga
  yozadi (mavjud `daily_analytics_reporter.py` patterniga o'xshash). Yangi
  endpoint `GET /api/sales-quality/training-advice` faqat DB'dan o'qiydi —
  runtime'da AI chaqirilmaydi.

**Frontend**: "AI tavsiyasini yangilash" tugmasi endi `training-advice`
endpoint'ini qayta fetch qiladi (keshlangan qiymatni ko'rsatadi, `setTimeout`
soxta animatsiya olib tashlanadi).

## 3. Mijoz tahlili tab

**Backend**:
- Yangi jadval `objection_clusters` (cluster_id, label, count, updated_at)
- Yangi kunlik scheduler `src/schedulers/objection_clustering_scheduler.py`:
  so'nggi 30 kunlik `call_analyses.objections_raised` dan barcha e'tirozlarni
  yig'adi, `OishaBrain`ga bitta batch so'rov yuborib semantik guruhlarga
  ajratadi (masalan "narx qimmat" + "qimmat narx ekan" → bitta cluster), har
  cluster uchun `label` va `count`ni DB'ga yozadi (eski qatorlarni almashtiradi)
- Yangi endpoint `GET /api/sales-quality/objections` — `objection_clusters`dan
  o'qiydi, foizini hisoblab qaytaradi (`count / jami_scored_qongiroqlar_soni`)

**Frontend**: "Top e'tirozlar tahlili" bloki shu endpointdan olingan
cluster/foiz bilan render qilinadi. "Jami bitim summasi/soni" kartalari —
`CRMPeriodReporter`dagi mavjud `won_amount`/`won_count`ga ulanadi (yangi backend
kerak emas, faqat frontend `crm/reports` endpoint'ini chaqiradi).

## 4. Lid analitikasi tab

**Backend**: yangi endpoint `GET /api/crm/lead-quality`
(`src/api/routes/crm_reports.py` ga qo'shiladi):

- `CRMPeriodReporter`/AmoCRM orqali tanlangan davrdagi barcha lidlarni (`price`
  bilan) oladi
- Narx bo'yicha tartiblab tertsil chegaralarini hisoblaydi: pastki 1/3 = "past",
  o'rta 1/3 = "o'rtacha", yuqori 1/3 = "yaxshi"
- Har guruh uchun son va foizni qaytaradi
- Lid yo'q yoki narxsiz bo'lsa `{"available": false}`

**Frontend**: "Lid sifati taqsimoti" gradient bar shu endpointdan olingan
haqiqiy foiz bilan chiziladi. "Jami yangi lidlar/Yutganlar/Yutqazilganlar"
kartalari — mavjud `crm/reports` (`new_leads`, `won_count`, `lost_count`,
`active_count`) ga ulanadi, `change` (oldingi davrga nisbatan %) mavjud
`deltas` field'idan hisoblanadi.

## 5. Marketing ROI tab (yangi)

**Backend**: yangi endpoint `GET /api/finance/marketing-roi`
(`src/api/routes/finance_dashboard.py` ga qo'shiladi, `Permission.FINANCE_READ`):

- `finance_source`dan tanlangan davrdagi `category == "marketing"` chiqimlar
  yig'indisini oladi
- `CRMPeriodReporter`dan shu davrdagi `won_count`ni oladi
- `CAC = marketing_xarajat / won_count` (won_count == 0 bo'lsa `cac: null`,
  "hisoblab bo'lmadi" holati)
- Qaytaradi: `{available, period, marketing_spend, won_count, cac}`
- Ikkala manba (finance yoki AmoCRM) ulanmagan bo'lsa `available: false`

**Frontend**: yangi tab `"marketing"` — `analytics/page.tsx` tab ro'yxatiga
qo'shiladi. KPI kartalari: Marketing xarajat, Yangi mijozlar (won), CAC.

## Umumiy qoidalar

- Har bir yangi endpoint mavjud RBAC pattern'iga rioya qiladi
  (`require_permissions`)
- Ma'lumot manbai ulanmagan yoki xato bo'lsa har doim `available: false` /
  503 — hech qachon soxta/namuna raqam qaytarilmaydi (`finance_dashboard.py`
  dagi mavjud qoida davom etadi)
- Yangi scheduler'lar (`training_advice_scheduler.py`,
  `objection_clustering_scheduler.py`) mavjud `src/schedulers/` papkasiga,
  400-qator standartiga rioya qilib qo'shiladi
- Yangi jadvallar (`training_advice`, `objection_clusters`) Turso/SQLite orqali,
  `database_pool.py` connection pool ishlatiladi — xom SQL connection ochilmaydi
- Test: har yangi endpoint uchun `tests/test_*.py`, `SKIP_LIVE=1` bilan mock
  qilinadigan

## Testing strategiyasi

- Backend: har endpoint uchun unit test — bo'sh DB holati (`available: false`),
  to'liq ma'lumot holati, RBAC rad etish holati
- Scheduler: mock `OishaBrain` javobi bilan cluster/advice yozilishini tekshirish
- Frontend: manual QA — dev serverda har tabni ochib, backend o'chirilganda
  (`available: false`) va yoqilganda ko'rinishni tekshirish

## Amalga oshirish tartibi (kichik PR'larga bo'lingan)

1. Sifat nazorati (`weak-criteria` endpoint + frontend)
2. Jamoa malakasi (`training-advice` scheduler + endpoint + frontend)
3. Mijoz tahlili (`objection-clustering` scheduler + endpoint + frontend)
4. Lid analitikasi (`lead-quality` endpoint + frontend)
5. Marketing ROI (yangi tab, `marketing-roi` endpoint + frontend)

Har biri alohida PR, mustaqil test qilinadi va deploy bo'ladi (400-qator va
AGENTS.md pre-flight qoidalariga muvofiq).
