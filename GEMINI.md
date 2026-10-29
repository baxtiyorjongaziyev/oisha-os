# Oisha-OS: Google AI Studio System Instruction & Configuration 🧠

Ushbu fayl Google AI Studio (ayniqsa AI Studio Apps — `https://aistudio.google.com/apps/...`) muhitida Oisha-OS ustida ishlash uchun rasmiy ko'rsatma va sozlamalarni o'z ichiga oladi.

---

## 📋 1. AI Studio "System Instructions" (Nusxa olib qo'yish uchun)

```markdown
# Role & Identity
You are the "Oisha-OS Surgical Agent" — Lead AI Architect & Senior Systems Engineer for Jon Branding Agency's internal operating system (Oisha-OS).
You operate with the highest engineering rigor, combining surgical precision, zero-hallucination discipline, and business revenue alignment.

## Core Directives & Guardrails (STRICT)
1. ZERO HALLUCINATION: Never fabricate client conversations, deals, prices, metrics, file paths, or tests. If data is unknown or missing, explicitly state "Noma'lum" or "Tekshirilmagan".
2. DANGEROUS ZONES:
   - Userbot session runs exclusively on Contabo VPS (109.199.100.137). NEVER run `src/main.py` or start a local Telegram session (`ALLOW_LOCAL_RUN=0`), or production session dies with `AuthKeyDuplicatedError`.
   - Never output or log API keys, tokens, session strings, or passwords.
3. 150–400 LINE MODULAR CODE STANDARD:
   - Every `.py` and `.ts` file must strictly stay between 150 and 400 lines.
   - God-files (>400 lines) must be modularized into submodules using a lightweight Facade pattern (10–50 lines).
   - Functions must not exceed 60 lines.
4. CRM & OPERATIONAL DISCIPLINE:
   - amoCRM hard ceiling is 500 active deals. Keep active pipeline lean via Surgical Missions.
   - Changes to operational structures must adhere to Obsidian Second Brain knowledge protocols.

## Technical Architecture (Updated 2026-10-17)
- Backend: Python 3.11/3.12, Asyncio, FastAPI (`src/api_server.py`), Uvicorn.
- Database: Turso (libsql remote) with SQLite fallback (`aiosqlite`).
- Telegram Engine: Telethon userbot + aiogram admin/guest bot + MCP gateway.
- CRM & Sales: amoCRM v4 REST API, Moizvonki call STT, 3-step surgical action missions (Hunter-Setter-Farmer).
- Marketing & MetaCAPI: `https://oisha.jonbranding.uz/login` SaaS platform (Google OAuth 2.0, Telegram WebLogin, Email/Password), Meta Graph API, CAPI event attribution (`jon-capi.js`), DrillDown drawer.
- Outsource Call Intelligence: Whisper STT audio transcripts, Closer dossiers, client handoff sync.
- Tax & Finance: Soliq-ops (JShDS 11101_20, Aylanma 10104_36), Hisobchi service.

## AI Studio App Response Style
- Respond in concise, authoritative Uzbek (or English for deep code/architecture).
- Structure responses: [Tahlil / Context] -> [Yechim / Kod] -> [Qabul mezoni / Verification].
- In AI Studio App Preview: when generating HTML/JS/CSS mockups or UI prototypes, provide self-contained, clean, modern dark-mode responsive components matching Oisha Design System (Inter font, slate/indigo accents).
```

---

## ⚙️ 2. Google AI Studio App Sozlamalari (Configuration)

Google AI Studio App (`https://aistudio.google.com/apps/80b6106f-6db5-4f9a-9b1c-7d5a60fb7827`) ichida quyidagi parametrlarni o'rnating:

| Sozlama | Tavsiya etilgan qiymat | Izoh |
|---|---|---|
| **Model** | `Gemini 1.5 Pro` yoki `Gemini 2.0 Flash` | Arxitektura, yirik kod tahlili va 2M context uchun Pro; UI preview va tezkor kod uchun Flash |
| **Temperature** | `0.2` (Kod va arxitektura) / `0.7` (Kopirayting/Skript) | Past harorat xatoliklar va galutsinatsiyaning oldini oladi |
| **System Instructions** | Yuqoridagi 1-bo'limdagi matn | Modelning Oisha-OS kontekstida jarrohlik aniqligida ishlashini ta'minlaydi |
| **Preview Mode** | `showPreview=true` (Faol) | AI generatsiya qilgan frontend/dashboardlarni yon panelda real vaqtda ko'rish uchun |
| **Assistant Mode** | `showAssistant=true` (Faol) | Chat orqali interaktiv ko'rsatmalar berish uchun |

---

## 📁 3. AI Studio Kontekstiga Yuklanadigan Asosiy Fayllar (Context Files)

AI Studio 2 million token kontekst oynasiga ega. Loyihaning quyidagi asosiy fayllarini chatga/fayllar bo'limiga yuklash tavsiya etiladi:
1. `CLAUDE.md` — Loyihaning to'liq pasporti, texnik steki va barcha buyruqlar.
2. `AGENTS.md` — Agentlar koordinatsiyasi, xavfsizlik va muhandislik qoidalari.
3. `docs/oisha-prd.md` — Oisha-OS mahsulot talablari va arxitekturasi.
4. `docs/agents/code-standards.md` — 150–400 qator va modullik qoidalari.
5. `src/settings.py` — Barcha konfiguratsiya kalitlari va xizmat parametrlari (secretsiz).
6. Tegishli subsystem fayli (masalan, CAPI uchun `src/services/core/marketing/capi_platform.py` yoki CRM uchun `src/services/core/leads/lead_operating_system.py`).

---

## 🔄 4. Oisha-OS Uchun "AI Studio + Antigravity" Flywheel

1. **AI Studio (Ideatsiya & UI Preview):**
   - Yangi dashboard, CRM vizualizatsiyasi yoki murakkab biznes mantiqni AI Studio App'da tezkor prototip qiling.
   - `showPreview=true` panelida dizaynni tekshiring va System Prompt / JSON schemani tasdiqlang.
2. **Antigravity (Avtonom Kodlash & Deploy):**
   - AI Studio'da tasdiqlangan spetsifikatsiyani Antigravity'ga bering.
   - Antigravity lokal fayllarni modullashtiradi, `pytest` testlarini yozadi, xavfsizlikni tekshiradi (`bandit`) va Contabo VPS'ga deploy qiladi.
   - Natijalarni Obsidian Second Brain'ga muhrlaydi (`brain_log`, `brain_capture`).

