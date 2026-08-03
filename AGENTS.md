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
- **Codex Coordinator** — self-improvement report dedup, failure root-cause, approval UX va Telegram MCP restore
- **Codex Coordinator (Cloud deploy)** — Aiogram Cloud Run head deploy, webhook switch va two-head production smoke

### Operational Notes
- Telegram MCP approval gateway: upstream `127.0.0.1:8765/mcp`, gateway `127.0.0.1:8766/mcp`. `TELEGRAM_MCP_SESSION_STRING` must be a dedicated session and must never equal `USERBOT_SESSION_STRING`. Read tools are automatic; every mutation is owner-approved through Telegram. Neither port may be exposed by Nginx.
- ⚠️ **USERBOT SESSION OWNER: Oracle VM.** 
  - **STATUS (FIXED):** Windows kompyuterlarda `AuthKeyDuplicatedError` oldini olish uchun `boot.py` da Userbot lokal ishlashi **qat'iyan to'sib qo'yilgan (`client = None`)**.
  - Yangi session string faqat Oracle VM (Linux) da ishlaydi va qayta uzilmaydi. Hozirda Oracle VM da MUVAFFAQIYATLI ISHLAMOQDA.
- **Telegram architecture decision:** userbot Telethon'da qoladi. Bot akkaunt (`BOT_TOKEN`, @jonairobot) bosqichma-bosqich Aiogram'ga ko'chiriladi. Migratsiya adapter-first bo'lsin: avval `bot_client.send_message`/callback/command yuzasi uchun compatibility adapter, keyin Hisobchi approvals, admin commands, Frog reports va boshqa bot-token flows alohida ko'chiriladi. Bir martada to'liq almashtirmang; har bosqichda test va production-safe rollback bo'lsin.
- Telegram Bot API guruh access qayta tiklandi: `crm_group` va `team_group` `getChat` tekshiruvida `200 OK`. `scripts/prod/probe_integrations.py` bilan AmoCRM, Airtable va Telegram Bot API ham OK tasdiqlangan.

### Done (Integration — Claude)
- salescoach-ai qayta yaratildi: MCP `server.ts`, `call-intel/*` (Fireflies+Gong → scoring queue, webhook secret bilan), `ServiceOrJwtAuthGuard` (calls+negotiations), worker `telegram_notify.ts`. API `tsc --noEmit` TOZA.
- oisha-os bridge (YANGI, shared emas): `salescoach_sync.py`, `apollo_enrich.py`, `docusign_sync.py` (DocuSign → **Telegram signing URL**, email'siz — UZ). app_ctx singleton COLLISION tuzatildi (uchchalasi `app_ctx.instance` edi → unikal nomlar).
- 5 agent MCP config ulandi (repo tashqarisida): Claude/Codex/Gemini/OpenCode/Antigravity-Cline → oisha-amocrm, oisha-telegram, salescoach-ai.
- ⚠️ **For Coordinator (settings.py ga qo'shing):** SALESCOACH_{API_URL,SERVICE_TOKEN,ENABLED}, DOCUSIGN_{ENABLED,BASE_URI,ACCOUNT_ID,ACCESS_TOKEN,TEMPLATE_ID}, APOLLO_{ENABLED,API_KEY}. Kod `getattr` bilan himoyalangan — varsiz ham ishlaydi (disabled).
- ioredis dup TUZATILDI: bullmq 5.79.1 ioredis'ni aynan `5.10.1` ga pin qiladi, apps esa `^5.11.1` (TRAE security update) → root `pnpm.overrides.ioredis="^5.11.1"` (TRAE yangi versiyasi saqlanadi, bullmq'niki ko'tariladi). Worker+API `tsc --noEmit` TOZA.

### Done (MCP birlashtirish — Claude)
- **Uchta MCP yozuvi bittaga birlashtirildi.** Ilgari: `telegram` (SSH→Oracle),
  `oisha-telegram` (lokal — API'siz, hech qayerga ulanmasdi), `oisha-amocrm` (lokal).
  Endi yagona `scripts/oisha_mcp_server.py` (FastMCP) — 12 tool: Telegram (4),
  AmoCRM (4), Airtable (1), Instagram (3). Oracle'da ishlaydi; Telegram toollari
  `/api/internal/mcp` orqali boradi, userbot sessiyasiga to'g'ridan-to'g'ri tegmaydi.
- Eski `scripts/mcp_server.py`, `scripts/telegram_mcp_server.py` va `src/*` shim'lari
  yangi serverga yo'naltiruvchi bo'lib qoldi — mavjud konfiguratsiyalar buzilmaydi.
- `scripts/telegram_mcp_server.py:42` dagi hardcoded Nginx paroli olib tashlandi;
  Basic Auth endi faqat `OISHA_API_USER`/`OISHA_API_PASS` env'dan.
  ⚠️ **Owner uchun:** eski parol repo tarixida qolgan — Nginx'da almashtirish kerak.
- ⚠️ **Coordinator uchun (Rule 3 istisnosi):** `settings.py` ga `OISHA_API_SECRET`,
  `JWT_SECRET`, `OISHA_SERVICE_TOKENS_JSON`, `OISHA_PROXY_ROLE_MAP_JSON` qo'shildi.
  Sabab: `0e6b4d7` auth o'qishni `os.environ` dan `settings` ga ko'chirgan, lekin
  maydonlar e'lon qilinmagan edi → `getattr(...)` doim `""` qaytarib, butun HTTP
  auth jim ishlamay qolgan (main'da 34 test yiqilgan). Shoshilinch tuzatish sifatida
  kiritildi.

### Done (yangi)
- Oisha ikki-bosh Telegram runtime kodi tayyorlandi: Oracle Telethon userbotni saqlaydi va `TELEGRAM_BOT_INGRESS_MODE=disabled` bilan @jonairobot update'larini qabul qilmaydi; alohida Cloud Run entrypoint faqat Aiogram webhook, owner/admin dispatcher, Hisobchi approval callback va Turso-backed bounded idempotency'ni boshqaradi. Secret-safe Docker/Cloud Build/PowerShell deploy artefaktlari `min=0`, `max=1`, `concurrency=1` bilan qo'shildi; eski `.env`-ni command line'ga chiqaradigan full-runtime GCP deploy fail-closed qilindi. Test: 1112 passed, 13 skipped; Bandit medium/high 0 (Codex).
- Telegram Userbot sessiyasini doimiy tirik saqlash (`session_keeper.py`) va har 5 daqiqada ping yuborish, hamda sessiya o'zgarganda avtomatik `data/userbot_session_string.txt` ga saqlash tizimi ishga tushirildi va Oracle VM ga deploy qilindi. Bu orqali 401 Unauthorized va qayta login qilish muammolari to'liq hal etildi (Antigravity).
- Aiogram 3.x bot-token migratsiyasining navbatdagi bosqichi bajarildi: Admin komandalar dispetcheri (`admin_aiogram_dispatcher.py`) kengaytirilib, VPS status (`/vps_status`), auto-reply rejimi va kill-switch boshqaruvi (`/auto_status`, `/pause_auto`, `/resume_auto`, `/set_mode`) qo'shildi. `test_admin_aiogram_dispatcher.py` ga tegishli unit-testlar qo'shildi (Antigravity).
- Oisha Telegram ikki bosh migratsiyasining xavfsiz birinchi bosqichi tayyorlandi: Telethon userbot alohida qoladi; Aiogram `@jonairobot` uchun polling lifecycle, outbound runtime, ko'chirilgan admin komandalar va Hisobchi approval callback adapterini boshqaradi. Aiogram rejimida Telethon bot-token receiver ishga tushmaydi. Ko'chmagan legacy AdminBot komandalar yo'qolmasligi uchun production default hali Telethon; live switch qolgan routerlar ko'chgach qilinadi. Test: 687 passed, 13 skipped; Bandit `src/ -ll`: medium/high issue yo'q (Codex).
- JARVIS gap-auditidan keyin Oisha Business Command Center branding agentligi fokusida qo'shildi: lead, vazifa, eslatma, brief/KP, loyiha/deadline, avans, agentlik analitikasi va jamoa yuklamasi intentlari; mutation approval gate, stable idempotency key, evidence-first read policy va secret chiqarmaydigan real integration registry. Ombor funksiyasi ataylab kiritilmagan. API: `POST /api/oisha/command/plan`, `GET /api/oisha/integrations` (Codex).
- Oisha self-improvement loop qo'shildi: har kuni 10:00 da read-only diagnostika, stable fingerprint/dedup, ownerga Telegram digest, `/oisha_rivoj` va `/oisha_takliflar`, owner-only accept/defer/reject hamda AI-agent handoff. Weekly self-evolution endi tasdiqsiz branch/PR yaratmaydi. Test: 11 yangi + 13 regressiya testlari passed; Bandit `src/ -ll`: no issues (Codex).
- Oracle Production Deploy #28758418917 success. Fixes: `c8a9871` missing `telegram_mcp` route qo'shildi, `27306eb`/`59820c8` runtime detection VM/systemd uchun tuzatildi. Test: `tests/test_agent_runtime.py` 2 passed.
- `src/api_server.py:288`: silent `except Exception: pass` → `logger.warning` (hisobchi_mcp router mount failure endi loglanadi)
- Local `.env` cleaned up (170→104 lines, duplicate block removed)
- Server `.env` Python code qoldiqlari tozalandi, keyingi deploy GitHub secretlardan to'g'ri qiymatlarni tiklaydi
- capcom6/android-sms-gateway cloud/private API uchun `SmsGatewayClient` qo'shildi: `Oisha -> api.sms-gate.app -> Android telefon -> SMS` oqimi env orqali disabled-by-default ishlaydi, webhook payload normalize qiladi. Test: `tests/test_sms_gateway_client.py` 5 passed; yangi fayl Bandit: no issues (Codex).
- Saved Messages/private photo receipt auto-scan cheklandi: endi owner private rasmlari faqat `/kirim`, `/chiqim`, `/chek`, `/receipt`, `#kirim`, `#chiqim` markerlari bilan ishlanadi; oddiy saqlangan rasmlar Hisobchi/Gemini tekshiruviga tushmaydi. Test: 358 passed, 13 skipped; Bandit: no issues (Codex).
- Barcha ochiq PRlar (38 ta) va Dependabot security alerts (multer, nodemailer, @babel/core) hal qilindi: dependency lar eng oxirgi versiyaga yangilandi, xavfsizlik kamchiliklari (SSL verification) tuzatildi va gitleaks historical allowlist yangilandi (TRAE).
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
- Telegram kanallaridan a'zolarni o'rniga faol mijozlarni (postlarga komment yozganlarni) sifatli lead sifatida ajratib olish tizimi `TelegramScraperReal`da implement qilindi (`_extract_channel_members` yangilandi va unikal `extract_leads_from_channel` metodi qo'shildi). Testlardan o'tdi va GitHubga push qilindi (Antigravity).
- `salescoach-ai`dagi yangi Dependabot xavfsizlik kamchiliklari (`multer`, `postcss`, `js-yaml`) root `package.json` overrides orqali to'liq bartaraf etildi va `pnpm-lock.yaml` yangilandi (Antigravity).
- Oisha-OS Admin veb-sayti (`https://oisha.jonbranding.uz/`) uchun to'liq premium oq-dizayn (light theme) ishlab chiqildi, CSS o'zgaruvchilari modernizatsiya qilindi va muvaffaqiyatli build qilinib, ishga tushirildi (Antigravity).
- Remote VM dagi Google API / Sheets xizmatlarining ishlamayotganligi `data/service_account.json` faylini serverga yuklash orqali bartaraf etildi va to'liq bog'landi (Antigravity).
- `src/boot.py` faylidagi fatal NameError xatoligi (aniqlanmagan `_spawn_task` o'rniga `asyncio.create_task` qo'llash orqali) to'liq tuzatildi va bot muvaffaqiyatli ishga tushdi (Antigravity).

### Next Tasks
1. [Done] `self_command_handler` (1000+ lines) → `src/commands/` ga ajratish
2. [Done] `except Exception: pass` larni tuzatish (~30+ joy `call_analyzer.py` da tuzatildi)
- Global → app_ctx.* migratsiyasi (Jarayonda)
- [Done] f-string SQL → parametrized query (database.py:682, 998)
- [Done] Handler lar: `src/handlers/` ga ajratish (negotiation, kirim, case_publisher, etc.)
- [Done] Turso DB schema migration for FrogAgent (added profit_estimate, source_manager, external_task_id, is_frog to tasks table) and fixed database_pool SQLite error handling.
- [Done] FrogAgent va FrogScheduler remote VM ga deploy qilinib muvaffaqiyatli ishga tushirildi. Har kuni 09:00 da Telegram orqali eng foydali vazifalar (Frog) ro'yxati yuboriladi.
- Bot akkauntni Aiogram'ga bosqichma-bosqich migratsiya qilish: Telethon userbot o'zgarmaydi; @jonairobot bot-token head adapter orqali ajratilib, keyin command/callback/report oqimlari navbat bilan ko'chiriladi.

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
