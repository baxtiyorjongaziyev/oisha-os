# 🗺️ Oisha-OS — Road Map

> **Vazifa**: Jon Branding agentligi uchun 24/7 avtonom AI operatsion tizim.
> Telegram userbot + AI agent + CRM integratsiya + ichki jamoaviy boshqaruv.
> **Deploy**: Google Cloud Run (`oisha-master-bot` · `europe-west3`)

---

## ✅ Hozirgi holat (Bajarilgan)

### Core Infrastructure
| Komponent | Holat |
|---|---|
| Telethon Userbot (24/7) | ✅ Cloud Run'da ishlamoqda |
| Aiogram Bot | ✅ Ishlamoqda |
| FastAPI health server (`/health`) | ✅ Ishlamoqda |
| Turso (libSQL) database | ✅ Ulangan |
| GCS (Google Cloud Storage) session persistence | ✅ Sozlangan |
| GitHub Actions CI/CD | ✅ Auto-deploy `main` → Cloud Run |

### AI & Agents
| Komponent | Holat |
|---|---|
| Gemini AI Router | ✅ `src/agents/ai_router.py` |
| Sales Agent | ✅ `src/agents/sales_agent.py` |
| Negotiation Engine | ✅ `src/agents/negotiation_engine.py` |
| Persona Hub (Oisha persona) | ✅ `src/services/core/persona_hub.py` |
| Lead Operating System (LOS) | ✅ `src/services/core/lead_operating_system.py` |
| Auto Reply Gate (shadow mode) | ✅ `src/services/core/auto_reply_gate.py` |
| Mission Control | ✅ `src/services/core/mission_control.py` |
| Proactive Worker | ✅ `src/services/core/proactive_worker.py` |

### CRM & Integrations
| Komponent | Holat |
|---|---|
| AmoCRM sink (leads, contacts, notes) | ✅ Ulangan |
| Airtable sync (loyihalar) | ✅ Ulangan |
| Google Drive (fayllar) | ✅ Ulangan |
| Google Sheets | ✅ Ulangan |
| Google Calendar | ✅ Ulangan |
| Enterprise Reporter | ✅ Telegram cockpit report |

---

## 🔜 Keyingi bosqich (Phase 2)

### 🧠 AI Chuqurlashish
- [ ] **Chat summarization (Infinite Memory)** — Kontekstni cheksiz uzaytirish uchun rekursiv xulosa
- [ ] **Airtable summary sync** — AI yaratgan xulosaларni Airtable'da ko'rsatish
- [ ] **Lead scoring avtomatlashtirish** — VIP_LEAD_SCORE_THRESHOLD = 80 logikasini kengaytirish
- [ ] **Auto-reply production mode** — `shadow` → `active` rejimga o'tish (test qilib bo'lgach)

### 📊 Monitoring & Analytics
- [ ] **BigQuery integration** — `scripts/bq/schema.sql` tayyor, pipeline kerak
- [ ] **Dashboard** — Cloud Run metrics + lead stats bitta joyda
- [ ] **SLA Monitor yaxshilashtirish** — Alert thresholds sozlash

### 🔧 AmoCRM Tozalash (Muhim!)
- [ ] **Lost leads o'chirish** — 501/500 limit muammosi (Authorization Code kerak)
- [ ] **File offloading** — 406MB/100MB disk muammosi → Google Drive'ga ko'chirish
- [ ] `crm_janitor.py` ishga tushirish
- [ ] `crm_file_offloader.py` ishga tushirish

### 🔐 Xavfsizlik
- [ ] **Userbot session yangilash** — Sessiya muddati tugaganda avtomatik refresh
- [ ] **Secret rotation** — GCP Secret Manager versiyalarini boshqarish

---

## 🛠️ Qaysi vositada qaysi vazifa

| Vazifa | Asbob |
|---|---|
| Yangi servis yoki agent yozish | **Google AI Studio** (bepul, Gemini 3 Pro) |
| CI/CD, infra, deploy bug | **Antigravity** (bu yerda) |
| AmoCRM debug, CRM tozalash | **Antigravity** — debug skriptlar |
| Log tahlili, error tracing | **Antigravity** + GCP Logs Explorer |
| Kontent (Oisha persona, xabarlar) | **To'g'ridan-to'g'ri fayl tahrir** |

---

## 📐 Arxitektura

```
src/
├── main.py                    # Asosiy kirish nuqtasi (Telethon + Aiogram)
├── api_server.py              # FastAPI (/health, /webhook)
├── database.py                # SQLite + Turso (libSQL) wrapper
├── database_pool.py           # Connection pool
├── settings.py                # Pydantic settings
├── agents/
│   ├── ai_router.py           # Multi-model AI routing (Gemini, DeepSeek)
│   ├── core.py                # Agent base class
│   ├── orchestrator.py        # Agent koordinatsiya
│   ├── sales_agent.py         # Sotuvchi agent
│   └── negotiation_engine.py  # Muzokara logikasi
├── services/core/             # 50+ servis (CRM, AI, monitoring)
│   ├── persona_hub.py         # Oisha persona boshqaruvi
│   ├── lead_operating_system.py # LOS — markaziy lead boshqaruvi
│   ├── auto_reply_gate.py     # Shadow/active auto-reply
│   ├── mission_control.py     # Jamoaviy vazifalar
│   ├── proactive_worker.py    # Background proactive outreach
│   └── enterprise_reporter.py # Cockpit report generator
├── services/debug/            # Diagnostika va tozalash skriptlari
│   ├── crm_janitor.py         # AmoCRM lead tozalash
│   ├── crm_file_offloader.py  # Fayllarni Drive'ga ko'chirish
│   └── get_amocrm_token.py    # Token yangilash
└── controllers/               # Telegram message handler
```

## 🔑 Muhit

```
Cloud Run Service:  oisha-master-bot
Region:             europe-west3
Project:            jonbranding-85662071-ea38e
Database:           Turso (libSQL) — oisha-os-db
GCS Bucket:         session persistence
Secrets (GCP):      BOT_TOKEN, API_ID, API_HASH, GEMINI_API_KEY, ...
```
