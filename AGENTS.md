# Oisha-OS Agent Coordination Protocol

> Barcha AI agentlar ish boshlashdan oldin bu faylni o'qiydi va tugatgandan keyin yangilaydi.

## Communication Rules

1. **Bir faylga bir vaqtda faqat bitta agent yozadi**
2. **Agent ish boshlaganda `## Locks` ga o'z nomini yozadi, tugatganda o'chiradi**
3. **Shared fayllarga (settings.py, context.py, boot.py) faqat Agent Coordinator yozadi**
4. **Har bir PR dan oldin `pytest -q` va `bandit -r src/ -ll` ishga tushiriladi**
5. **git commit → git push → keyin keyingi agent pull qiladi (rebase)**

## Roles

| Agent | Scope | Owner |
|-------|-------|-------|
| **Coordinator** | AGENTS.md, settings.py, context.py, boot.py, PR merge | @user |
| **Parser** | main.py → handlers/, commands/, schedulers/ | — |
| **Hisobchi** | hisobchi_engine.py, hisobchi_handlers.py, hisobchi_schema.py | — |
| **Security** | tests/, bandit issues, exception handling | — |
| **Migration** | global variable → app_ctx.* | — |
| **Database** | database.py, migrations, SQL optimization | — |
| **API Server** | api_server.py, endpoints, auth | — |
| **Integration** | AmoCRM, Airtable, Telegram integrations | — |
| **Documentation** | README, API docs, inline docs | — |
| **Performance** | profiling, caching, optimization | — |
| **Code Quality** | dead code, naming, type hints | — |

## Current State

# Oisha-OS Agent Coordination Protocol

> Barcha AI agentlar ish boshlashdan oldin bu faylni o'qiydi va tugatgandan keyin yangilaydi.

## Communication Rules

1. **Bir faylga bir vaqtda faqat bitta agent yozadi**
2. **Agent ish boshlaganda `## Locks` ga o'z nomini yozadi, tugatganda o'chiradi**
3. **Shared fayllarga (settings.py, context.py, boot.py) faqat Agent Coordinator yozadi**
4. **Har bir PR dan oldin `pytest -q` va `bandit -r src/ -ll` ishga tushiriladi**
5. **git commit → git push → keyin keyingi agent pull qiladi (rebase)**

## Roles

| Agent | Scope | Owner |
|-------|-------|-------|
| **Coordinator** | AGENTS.md, settings.py, context.py, boot.py, PR merge | @user |
| **Parser** | main.py → handlers/, commands/, schedulers/ | — |
| **Hisobchi** | hisobchi_engine.py, hisobchi_handlers.py, hisobchi_schema.py | — |
| **Security** | tests/, bandit issues, exception handling | — |
| **Migration** | global variable → app_ctx.* | — |
| **Database** | database.py, migrations, SQL optimization | — |
| **API Server** | api_server.py, endpoints, auth | — |
| **Integration** | AmoCRM, Airtable, Telegram integrations | — |
| **Documentation** | README, API docs, inline docs | — |
| **Performance** | profiling, caching, optimization | — |
| **Code Quality** | dead code, naming, type hints | — |

## Current State

### Locked
*(none)*

### Done (Integration — Claude)
- salescoach-ai qayta yaratildi: MCP `server.ts`, `call-intel/*` (Fireflies+Gong → scoring queue, webhook secret bilan), `ServiceOrJwtAuthGuard` (calls+negotiations), worker `telegram_notify.ts`. API `tsc --noEmit` TOZA.
- oisha-os bridge (YANGI, shared emas): `salescoach_sync.py`, `apollo_enrich.py`, `docusign_sync.py` (DocuSign → **Telegram signing URL**, email'siz — UZ). app_ctx singleton COLLISION tuzatildi (uchchalasi `app_ctx.instance` edi → unikal nomlar).
- 5 agent MCP config ulandi (repo tashqarisida): Claude/Codex/Gemini/OpenCode/Antigravity-Cline → oisha-amocrm, oisha-telegram, salescoach-ai.
- ⚠️ **For Coordinator (settings.py ga qo'shing):** SALESCOACH_{API_URL,SERVICE_TOKEN,ENABLED}, DOCUSIGN_{ENABLED,BASE_URI,ACCOUNT_ID,ACCESS_TOKEN,TEMPLATE_ID}, APOLLO_{ENABLED,API_KEY}. Kod `getattr` bilan himoyalangan — varsiz ham ishlaydi (disabled).
- ⚠️ **Known issue:** worker `tsc` — ioredis dup (5.11.1 vs 5.10.1) pre-existing dep drift; mening kodim emas (telegram_notify.ts toza). `pnpm dedupe` kerak.

### Done (yangi)
- Pytest/Bandit pre-flight failurelari ideal PR holatiga keltirildi: OS driver unit testlari desktop dependencydan ajratildi, `SKIP_LIVE=1` live AI testlarga qo'llandi, OAuth helper import-safe qilindi va default `127.0.0.1` ga bind qiladi; regression testlar qo'shildi. Full pre-flight: 364 passed, 13 skipped; Bandit: no issues (Codex).
- Meta Graph API orqali Instagram DM va Comment webhooklari to'liq implement qilindi (`src/api_server.py` va `src/services/core/instagram_agent.py` yaratildi) hamda local va remote testlardan muvaffaqiyatli o'tdi (Antigravity).
- Webhook so'rovlarini `x-hub-signature-256` orqali xavfsiz tasdiqlash va background tasks orqali Meta timeoutlarining oldini olish yo'lga qo'yildi (Antigravity).
- Yangilangan kod remote Oracle VM ga deploy qilindi, uerdagi `oisha-os` systemd xizmati qayta ishga tushirilib, API server muvaffaqiyatli ishlayotganligi `/healthz/` orqali tasdiqlandi (Antigravity).
- `handle_new_message` event handler sifatida ro'yxatdan o'tkazildi
- Hisobchi AI: `init_hisobchi_tables()` boot.py da chaqiriladi
- Hisobchi AI: `_hisobchi_engine` global placeholder qo'shildi
- Masofaviy n8n da Google Gemini API orqali ishlaydigan bepul AI Chatbot workflow (ID: `xf2kLGu1vuXGM5cC`) to'liq sozlandi va faollashtirildi (Antigravity).
- n8n v1.0+ ga mos keladigan yangi connection formatiga (`ai_languageModel` porti) muvofiq Gemini ulanishlari to'g'rilandi.
- Gemini API ning `host` parametridagi protokol xatosi va `modelName` parametrining model mos kelmasligi (`gemini-2.5-flash` ga o'zgartirish orqali) hal qilindi.
- Chatbot webhook POST so'rovlari muvaffaqiyatli sinovdan o'tdi (Response: `{"output":"..."}`).
- database.py: f-string SQL -> parametrized query refactoring bajarildi (682 va 998 qatorlar, `upsert_user` va `get_storage_counts`). Bandit va pytest tekshiruvlaridan muvaffaqiyatli o'tdi (Antigravity).
- Web chat widgeti production xatoligi (FastAPI /api/chat/send va /api/chat/history API-dagi 422 xatoliklar) `X-Secret-Key` header qo'llab-quvvatlash orqali tuzatildi, barcha testlardan o'tdi va remote Oracle VM ga deploy qilinib muvaffaqiyatli ishga tushirildi (Antigravity).

### Next Tasks
1. [Done] `self_command_handler` (1000+ lines) → `src/commands/` ga ajratish
2. [Done] `except Exception: pass` larni tuzatish (~30+ joy `call_analyzer.py` da tuzatildi)
- Global → app_ctx.* migratsiyasi (Jarayonda)
- [Done] f-string SQL → parametrized query (database.py:682, 998)
- [Done] Handler lar: `src/handlers/` ga ajratish (negotiation, kirim, case_publisher, etc.)
- [Done] Turso DB schema migration for FrogAgent (added profit_estimate, source_manager, external_task_id, is_frog to tasks table) and fixed database_pool SQLite error handling.
- [Done] FrogAgent va FrogScheduler remote VM ga deploy qilinib muvaffaqiyatli ishga tushirildi. Har kuni 09:00 da Telegram orqali eng foydali vazifalar (Frog) ro'yxati yuboriladi.

### Dead Files (don't touch)
- `src/agents/` — autonomous AI agents, domain-specific, bu refactoringga kirmaydi
- `src/services/debug/` — tashqi debug tools
- `src/legacy/` — eski prototiplar

## Pre-flight Checklist (har bir PR dan oldin)
```powershell
$env:SKIP_LIVE=1; python -m pytest -q --tb=short
bandit -r src/ -ll
```

## Branch Naming
`feat/<short-description>` yoki `fix/<short-description>`

## Commit Style
`feat(scope): message` / `fix(scope): message` / `refactor(scope): message`

## 🚀 Oisha-OS Future Roadmap (Vision)
> Ushbu bo'lim Oisha-OS ning kelajakdagi arxitekturasini belgilaydi. Barcha agentlar kelgusida shu 4 ta yo'nalish bo'yicha ishlashga tayyor turishi kerak:

1. **🎙 AI Voice Agents** (`src/services/core/voice_agent.py`): AmoCRM webhook → Vapi.ai qo'ng'iroq → natijani AmoCRM ga yozish. `ENABLE_VOICE_AGENT=True` da ishlaydi.
2. **🪄 Edge AI Personalization** (`src/services/edge/edge_personalizer.py` + `apps/worker/src/edge_personalizer.ts`): Cloudflare Workers AI + GA4 segmentatsiya → vebsayt kontentini real-time moslash.
3. **📰 Avtomatlashtirilgan Case-Study Publisher** (`src/services/core/sanity_publisher.py`): AmoCRM'da loyiha yakunlanganda AI maqola → Sanity CMS → jonbranding.uz/cases/.
4. **🔮 Predictive LTV** (`src/services/core/ltv_predictor.py`, `ltv_trainer.py`): Scikit-Learn RandomForest + tarixiy AmoCRM data → yangi lead LTV → VIP alert.
5. **📦 Yangi modullar:**
   - `src/services/core/voice_agent.py` — Vapi.ai integratsiyasi
   - `src/services/core/sanity_publisher.py` — Sanity CMS ga avtopublish
   - `src/services/core/ltv_predictor.py` — LTV ML model
   - `src/services/core/ltv_trainer.py` — Avtomatik model train (00:30 da)
   - `src/services/edge/edge_personalizer.py` — Cloudflare segmentatsiya logikasi
   - `apps/worker/src/edge_personalizer.ts` — Cloudflare Worker script
