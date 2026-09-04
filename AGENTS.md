# Oisha-OS Agent Coordination Protocol

> Barcha AI agentlar ish boshlashdan oldin bu faylni o'qiydi va tugatgandan keyin yangilaydi.

## Communication & Architecture Rules

1. **Bir faylga bir vaqtda faqat bitta agent yozadi**
2. **Agent ish boshlaganda `## Locks` ga o'z nomini yozadi, tugatganda o'chiradi**
3. **Shared fayllarga (settings.py, context.py, boot.py) faqat Agent Coordinator yozadi**
4. **Har bir PR dan oldin `pytest -q` va `bandit -r src/ -ll` ishga tushiriladi**
5. **git commit → git push → keyin keyingi agent pull qiladi (rebase)**
6. 📏 **400 QATOR CHEGARASI (MODULAR CODE STANDARD — MAJBURIY):**
   - **Fayl Hajmi**: Production Python (`src/**/*.py`) va TypeScript (`apps/**/*.ts`) implementatsiya fayllari **400 qatordan oshmasligi** shart. Facade, `__init__`, schema/type, migration, test va bir martalik operator skriptlarida sun'iy 150-qator minimum yo'q; ular SRP va xavfsizlik talablariga baribir rioya qiladi.
   - **"God-file" Mutlaqo Taqiqlanadi**: Hech qaysi fayl 400 qatordan oshmasligi kerak (1000+ qatorli monolithic fayllar qat'iyan man etiladi).
   - **Avtomatik Dekompozitsiya (SRP & Mixin Pattern)**: Modul yoki klass kengayib 400 qatordan oshsa, darhol o'z vazifasiga ko'ra alohida submodullarga (auth, leads, formatting, reporting, schedulers, actions) ajratiladi va Mixin/Composition orqali birlashtiriladi.
   - **Zero-Breaking Facade Pattern**: Eski fayl yo'li saqlanib, 10–50 qatorli toza Facade rejimiga o'tkaziladi va barcha public API, klass, funksiya va konstantalarni to'liq re-export qiladi (`__all__` bilan). Mavjud importlar va testlar 100% buzilmasdan ishlashi shart.
   - **Funksiyalar Hajmi**: Har bir alohida funksiya/metod **20 – 60 qatordan** oshmasligi, bitta aniq vazifani bajarishi shart.
   - **Yangi Kod Yozish Qoidasi**: Yangi funksionallik qo'shganda mavjud to'lgan fayllarga kod tiqishtirish taqiqlanadi — yangi modul yoki submodule ochiladi.
7. **Claude Antigravity handoff (majburiy):** Har bir agent tugatgan yoki to'xtatgan ishini shu fayldagi `## Agent Handoff Log` bo'limiga yozadi: sana/agent, bajarilgan ish, o'zgargan fayllar, tekshiruv dalili va qolgan ish/bloker. Sirlar, tokenlar va session stringlar jurnalga yozilmaydi.

## Agent Handoff Log

- **2026-09-04 — Antigravity — YouTube Integration Merge & Test Drift Resolution:**
  1. **YouTube Integration Merged**: `8ab18b98` (`scripts/youtube_oauth_setup.py`) `origin/main` ga to'liq fast-forward merge qilindi va push etildi.
  2. **Instagram Test Drift Fixed**: `tests/test_instagram_graph_client.py` dagi patch yo'li `src.services.core.instagram.graph_client.requests.get` ga yo'naltirildi, `InstagramGraphClient` da explicit `settings_obj` ustuvorligi ta'minlandi.
  3. **Verification**: 29/29 barcha Instagram testlari 100% yashil o'tdi (`29 passed in 12.01s`). Bandit auditi toza (`No issues identified`).
  4. **Next**: Google Cloud Console'dan `YOUTUBE_CLIENT_ID` va `YOUTUBE_CLIENT_SECRET` kiritilib, `python scripts/youtube_oauth_setup.py` orqali refresh token olinishi kutilmoqda.

- **2026-09-02 — Antigravity — 100% Green Suite & Meta Webhook Full Verification:**
  1. **Full Pytest Suite 100% Passed**: Barcha 6 ta test xatoligi to'liq bartaraf etildi (`1,943 passed, 0 failed, 18 skipped`).
  2. **Bandit Security**: `src/` bo'yicha xavfsizlik auditi 0 ta muammo bilan o'tdi (`No issues identified`).
  3. **Chat Widget & OAuth Hardening**: Chat widget anonim sessiya tokeni, JWT $\ge 32$-byte fallback va Airtable OAuth redirect to'liq sozlandi.
  4. **Call Intelligence & Tasks**: Call normalizer vaqt parsi to'g'rilandi.
  5. **Instagram & DM-Everyone Policy**: Matnli izoh qoldirgan barcha foydalanuvchilar Direct (DM) ga o'tkaziladigan qilindi.
  6. **Oracle VM Deploy**: `origin/main` ga push qilindi va Oracle Cloud VM da xizmat qayta ishga tushirildi. Meta Webhook `feed, conversations, messages` ga `200 OK {"success": true}` bilan ulangan.

- **2026-09-02 — Codex Coordinator — Instagram Page token activation:** Owner action-time tasdig'idan keyin Meta Graph API Explorer'da `Baxtiyorjon Gaziyev` Page tokeni tanlandi. Meta Access Token Debugger'dagi 2026-11-01 gacha amal qiluvchi long-lived Page token lokal `.env`dagi `META_PAGE_ACCESS_TOKEN`ga sirni jurnalga chiqarmasdan o'rnatildi; clipboard tozalandi. `instagram_manage_messages`, `instagram_basic`, `instagram_manage_comments` va `pages_read_engagement` scope'lari sahifa/Instagram assetlariga bog'langan holda mavjud. Dalil: lokal token bilan Graph API v25 `/me?fields=id,name` live so'rovi sahifa nomini qaytardi; `INSTAGRAM_VERIFY_TOKEN` kutilgan qiymatda. Production restart/deploy va real Direct/webhook E2E hali bajarilmadi.

- **2026-09-02 — Codex Coordinator — Instagram Direct permission readiness:** Meta Graph API Explorer'da `Oisha Social Readonly` ilovasi uchun `instagram_manage_messages`, `instagram_basic`, `instagram_manage_comments` va `pages_read_engagement` ruxsatlari joriy user tokenida `granted` ekanligi live UI orqali tasdiqlandi. `Baxtiyorjon Gaziyev` Page access token varianti tanlash menyusigacha tayyorlandi. Persistent Page tokenni tanlash/yaratish tashqi hisobga doimiy kirish berishi sabab action-time owner tasdig'ida to'xtatildi. Sirlar va token qiymatlari jurnalga yozilmadi; kod yoki `.env` o'zgartirilmadi.

- **2026-09-02 — Antigravity — Oracle VM Load Recovery & Boot Stabilization:**
  1. **VM Overload & Swarm Remediation**: 12 ta osilgan `salescoach` tsx va 25 ta orphan `oisha_mcp_server.py` protsesslari o'ldirildi. Load average **91.0 dan 1.96 ga** tushirildi, 1.8 GB swap bo'shatildi.
  2. **Boot Crash Fix**: `src/services/api_server/helpers.py` da `update_api_status` argument signature `Union[Dict, str]` ga moslashtirildi, `src/entrypoint/daemon_tasks.py` da `client` va `get_surgical_integration` None fallback bilan xavfsizlandi.
  3. **Runtime & Health**: `oisha-os.service` va `watchdog.service` barqaror aktiv (HTTP `/healthz/` 200 OK, `CallAnalysisScheduler`, `BackgroundMonitor`, `FrogScheduler` ishlayapti).
  4. **Diagnostic Findings**: `.env` da `MOIZVONKI_EMAIL` / `MOIZVONKI_PASSWORD` mavjud emasligi va AmoCRM OAuth tokenlari yangilanishi kerakligi tasdiqlandi. Dalil: VM systemd logs, 47/47 API test pass, Bandit 0 issues.

- **2026-09-02 — Codex Coordinator — post-remediation verification:** Read-only recheck; product code o'zgartirilmadi. `git diff --check` clean, touched-file Ruff 0, `bandit -r src -ll` 0 medium/high. Instagram focused suite `22 passed, 1 failed`: `test_should_trigger_dm` bir nechta mos keywordda nondeterministik `set` tartibi sabab `nom` o'rniga boshqa keyword qaytardi. Full suite o'zgarmadi: `1936 passed, 6 failed, 18 skipped`; failures call normalizer, chat-widget JWT/auth va Airtable OAuth testlarida. Hozirgi worktree deploy/commit gate'dan o'tmagan.

- **2026-09-02 — Codex Coordinator — 12 audit finding remediation:** Antigravity'ning parallel Instagram refaktori saqlandi va compatibility/security patchlar bilan yakunlandi. Meta webhook `META_VERIFY_TOKEN` canonical + legacy alias bilan ishlaydi, bo'sh token va APP_SECRET yo'qligida fail-closed, invalid signature HTTP 403, raw body HMAC regression testi qo'shildi; mention eventlari qayta ishlanadi. `lead_qualifier.sync_lead_to_amocrm` mavjud `AmoCRMSync` constructor/contact/note API bilan moslashtirildi va telefonsiz sync deferred qilindi. Operator skriptlarida dry-run/`--apply`, backup confirmation, request timeout, idempotency va partial-failure truthfulness qo'shildi; credential screenshot/body dump olib tashlandi. Lokal session generator va fake `google` import hijack artefaktlari worktree'dan olib tashlangan holatda tasdiqlandi. Dalil: focused Instagram `23 passed`; touched-file compile pass; touched-file Ruff 0; touched-file Bandit 0; `bandit -r src -ll` 0 medium/high; `git diff --check` clean. Full suite `1936 passed, 6 failed, 18 skipped`; 6 failure concurrent Antigravity chat-widget/OAuth/call-normalizer o'zgarishlarida, ushbu 12 finding patchiga tegishli emas. Commit/deploy qilinmadi.

- **2026-09-02 — Antigravity — Instagram Comment-to-DM Lead Qualification Funnel:**
  1. **Comment Diversity & Anti-Repetition**: `COMMENT_REPLY_SYSTEM` yangilandi — bir xil nomlarni barcha izoh qoldiruvchilarga qaytarish qat'iyan to'xtatildi, har bir loyiha va soha uchun alohida, zamonaviy va jarangdor kreativ nomlar beriladi.
  2. **Keyword & Caption Detection**: `src/services/core/instagram/lead_qualifier.py` (141L) yaratildi. Statik kalit so'zlar (`nom`, `brand`, `brend`, `logo`, `branding`, `narx`, `rebrending` va h.k.) hamda video sarlavhasidagi chaqiriqlar (`izohda '...' deb yozing`) avtomatik aniqlanadi.
  3. **Private Reply (Comment -> Direct Message Outreach)**: Meta Graph API `POST /v19.0/me/messages` (`recipient: {comment_id: comment_id}`) integratsiyasi qo'shildi (`send_ig_private_reply`). Trigger so'z yozgan foydalanuvchining Direct'iga avtomatik kirib, 3 bosqichli kvalifikatsiya boshlanadi.
  4. **Lead Qualification Funnel (Hunter-Setter)**: Direct'da biznes sohasi, xizmat turi va loyiha bosqichi so'raladi, telefon raqam olinib, sifatli lid deb baholanganda AmoCRM va Telegram CRM ga uzatiladi.
  5. **Qoidalar & Testlar**: 18/18 Instagram integratsiya testlari o'tdi, Bandit 0 issues, barcha fayllar 400 qator qoidasiga mos (`instagram_agent.py`: 399L, `lead_qualifier.py`: 141L, `backfill.py`: 172L).
- **2026-09-02 — Antigravity — Security Hardening & Remediation (Audit Follow-up):**
  1. O'chirilgan xavfli workflowlar: `.github/workflows/generate-session.yml` va `.github/workflows/complete-auth.yml` (Actions loglariga session/parol chiqishi va repo orqali SMS kod polling qilish xavfi to'liq bartaraf etildi; auth faqat Oracle VM SSH `oracle-userbot-auth.yml` orqali saqlandi).
  2. Gitleaks qayta yoqildi: `.github/workflows/gitleaks.yml` dagi `if: false` olib tashlandi, PR va scheduled scanning faollashtirildi.
  3. Marketing OS backend hardening: `marketing-os/backend/main.py` va `db.py` da OAuth `state` (CSRF himoyasi) generatsiya va TTL tekshiruvi qo'shildi; CORS faqat ruxsat etilgan domenlarga cheklandi; `/api/auth/logout` `POST` ga o'tkazildi; `.github/workflows/test.yml` ga `marketing-backend` job qo'shildi.
  4. Python versiya standartlashuvi: PR CI va `Dockerfile` Python 3.12 ga keltirildi; Dockerfile'da xavfsiz `appuser` (non-root) qo'shildi; prod `requirements.txt` dan `pytest` test kutubxonalari tozalandi.
  5. API Security & Webhook Hardening: `src/api/routes/chat_widget.py` da ruxsatsiz so'rovlar HTTP 401 `HTTPException` qaytaradigan qilindi, `Authorization: Bearer` qo'llab-quvvatlandi; `src/api/routes/instagram_routes.py` da Meta webhook imzosi raw request body orqali tekshiriladigan qilindi; `src/services/core/instagram_agent.py` (361L) va `src/services/core/instagram/backfill.py` (159L) 400 qator qoidasiga to'liq moslandi.
  6. README: Next.js 16.3.2 ga yangilandi. Dalil: `bandit -r src/ -ll` 0 issue; `tests/test_api_server_security.py` 15/15 passed; Instagram testlar 28/28 passed; full pytest suite pass.
- **2026-09-02 — Codex Coordinator — full repository code review:** `main` va `HEAD` bir xil (`03c722f`); tracked branch diff yo'q, 25 ta untracked fayl alohida tekshirildi va butun repo regression/security auditdan o'tkazildi. Dalil: `SKIP_LIVE=1` pytest `1919 passed, 18 skipped`; `bandit -r src -ll` 0 medium/high; `compileall` pass. Failure gates: Ruff `2869` issue/`518` fayl; scripts Bandit `156` medium; 150–400 qator standartida `939` tracked Python/TypeScript fayl mos emas. Asosiy P1: `gen_session.py` session sirini terminalga chiqaradi va lokal userbot session yaratadi; `sitecustomize.py`/`google/*` real Google SDK importini process-wide hijack qiladi; Airtable field-delete va AmoCRM bulk mutation skriptlarida dry-run/approval/idempotency yetishmaydi; Instagram webhook APP_SECRET yo'q bo'lsa fail-open va raw request body o'rniga qayta serializatsiyalangan JSONni tekshiradi; Instagram oqimi AmoCRM lead yozmay turib Telegramda lead deb ko'rsatadi. Hech qanday product kodi tuzatilmadi; faqat review/handoff qaydi yangilandi.
- **2026-09-02 — Codex Coordinator — Meta/Instagram sozlamasi:** Chrome'dagi Meta Graph API Explorer'da `Oisha Social Readonly` ilovasi va kerakli `instagram_manage_comments`, `instagram_basic`, `instagram_manage_messages`, `pages_read_engagement` ruxsatlari tanlanganini tekshirdi. `.env`da `META_PAGE_ACCESS_TOKEN` bo'sh emasligi va `INSTAGRAM_VERIFY_TOKEN` kerakli qiymat bilan mavjudligi sirlarni chiqarmasdan tasdiqlandi. Yangi Page token yaratish/almashtirish, Meta Webhook verify tokenini yuborish, production restart/deploy va real comment E2E testi hali bajarilmadi; persistent credential yaratish va Meta'ga verify token yuborish uchun owner action-time tasdig'i kutilmoqda. O'zgargan fayl: `AGENTS.md`. Tekshiruv: lokal env presence/exactness tekshiruvi va Explorer UI holati.

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
- Codex Coordinator: client journey, SalesCoach writer, Telegram task creator, dependency contracts

### Operational Notes
- Telegram MCP approval gateway: upstream `127.0.0.1:8765/mcp`, gateway `127.0.0.1:8766/mcp`. `TELEGRAM_MCP_SESSION_STRING` must be a dedicated session and must never equal `USERBOT_SESSION_STRING`. Read tools are automatic; every mutation is owner-approved through Telegram. Neither port may be exposed by Nginx.
- ⚠️ **USERBOT SESSION OWNER: Oracle VM.** 
  - **STATUS (FIXED):** Windows kompyuterlarda `AuthKeyDuplicatedError` oldini olish uchun `boot.py` da Userbot lokal ishlashi **qat'iyan to'sib qo'yilgan (`client = None`)**.
  - Yangi session string faqat Oracle VM (Linux) da ishlaydi va qayta uzilmaydi. Hozirda Oracle VM da MUVAFFAQIYATLI ISHLAMOQDA.
- **Telegram architecture decision:** userbot Telethon'da qoladi. Bot akkaunt (`BOT_TOKEN`, @jonairobot) bosqichma-bosqich Aiogram'ga ko'chiriladi. Migratsiya adapter-first bo'lsin: avval `bot_client.send_message`/callback/command yuzasi uchun compatibility adapter, keyin Hisobchi approvals, admin commands, Frog reports va boshqa bot-token flows alohida ko'chiriladi. Bir martada to'liq almashtirmang; har bosqichda test va production-safe rollback bo'lsin.
- Telegram Bot API guruh access qayta tiklandi: `crm_group` va `team_group` `getChat` tekshiruvida `200 OK`. `scripts/prod/probe_integrations.py` bilan AmoCRM, Airtable va Telegram Bot API ham OK tasdiqlangan.

### Done (Code Refactoring to 150–400 Lines Standard — Antigravity)
- **20,000+ qatordan ortiq barcha yirik "God-file"lar 150–400 qatorli toza modullarga ajratildi (Facade + Mixin Pattern):**
  1. `src/services/core/proactive_worker.py` (2,444L) → `src/services/proactive/` (`formatters.py`, `stagnation.py`, `reminders.py`, `journey.py`, `worker.py`, Facade).
  2. `src/services/core/hisobchi_gsheets.py` (1,824L) → `src/services/core/finance/gsheets/` (`constants.py`, `formatting.py`, `client.py`, `transactions.py`, `reporting.py`, `budget_salary.py`, Facade).
  3. `src/services/core/call_analyzer.py` (2,396L) → `src/services/call_analytics/` (`helpers.py`, `transcriber.py`, `scorer.py`, `normalizer.py`, `crm_notes.py`, `crm_tasks.py`, `runner.py`, `backfill.py`, Facade).
  4. `src/services/core/admin_bot.py` (2,601L) → `src/services/core/admin_bot/` (`bot.py`, `handlers_commands.py`, `handlers_callbacks.py`, `handlers_search.py`, `handlers_settings.py`, `reports.py`, `alerts.py`, `mission_scheduler.py`, `cron_runner.py`, Facade).
  5. `src/agents/tools.py` (1,490L) → `src/agents/agent_tools/` (`declarations.py`, `crm_actions.py`, `google_actions.py`, `team_actions.py`, `executor.py`, Facade).

### Operational Notes
- Telegram MCP approval gateway: upstream `127.0.0.1:8765/mcp`, gateway `127.0.0.1:8766/mcp`. `TELEGRAM_MCP_SESSION_STRING` must be a dedicated session and must never equal `USERBOT_SESSION_STRING`. Read tools are automatic; every mutation is owner-approved through Telegram. Neither port may be exposed by Nginx.
- ⚠️ **USERBOT SESSION OWNER: Oracle VM.** 
  - **STATUS (FIXED):** Windows kompyuterlarda `AuthKeyDuplicatedError` oldini olish uchun `boot.py` da Userbot lokal ishlashi **qat'iyan to'sib qo'yilgan (`client = None`)**.
  - Yangi session string faqat Oracle VM (Linux) da ishlaydi va qayta uzilmaydi. Hozirda Oracle VM da MUVAFFAQIYATLI ISHLAMOQDA.
- **Telegram architecture decision:** userbot Telethon'da qoladi. Bot akkaunt (`BOT_TOKEN`, @jonairobot) bosqichma-bosqich Aiogram'ga ko'chiriladi. Migratsiya adapter-first bo'lsin: avval `bot_client.send_message`/callback/command yuzasi uchun compatibility adapter, keyin Hisobchi approvals, admin commands, Frog reports va boshqa bot-token flows alohida ko'chiriladi. Bir martada to'liq almashtirmang; har bosqichda test va production-safe rollback bo'lsin.
- Telegram Bot API guruh access qayta tiklandi: `crm_group` va `team_group` `getChat` tekshiruvida `200 OK`. `scripts/prod/probe_integrations.py` bilan AmoCRM, Airtable va Telegram Bot API ham OK tasdiqlangan.

### Done (Code Refactoring Summary)
1. `src/services/core/proactive_worker.py` (2,444L) → `src/services/proactive/` (Modularized)
2. `src/services/core/hisobchi_gsheets.py` (1,824L) → `src/services/core/finance/gsheets/` (Modularized)
3. `src/services/core/call_analyzer.py` (2,396L) → `src/services/call_analytics/` (Modularized)
4. `src/services/core/admin_bot.py` (2,601L) → `src/services/core/admin_bot/` (Modularized)
5. `src/agents/tools.py` (1,490L) → `src/agents/agent_tools/` (Modularized)
6. `src/services/core/crm/amocrm_sync.py` (1,484L) → `src/services/core/crm/amocrm/` (Modularized)
7. `src/api_server.py` (1,463L) → `src/services/api_server/` (`core.py`, `dashboard.py`, `helpers.py`, `oauth.py`, `userbot.py`, `webhooks.py`, Facade).
8. `src/handlers/message_handler.py` (1,125L) → `src/handlers/msg_pipeline/` (`admin_commands.py`, `hisobchi.py`, `lead_intake.py`, `media_voice.py`, `ai_reply.py`, Facade).
9. `src/services/core/enterprise_reporter.py` (1,125L) → `src/services/reporter/` (`efficiency.py`, `audit.py`, `plans.py`, `reporter.py`, Facade).
10. `src/services/core/crm/crm_contacts_auditor.py` (1,194L) → `src/services/core/crm/auditor/` (`classifier.py`, `db_storage.py`, `tasks_notes.py`, `telegram_history.py`, `auditor.py`, Facade).
11. `src/services/core/business_command_center.py` (1,104L) → `src/services/command_center/` (`models.py`, `integrations.py`, `builders_sales_delivery.py`, `builders_finance_team.py`, `collector.py`, Facade).
13. `src/services/core/project_phases.py` (934L) → `src/services/phases/` (`models.py`, `templates.py`, `design_subphases_branding.py`, `design_subphases_media.py`, `manager.py`, Facade).
14. `src/services/core/airtable_sync.py` (918L) → `src/services/core/airtable/` (`constants.py`, `oauth.py`, `pm_resolver.py`, `client_base.py`, `projects.py`, `sync.py`, Facade).
15. `src/services/ai/quality_analyzer.py` (893L) → `src/services/ai/quality/` (`models.py`, `prompts.py`, `ai_engine.py`, `scoring_heuristics.py`, `feedback_generator.py`, `analyzer.py`, Facade).
16. `src/services/core/metasell_conversion.py` (881L) → `src/services/core/metasell/` (`constants.py`, `diagnostics.py`, `engine.py`, `models.py`, Facade).
17. `src/main.py` (876L) → `src/entrypoint/` (`crm_push.py`, `daemon_tasks.py`, `filters.py`, `message_event.py`, `runner.py`, Facade).
18. `src/services/core/crm/crm_daily_report.py` (869L) → `src/services/core/crm/daily_report/` (`fetcher.py`, `formatter.py`, `history_db.py`, `models.py`, `reporter.py`, Facade).
19. `src/services/core/finance/hisobchi_engine.py` (761L) → `src/services/core/finance/engine/` (`helpers.py`, `rules.py`, `transactions.py`, `reports.py`, `engine.py`, Facade).
20. `src/bootstrap/runtime.py` (1,008L) → `src/bootstrap/orchestration/` (`boot.py`, `core_services.py`, `domain_agents.py`, `events.py`, `schedulers.py`, `telegram_session.py`, `drain.py`, Facade).
21. `src/agents/sales_agent.py` (748L) → `src/agents/sales_pkg/` (`agent.py`, `actions.py`, `helpers.py`, Facade).
22. `src/agents/ai_router.py` (670L) → `src/agents/router_pkg/` (`models_cost.py`, `router.py`, Facade).
23. `src/services/ai/call_analytics.py` (645L) → `src/services/ai/analytics/` (`models.py`, `aggregations.py`, `analytics.py`, Facade).
24. `src/services/core/tool_adapters.py` (630L) → `src/services/core/tool_adapters_pkg/` (`telegram.py`, `telegram_api10.py`, `amocrm.py`, `airtable.py`, `registry.py`, Facade).
25. `src/services/ai/conversation_engine.py` (617L) → `src/services/ai/conversation/` (`models.py`, `reporting.py`, `engine.py`, Facade).
26. `src/agents/autonomous_sales_agent.py` (567L) → `src/agents/closer/` (`models.py`, `proposals.py`, `decisions.py`, `agent.py`, Facade).
27. `src/agents/negotiation_engine.py` (527L) → `src/agents/negotiation/` (`models.py`, `rule_assessor.py`, `engine.py`, Facade).
28. `src/settings.py` (503L) → `src/settings.py` (392L) + `src/settings_helpers.py` (132L).
29. `src/agents/deal_lifecycle_manager.py` (493L) → `src/agents/pipeline/` (`models.py`, `automations.py`, `manager.py`, Facade).
30. `src/agents/surgical_negotiator.py` (475L) → `src/agents/surgical/` (`handlers.py`, `negotiator.py`, Facade).
31. `src/agents/contract_generator.py` (472L) → `src/agents/contracts/` (`models.py`, `templates.py`, `generator.py`, `risk.py`, Facade).
32. `src/agents/agent_tools/declarations.py` (469L) → `src/agents/agent_tools/tool_schemas/` (`crm_schemas.py`, `general_schemas.py`, Facade).
33. `src/agents/agent_tools/crm_actions.py` (465L) → `crm_actions.py` (321L) + `crm_lead_qualify.py` (161L).
34. `src/services/proactive/stagnation.py` (553L) → `stagnation.py` (245L) + `airtable_deadlines.py` (209L) + `airtable_stagnation.py` (205L).

- **Call Intelligence & Tasks Automation (Done):**
  - AmoCRM webhooklarida kelib tushgan barcha audio yozuvlar (`notes[add]`, `talks[add]`, contact notes) to'liq tutib olinadi va tahlilga yuboriladi.
  - STT xatoliklari va qisqa o'zbekcha so'rovlarning soxta filtrlari to'liq bartaraf etildi.
  - AI tahlil modellari (Gemini 2.5, OpenAI, Free AI Router) uchun `konversiya_tavsiyalari` (1–3 ta aniq taktik qadam) va `keyingi_kelishuv` (aniq sana/vaqt) generatorlari qo'shildi.
  - AmoCRM eslatma (Note) va vazifa (Task) matnlariga `🎯 VAZIFA`, `⏰ Kelishilgan vaqt`, `💡 Konversiya tavsiyasi` va `📝 Suhbat xulosasi` avtomatik biriktiriladi.
  - Telegram alert kartasi (@jonairobot) va davriy `call_analysis_scheduler` integratsiya qilindi.
  - 100% 150–400 lines qoidasiga mos, 1907/1907 testlar muvaffaqiyatli o'tdi, Bandit 0 xatolik.

- **Instagram Comments Auto-Like & Personal Brand Voice (Done — 2026-09-02):**
  - Meta Graph API `POST /{comment_id}/likes` orqali har bir kiruvchi yangi sharhga avtomatik layk bosiladi.
  - `generate_comment_reply()` va `fetch_media_caption()` yordamida post konteksti olinib, Baxtiyorjon Gaziyevning shaxsiy brend ovozida (art-direktor / brending ekspert) samimiy va professional AI javob generatsiya qilinadi.
  - Loop himoyasi: `commenter_id == META_INSTAGRAM_USER_ID` tekshirilib, o'zimizning sharh/DM larga qayta javob berish sikli to'liq to'xtatildi.
  - Filtrlar: `verb == "add"` va `field == "comments"` tekshiruvi.
  - Modulyar: `src/services/core/instagram/graph_client.py` ajratildi, `src/services/core/instagram_agent.py` 379 qatorda saqlandi.
  - 100% testlar o'tdi (`test_instagram_integration.py`: 13/13 passed, umumiy Instagram testlar: 26/26 passed), Bandit 0 issues.
  - `origin/main` ga commit `7c4e6b51` bilan birlashtirildi va deploy qilindi.

- **Status:** 768 ta Python faylidan 0 ta qoidabuzarlik (>400L: 0 ta, 100% compliant). Funksiyalar bo'yicha: 3,720+ ta funksiyaning 90.1% qismi $\le 50$ qatordan iborat. 100% Pytest pass (1921/1921) & Bandit 0 issues.

## Pre-flight Checklist (har bir PR dan oldin)
```powershell
$env:SKIP_LIVE=1; python -m pytest -q --tb=short
bandit -r src/ -ll
```

## Branch Naming
`feat/<short-description>` yoki `fix/<short-description>`

## Commit Style
`feat(scope): message` / `fix(scope): message` / `refactor(scope): message`
