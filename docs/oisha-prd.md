# Oisha OS — Product Requirements Document

**Status:** Draft v1.0  
**Date:** 2026-09-29  
**Product owner:** Jon Branding  
**Primary market:** Branding and creative agencies

## 1. Product summary

Oisha OS — Jon Branding agentligining 24/7 operatsion miyasi. U AmoCRM, Google
Drive, Airtable/Google Sheets, Hisobchi, Google Calendar, Telegram va boshqa
tasdiqlangan manbalardan real signal yig‘adi; ularni tekshiradi, izohlaydi,
egaga qisqa va dalilli ko‘rinishda beradi hamda faqat ruxsat berilgan hollarda
amaliy o‘zgarish qiladi.

Oisha ERP o‘rnini bosmaydi. Har bir domenning manba tizimi source of truth
bo‘lib qoladi; Oisha esa integratsiya, tahlil, ogohlantirish, rejalashtirish va
approval qatlamidir.

## 2. Problem

Agentlik rahbari bugungi holatni bilish uchun bir nechta tizimni qo‘lda tekshiradi.
Natijada yangi leadlar, kechikayotgan loyihalar, olinmagan to‘lovlar,
javobsiz mijozlar va egasiz tasklar kech ko‘rinadi. Turli manbalardagi raqamlar
bir-biriga mos kelmasligi va source ishlamaganda nol ko‘rsatilishi noto‘g‘ri
qarorlarga olib kelishi mumkin.

## 3. Product goals

1. Rahbarga “hozir biznesda nima bo‘lyapti?” savoliga qisqa, real va manbali javob berish.
2. Sotuv, loyiha, moliya va jamoa risklarini muammo kattalashishidan oldin ko‘rsatish.
3. Takroriy monitoring va hisobot ishlarini avtomatlashtirish.
4. Har bir AI xulosasini manba yozuvi, vaqt va evidence bilan izohlash.
5. Owner approval talab qilinadigan o‘zgarishlarni xavfsiz va audit qilinadigan qilish.
6. Oisha’ni keyinchalik boshqa branding agentliklariga moslashtiriladigan mahsulotga aylantirish.

## 4. Non-goals

- AmoCRM, Airtable yoki Sheets o‘rniga yangi CRM/ERP qurish.
- Manba ulanmaganida raqam, status yoki revenue o‘ylab topish.
- Owner approval’siz moliyaviy, CRM, access yoki ommaviy kommunikatsiya mutatsiyasi.
- Birinchi bosqichda mijozlar uchun to‘liq portal yoki billing platformasi.
- Telegram userbot sessiyasini lokal kompyuterda ishlatish.

## 5. Users and jobs to be done

| User | Asosiy ehtiyoj | Natija |
| --- | --- | --- |
| Owner/Admin | Biznes pulsini ko‘rish, qaror qilish | Command Center, digest, approval |
| ROP/Sales lead | Leadlar va menejerlar intizomini nazorat qilish | Prioritetlar, SLA, coaching |
| Sales manager | Bugun kimga qo‘ng‘iroq qilishni bilish | Lead context, next action, task |
| Project manager | Deadline va handoff riskini ko‘rish | Risklar, egalar, bloklar |
| Finance owner | To‘lov, qarz va marjani nazorat qilish | Payment risks, source-linked snapshot |
| Operator/agent | Tizimdan aniq keyingi qadam olish | Telegram task va alert |

## 6. Product principles

- **Real-data-only:** har bir fakt source, timestamp va record/message ID bilan.
- **Source health first:** manba ishlamasa `source_unavailable` ko‘rsatiladi; zero deb talqin qilinmaydi.
- **Read first, write carefully:** default — read-only; mutatsiya approval/policy orqali.
- **Evidence over confidence:** AI xulosasi ishonchlilik darajasi va dalilini ko‘rsatadi.
- **One owner, one source:** har bir domen uchun canonical source belgilanadi.
- **Quiet automation:** faqat actionable o‘zgarishda xabar yuboriladi.
- **Reversible operations:** write-back oldidan plan, keyin verify va audit.

## 7. Source-of-truth map

| Domain | Canonical source | Oisha vazifasi |
| --- | --- | --- |
| Sales pipeline | AmoCRM | Prioritet, duplicate, follow-up, task |
| Client files | Google Drive | Brief, KP, brandbook va feedback linklari |
| Project delivery | Airtable/Google Sheets | Deadline, owner, stage, handoff risklari |
| Meetings | Google Calendar | Tasdiqlangan uchrashuv va reminder |
| Finance | Hisobchi + Google Sheets | Advance, debt, cost, margin signal |
| Conversation evidence | Telegram userbot | Ruxsat etilgan chat/voice konteksti |
| Approval and delivery | Telegram bot | Approval, report, alert va audit reference |
| Workflow glue | n8n | Core kodga tegishli bo‘lmagan workflowlar |

## 8. MVP scope

### 8.1 Command Center / RNP

Rahbar uchun yagona ko‘rinish:

- Bugungi sotuv prioritetlari.
- Kechikayotgan yoki qotib qolgan loyihalar.
- To‘lov va qarzdorlik risklari.
- Jamoa yuklamasi va egasiz tasklar.
- Javobsiz mijozlar va SLA buzilishlari.
- Integration health va oxirgi yangilanish vaqti.
- Har bir signal uchun severity, owner, deadline va evidence.

### 8.2 Sales Intelligence

- Yangi leadni normalizatsiya va duplicate tekshiruvi.
- Source, owner, funnel/stage va oxirgi activity ko‘rinishi.
- “Bugun kimga qo‘ng‘iroq qilish kerak?” ro‘yxati.
- Stuck lead, missed follow-up va repeated unanswered alertlari.
- AmoCRM’ga approved task/note write-back va post-write verification.

### 8.3 Conversation Intelligence

- AmoCRM call record va Telegram userbot ko‘ra oladigan audio/voice ingestion.
- Transcription, Uzbek/Russian/mixed language detection va timestamplar.
- Summary, objection, buying signal, commitment va next action.
- Sales rubric: greeting, needs, value, objections, closing, communication.
- Manager coaching va owner/ROP daily rollup.
- `mijoz`, `jamoa`, `shaxsiy`, `oila`, `noma'lum` call policy.

### 8.4 Project Operations

- Brief, KP, deadline, owner, stage va Drive file linklari.
- Deadline, blocked stage, missing owner va handoff risklari.
- Project bo‘yicha keyingi action va source record link.

### 8.5 Finance Signals

- Advance, remaining balance, expense, debt va missing-field risklari.
- Hisobchi/Sheets manbasi ishlamasa aniq unavailable holati.
- Marginni faqat tasdiqlangan fieldlar mavjud bo‘lsa ko‘rsatish.
- Moliyaviy yozuvlar uchun owner approval va Obsidian audit.

### 8.6 Reporting and delivery

- Telegram daily digest.
- Weekly/monthly management report.
- On-demand commands: `/command_center`, `/sales_today`, `/project_risks`,
  `/finance_risks`, `/team_capacity`.
- Source health buzilganida silent report yubormaslik.

## 9. Functional requirements

### FR-1 — Integration health

Har bir connector `configured`, `healthy`, `degraded`, `unavailable` yoki
`not_configured` holatini qaytaradi. Health endpoint token va secretlarni
oshkor qilmaydi. Report shu status va check timestampini ko‘rsatadi.

### FR-2 — Evidence envelope

Har bir signal quyidagi minimal ma’lumotga ega bo‘ladi:

```json
{
  "source": "amocrm",
  "source_record_id": "...",
  "observed_at": "...",
  "confidence": "high",
  "reason": "...",
  "recommended_action": "..."
}
```

### FR-3 — Approval boundary

Mutatsiya oldidan Oisha action plan yaratadi: nima o‘zgaradi, qayerda, kimga
ta’sir qiladi va rollback/verification qanday. Owner approval bo‘lmasa action
ishlamaydi, policy’da safe deb belgilanmagan barcha tashqi write’lar auditlanadi.

### FR-4 — Idempotency and retries

Har bir delivery/write action destination, event va operation key bilan
deduplicate qilinadi. Retry exponential backoff bilan bo‘ladi; partial failure
foydalanuvchiga aniq ko‘rsatiladi.

### FR-5 — Telegram UX

Xabarlar sodda o‘zbek tilida, qisqa, severity va keyingi qadam bilan keladi.
Har bir tugma approval, detail, mark-read yoki source link vazifasini aniq
ko‘rsatadi.

## 10. Non-functional requirements

- 24/7 production runtime Oracle VM yoki tasdiqlangan serverda.
- `/healthz` liveness, `/readyz` dependency readinessni ajratadi.
- Userbot faqat server runtime’da; lokal mashina session egasi emas.
- Secrets chat, log, memory va auditga yozilmaydi.
- Sensitive data default mask qilinadi; public share private/no-store bo‘ladi.
- Har bir production write’dan keyin read-back verification.
- Python/TypeScript production implementatsiya fayllari 400 qatordan oshmaydi.
- Muhim operatsiyalar append-only audit log bilan kuzatiladi.

## 11. Success metrics

Metrikalar faqat real source ulanganida hisoblanadi:

1. Daily digest yetkazilishi: `>= 99%` successful scheduled runs.
2. Actionable alert precision: owner “actionable” deb belgilagan alertlar ulushi.
3. Missed follow-up kamayishi: baseline bilan taqqoslanadi.
4. Lead response SLA: source timestamplari mavjud bo‘lsa.
5. Project deadline risklari: owner tasdiqlagan va vaqtida yopilgan risklar.
6. Finance reconciliation: source’dagi verified recordlar bilan moslik.
7. Data trust: unavailable source holatlarida fake zero/reportlar soni `0`.
8. Write safety: verified write-back ulushi `100%`.

## 12. Release phases

### Phase 0 — Foundation

Runtime health, connector contracts, source status, evidence envelope, audit,
approval boundary va Telegram delivery.

### Phase 1 — Owner cockpit

Command Center, sales today, project risks, finance risks, team capacity va
daily digest.

### Phase 2 — Sales execution

AmoCRM hygiene, deduplication, follow-up tasks, lead scoring, stuck-stage va
SLA alerts.

### Phase 3 — Delivery and finance

Project board, Drive links, payment/debt signals, margin visibility va
quarterly operational review.

### Phase 4 — Conversation intelligence

Call ingestion, transcription, rubric, coaching, Telegram context va SalesCoach
dashboard.

### Phase 5 — Productization

Multi-business isolation, configurable schemas, tenant-level policies, billing
va boshqa branding agentliklari uchun onboarding.

## 13. Acceptance criteria

- Owner `/command_center` orqali sales, project, finance, team va health signalini ko‘radi.
- Har bir raqamning source va timestampi bor; source unavailable bo‘lsa “Ma’lumot ulanmagan” chiqadi.
- Bugungi sales priority real AmoCRM leadlaridan tuziladi va duplicate/stuck sababini ko‘rsatadi.
- Project riskida deadline, owner, stage va evidence record mavjud.
- Finance riski taxminsiz, faqat verified source fieldlaridan hisoblanadi.
- Approved AmoCRM task/note yoziladi va read-back bilan tasdiqlanadi.
- Bir xil event ikki marta Telegramga yuborilmaydi.
- Daily digest dependency health buzilganda noto‘g‘ri “100%” yoki fake zero yubormaydi.
- Har bir tashqi mutation audit iziga ega.
- Production deploydan oldin `pytest -q`, `bandit -r src/ -ll` va tegishli integration checks o‘tadi.

## 14. Open decisions

- Birinchi public product surface: Telegram-first yoki web Command Center-first.
- Project source sifatida Airtable va Sheets o‘rtasidagi canonical tanlov.
- Finance uchun Hisobchi API/Sheets contractining yakuniy field mappingi.
- Multi-tenant model va billing faqat Phase 5’da tasdiqlanadi.
- AI inference provider, retention muddati va audio/transcript o‘chirish siyosati.

## 15. Risks and mitigations

| Risk | Mitigation |
| --- | --- |
| Connector downtime | Source health, retry, unavailable state, no fake numbers |
| Duplicate write/delivery | Idempotency key, atomic claim, read-back verification |
| AI hallucination | Evidence envelope, confidence, source-limited prompts |
| Secret/session leakage | Secret store, masked logs, no chat/memory persistence |
| Over-automation | Approval plan and policy-based safe actions |
| Monolithic code growth | 400-line limit, SRP modules, facade pattern |
| Conflicting data sources | Canonical source map and reconciliation alerts |

## 16. First implementation backlog

1. Freeze connector capability/status contract.
2. Finalize `/api/oisha/command-center` response schema.
3. Add evidence envelope to all command-center cards.
4. Verify live AmoCRM, project and finance field mappings.
5. Add durable per-destination idempotency store.
6. Build Telegram digest with source-health guard.
7. Add owner approval plan and append-only audit path.
8. Run live-source acceptance test and record evidence.
