# Oisha-OS CAPI Platform — Product Requirement Document (PRD)

> **Hujjat holati:** Tasdiqlangan / Arxitektura va Hardening joriy qilingan  
> **Versiya:** 1.0.0-PROD  
> **Mualliflar:** Antigravity (Surgical Lead) × Codex (Harness Lead) × Claude Code (Security Reviewer) × Baxtiyorjon Gaziyev (Owner)  
> **Sana:** 2026-10-14  
> **Maqsad:** Tashqi SaaS xizmatlariga (AdSinc, capip.uz) bog'liqlikni va oylik obuna xarajatlarini to'liq yo'qotish, mijozlar ma'lumotlari (PII) maxfiyligini 100% in-house saqlash, JonBranding veb-sayti va amoCRM savdo voronkasini Meta Conversions API (CAPI) orqali Meta Dataset (Pixel) bilan bevosita va kafolatli bog'lash.

---

## 1. Dunyo va Mahalliy Bozor Tahlili (CAPI Benchmarking)

### 1.1. Dunyodagi Eng Zo'r CAPI Platformalari

| O'rin | Platforma | Asosiy Kuchi | Event Match Quality (EMQ) | Narxi / Arzonligi | Kimlar uchun mos? |
|---|---|---|---|---|---|
| **#1 (eCommerce)** | **Elevar** | Shopify & D2C uchun dunyo oltin standarti. Server-side data layer, to'liq avtomatlashtirilgan Meta Business Partner integratsiyasi. | 9.2 – 9.8 / 10 | $150 – $1,000+/oy | Katta e-commerce brendlar, Shopify do'konlar |
| **#1 (Infratuzilma)** | **Stape.io** | Server-side Google Tag Manager (sGTM) hosting va to'g'ridan-to'g'ri CAPI gateway. Global anycast CDN, cookieless tracking, multi-platform (Meta, TikTok, Pinterest, Google). | 8.8 – 9.5 / 10 | $20 – $100/oy (yoki bepul tier) | Dasturchilar, texnik marketologlar, agentliklar |
| **#1 (Enterprise CDP)** | **Segment (Twilio) / RudderStack** | Customer Data Platform (CDP). Barcha touchpoint'lardan (web, app, CRM, POS) yagona Customer ID yaratish va Meta CAPI ga real vaqtda stream qilish. | 9.0 – 9.6 / 10 | $120 – $2,000+/oy | Katta korporatsiyalar, omnichannel bizneslar |
| **#1 (Edge Tracking)** | **Blotout (EdgeTag)** | Brauzer cheklovlari (iOS 14.5+, Safari ITP, AdBlockers)ni to'liq chetlab o'tuvchi Edge-compute arxitekturasi. 1st-party cookie va cookieless ID resolution. | 9.4 – 9.9 / 10 | $199+/oy | Ma'lumot yo'qotilishiga toqat qilolmaydigan brendlar |
| **#1 (ROAS & AI)** | **Triple Whale / ConvertedIn** | Reklama byudjeti optimizatsiyasi, multi-touch attribution va offline-to-online conversion modeling. | 8.7 – 9.3 / 10 | $300 – $1,500+/oy | Skalirlanuvchi reklama beruvchilar |

---

### 1.2. Mahalliy Bozor Tahlili: AdSinc.uz va CAPI Platform (capip.uz)

#### A. capip.uz (CAPI Platform)
* **Funksionallik va Interfeys:**
  * **Ulanishlar (Connections):** Meta Pixel/Dataset ID, Meta Access Token, Test Event Code kiritish formasi. amoCRM webhook ulash va voronkadagi statuslarni moslashtirish (Masalan: "Yangi lid" → Lead, "Kvalifikatsiya" → QualifiedLead, "Sotuv/Muvaffaqiyatli" → Purchase).
  * **Hisobot va Attribyutsiya Jadvali:** 27 ta tanlanadigan ustunli jadval (Kompaniya, Reklama guruhi, Reklama nomi, Xarajat, Lidlar soni, Lid narxi (CPL), Sotuvlar, Daromad, ROAS, va h.k.).
  * **Eventlar Jurnali (Logs):** Yuborilgan eventlar, Meta javob kodi, xatoliklar matni.
* **Kamchilik va Zaifliklari:**
  * Ma'lumot ulanmagan yoki nol bo'lsa ham "0" ko'rsatib chalg'itadi (haqiqatda "ulanish yo'q" deb ajratilishi kerak).
  * Xatoliklarni avtomatik qayta ishlash (durable lease va backoff) tizimi shaffof emas.
  * Mijoz telefon raqamlari va ma'lumotlari uchinchi tomon serveriga shifrlanmagan/xom holda borib tushadi.

#### B. adsinc.uz (AdSinc)
* **Funksionallik va Narx:**
  * CRM Attribution xizmati: har bir loyiha uchun oylik **240 000 so'm** to'lov talab qiladi.
  * Bitrix24 va amoCRM integratsiyalari, Pixel bridging.
* **Kamchilik va Zaifliklari:**
  * JonBranding kabi o'z server infratuzilmasiga (Oracle VM, Turso DB, Oisha-OS) ega agentlik uchun har oy chetdan 240,000 so'm to'lash mutlaqo iqtisodiy samarasiz.
  * Platforma yopiq kodli, serverlar kechikishi (latency) Meta talablariga mos kelmasligi mumkin.

---

## 2. Oisha-OS CAPI Platformasi — Maqsad va Maxsus Ustunliklar

Oisha-OS CAPI platformasi JonBranding uchun quyidagi eksklyuziv ustunliklarni beradi:
1. **$0 Oylik Xarajat:** AdSinc yoki capip.uz ga har oy to'lanadigan obuna narxi 0 ga teng.
2. **Nol Ma'lumot Sizishi (Zero PII Leakage):** Mijozning ismi, telefoni va emaili tashqi SaaS'larga chiqmaydi. Oisha-OS qabul qilgan zahoti SHA-256 bilan xeshlangan holda saqlaydi va Meta'ga uzatadi.
3. **Sayt + amoCRM Yagona Gibrid Voronkasi:**
   * **Saytdan:** PageView, ViewContent, Lead (forma to'ldirilganda, brauzer Pixel `eventID` bilan deduplikatsiyalangan holda).
   * **amoCRM'dan:** QualifiedLead (menejer kvalifikatsiya qilganda), Purchase (to'lov tushib bitim yopilganda, real narx va valyuta bilan).
4. **Durable Lease & Exponential Backoff:** Agar Meta API ishlamay qolsa yoki tarmoq uzilsa, birorta ham konversiya yo'qolmaydi — Oisha navbatda saqlab, 10 daqiqadan so'ng atomik qayta urinadi.
5. **Harness Loop Engineering:** Har bir event turi, xavfsizlik cheklovlari va transport qabul qilinishi unit, integratsiya va regression testlar bilan kafolatlangan.

---

## 3. Tizim Arxitekturasi va Detsentralizatsiyalangan Ma'lumot Oqimi

```mermaid
flowchart TD
    subgraph Browser ["Mijoz Brauzeri (Client-Side)"]
        A1["Foydalanuvchi Saytga Kiradi"] --> A2["Meta Pixel (Browser SDK)"]
        A2 -->|Generates event_id| A3["Pixel Lead Event (event_id: JB-xxx)"]
        A3 -->|Direct HTTP| MetaPixel["Meta Servers (Pixel)"]
        A1 -->|Form Submit| WebServer["JonBranding Web Server (Next.js)"]
    end

    subgraph WebBackend ["JonBranding Web Backend"]
        WebServer -->|Attaches event_id & Consent| B1["oisha-capi-delivery.ts"]
        B1 -->|POST /api/marketing/capi/events<br/>Bearer OISHA_CAPI_INGEST_SECRET| OishaIngest["Oisha Ingest Endpoint"]
    end

    subgraph OishaPlatform ["Oisha-OS CAPI Platform (Local/Internal)"]
        OishaIngest --> AuthCheck{"Ingest Token &<br/>Source == website?"}
        AuthCheck -->|No| Reject403["403 Forbidden"]
        AuthCheck -->|Yes| PIIHash["Hash phone/email with SHA-256"]
        PIIHash --> ConflictCheck{"event_id mavjudmi?"}
        ConflictCheck -->|Aynan bir xil| ReturnDup["202 Accepted (duplicate)"]
        ConflictCheck -->|Boshqa ma'lumot| Raise409["409 Conflict (event_id_conflict)"]
        ConflictCheck -->|Yangi| EnqueueDB["Durable Store (capi_platform_events)<br/>status='queued'"]
        
        AmoWebhook["amoCRM Status Webhook"] -->|Status 142 / Qualified| AmoCapiTrigger["meta_capi_triggers.py"]
        AmoCapiTrigger -->|Internal System Call| AmoCapiSender["meta_capi.py"]
        
        Scheduler["Background Worker (Every 30s)"] --> DispatchDue["platform.dispatch_due()"]
        EnqueueDB --> DispatchDue
        DispatchDue --> AtomicClaim["Atomic Lease Claim (status='pending')"]
        AtomicClaim --> MetaSender["Meta Graph API v21.0 Sender"]
    end

    subgraph MetaGraph ["Meta Graph API Servers"]
        MetaSender -->|POST /{DATASET_ID}/events| MetaAPI["Meta Conversions API"]
        MetaAPI --> ResponseCheck{"Meta Response"}
        ResponseCheck -->|events_received == 1| AckSent["Mark status='sent'"]
        ResponseCheck -->|HTTP 4xx Permanent| AckRejected["Mark status='rejected' (Terminal)"]
        ResponseCheck -->|HTTP 5xx / Network Timeout| AckRetry["Mark status='failed'<br/>Backoff Retry (1..60 min)"]
    end

    AckSent --> OishaPlatform
    AckRejected --> OishaPlatform
    AckRetry --> OishaPlatform
```

---

## 4. Harness Loop Engineering (Tekshiruv va Invariantlar Standarti)

Oisha-OS CAPI platformasi Harness Loop Engineering tamoyillari asosida qurilgan:

### 4.1. Asosiy Invariantlar (Mathematical & Engineering Invariants)
1. **Invariant 1 (Source Isolation):** Veb-sayt ingest tokeni (`OISHA_CAPI_INGEST_SECRET`) orqali faqat `source="website"` eventlari qabul qilinadi. Sayt kaliti bilan CRM sotuv (`Purchase`) yoki boshqa CRM eventlarini soxtalashtirish mutlaqo imkonsiz (HTTP 403 bilan to'xtatiladi).
2. **Invariant 2 (Idempotent Integrity):** Bir xil `event_id` qayta yuborilsa, u faqat avvalgi payload bilan 100% bir xil bo'lgandagina qabul qilinadi (`duplicate`). Agar xuddi shu `event_id` bilan boshqa foydalanuvchi yoki o'zgargan qiymat kelsa, qat'iy `ValueError("event_id_conflict")` (HTTP 409) qaytariladi.
3. **Invariant 3 (Terminal vs Retriable States):** Meta Graph API dan HTTP 4xx (400, 403, 404 - xato token, noo'rin payload) xatosi kelsa, u terminal `rejected` statusiga o'tadi va qayta behuda navbatga qo'yilmaydi. Faqat tarmoq va server xatolari (HTTP 5xx, timeout) eksponensial kechikish bilan qayta uriniladi.
4. **Invariant 4 (CSRF & Cookie Mutation Guard):** Barcha cookie (`oisha_token`) orqali amalga oshiriladigan mutatsiyalar (`POST /dispatch`, `POST /crm/.../retry`) so'rovda to'g'ri `Origin` sarlavhasini talab qiladi. Cross-origin yoki originsiz cookie so'rovlari 403 bilan rad etiladi.
5. **Invariant 5 (Transport vs Attribution Non-Hallucination):** Meta faqat `events_received: 1` javobini bergandagina event `sent` deb belgilanadi. Bu Meta'ga yetkazilganini bildiradi, lekin reklama attribyutsiyasini yoki savdo o'sishini uydirib ko'rsatmaydi.
6. **Invariant 6 (Privacy & Zero PII Leak):** Operator konsoli, API statusi va xatoliklar loglarida foydalanuvchining telefon raqami, emaili yoki Meta Access Token ko'rinmaydi.

---

## 5. API Spetsifikatsiyalari va Ma'lumotlar Shartnomasi

### 5.1. Saytdan Event Qabul Qilish (Intake)
* **Endpoint:** `POST /api/marketing/capi/events`
* **Sarlavha:** `Authorization: Bearer <OISHA_CAPI_INGEST_SECRET>`
* **Status kodi:** `202 Accepted` (navbatga olindi)
* **Maksimal tana hajmi:** 16 KiB
* **Payload namunasi (Lead):**
```json
{
  "source": "website",
  "event_name": "Lead",
  "event_id": "jb-form-1713098400-user42",
  "event_time": 1713098400,
  "event_source_url": "https://jonbranding.uz/contact",
  "client_user_agent": "Mozilla/5.0 ...",
  "phone": "+998901234567",
  "email": "mijoz@example.uz",
  "fbp": "fb.1.1713098000.1234567890",
  "fbc": "fb.1.1713098000.IwAR0...",
  "consent": true
}
```

### 5.2. CRM Sotuv Eventi (Purchase)
* **Tranzaksiya:** amoCRM da bitim statusi `#142` ("Muvaffaqiyatli yakunlandi") ga o'tganda.
* **Qoidalar:** 
  * `value` — amoCRM dagi haqiqiy bitim byudjeti (musbat son).
  * `currency` — `UZS` (yoki sozlangan valyuta).
  * `leadgen_id` — Meta Lead Ads ID (mavjud bo'lsa).
  * `event_id` formati: `crm-<leadgen_id>-Purchase`.

---

## 6. Bajarilgan Ishlar va Sinov Dalillari (Evidence)

1. **Yaratilgan/Mustahkamlangan Modullar:**
   * `src/services/core/marketing/capi_platform.py` — Asosiy orkestratsiya, dispatch va terminal rejection logikasi.
   * `src/services/core/marketing/capi_platform_store.py` — Atomik lizing, event conflict tekshiruvi va SQLite/Turso durable queue.
   * `src/services/core/marketing/capi_platform_schema.py` — Pydantic V2 qat'iy validatsiyasi, xeshlash va URL tozalash.
   * `src/api/routes/capi_platform.py` — Himoyalangan endpointlar, CSRF origin tekshiruvi, RBAC va fon worker lifespan'i.
   * `src/api/templates/capi_platform.html` — Oisha ichki boshqaruv konsoli (Status, Dataset, Eventlar oqimi).
2. **Tekshiruv Dalillari:**
   * `tests/test_capi_platform.py`: 19 ta unit va integratsiya testi 100% yashil.
   * `tests/test_capi_platform_hardening.py`: 4 ta Claude Code xavfsizlik ssenariysi 100% yashil.
   * `tests/test_meta_capi.py`: 18 ta CRM integratsiya testi 100% yashil.
   * **Jami:** 41 ta CAPI testi to'liq o'tdi (1.74 soniyada).
   * **Bandit:** 0 ta xavfsizlik zaifligi (`No issues identified`).
   * **Ruff:** Barcha fayllar sintaksis va import qoidalari bo'yicha toza.
   * **Skills sinxronizatsiyasi:** `scripts/sync_agent_skills.py` orqali 13 ta agent skilli to'liq sinxronlandi.

---

## 7. Keyingi Bosqichlar (Production Rollout)

1. **Serverga Deploy:** `feat/capi-platform` branchini testlab, Oracle VM ga joylash.
2. **Meta Test Events Tekshiruvi:** Owner tomonidan `META_CAPI_TEST_EVENT_CODE` kiritilib, Meta Events Manager "Test Events" bo'limida birinchi sinov eventini yuborish va qabul qilinganini jonli ko'rish.
3. **JonBranding Saytini Ulash:** `jonbranding-web` Vercel muhitiga `OISHA_CAPI_URL` va `OISHA_CAPI_INGEST_SECRET` kalitlarini o'rnatish.
