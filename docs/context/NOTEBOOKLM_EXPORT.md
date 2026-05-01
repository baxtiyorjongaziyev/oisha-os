# Oisha-OS — To'liq Tizim Tavsifi

> NotebookLM ga yuklash uchun. Oxirgi yangilash: 2026-04-26

---

## 1. Loyiha nima?

**Oisha-OS** — Jon Branding Agency uchun avtonomik AI operatsion tizim.
Kod nomi: "Surgical COO" — savdo jarayonini boshqaradi, AmoCRM bilan ishlaydi,
Telegram orqali jamoa bilan muloqot qiladi.

**Texnologiyalar:**
- Python 3.12 + FastAPI + asyncio
- Telethon (userbot) + aiogram (admin bot)
- Google Gemini 1.5 Flash/Pro
- AmoCRM v4 REST API
- Turso (libsql) + SQLite fallback
- Google Cloud Run (deploy)

---

## 2. Agentlar tizimi

| Agent | Fayl | Vazifa |
|---|---|---|
| MessageController | controllers/message_controller.py | Telegram xabarlarini yo'naltiradi |
| AdvisorAgent | services/core/advisor_agent.py | Real-vaqt savdo maslahat |
| AutoLeadAgent | services/core/auto_lead_agent.py | Avtonomik lead boshqaruvi |
| AuditAgent | services/core/audit_agent.py | Jamoa audit |
| EnterpriseReporter | services/core/enterprise_reporter.py | Kunlik hisobotlar |
| SalesCoach | services/core/sales_coach.py | Savdo trening |
| CRMGuard | services/core/crm_guard.py | CRM intizom |

**Agent loop:**
```
Vazifa → Planner (Gemini) → Executor (tools) → Verifier → Audit log
```

---

## 3. OpenClaw integratsiyasi

OpenClaw — 20+ kanaldan (WhatsApp, Telegram, Slack, Discord, Signal...) 
xabarlarni bir gateway orqali qabul qiladi.

**Arxitektura:**
```
Har qanday kanal → OpenClaw → Oisha-OS API → AgentOrchestrator → Gemini
```

**Endpoints:**
- `POST /webhook/openclaw` — HMAC-SHA256 xavfsiz, kanal xabarlarini qabul qiladi
- `POST /v1/chat/completions` — OpenAI-compatible, OpenClaw model backend sifatida
- `GET /v1/models` — mavjud agentlar ro'yxati
- `GET /webhook/openclaw/health` — health check

**Kanal ID mapping:**
- telegram: 0 + sender_id
- whatsapp: 1,000,000,000 + hash
- slack: 2,000,000,000 + hash
- discord: 3,000,000,000 + hash

---

## 4. Deployment

**Infra:**
- Google Cloud Run: `oisha-master-bot` | `europe-west3`
- GCP Project: `jonbranding-85662071-ea38e`
- Min instances: 1, Max: 1, RAM: 4Gi, CPU: 2

**CI/CD:**
- GitHub Actions: push to `main` → test → build → deploy
- Secrets: GCP Secret Manager orqali

**Userbot holati:**
- `ENABLE_CLOUD_USERBOT=True` — Cloud Run da ishlaydi
- `USERBOT_SESSION_STRING` — Telethon StringSession (DC2)

---

## 5. Muhim fayllar

```
src/main.py              — Entry point, barcha agentlar va Telegram client
src/api_server.py        — FastAPI: webhook, OpenAI endpoint, health
src/openclaw_bridge.py   — OpenClaw ↔ Oisha bridge
src/settings.py          — Pydantic settings
src/database.py          — Turso/SQLite singleton
.github/workflows/deploy.yml — CI/CD pipeline
deploy/openclaw/         — OpenClaw config va workspace
```

---

## 6. Biznes kontekst

- **Mijoz**: Jon Branding Agency (Toshkent)
- **Maqsad**: Savdo jarayonini avtomatlash, lead yo'qotmaslik
- **Asosiy kanal**: Telegram (userbot + bot)
- **CRM**: AmoCRM — lead yaratish, holat yangilash, deal kuzatuvi
- **Tillar**: O'zbek, Rus, Ingliz

**Asosiy muammo hal qilindi:**
Har bir kanaldan (WhatsApp, Telegram, Slack) kelgan mijoz xabari bitta AI agentga
yo'naltiriladi → CRM ga tushadi → jamoa xabardor bo'ladi.
