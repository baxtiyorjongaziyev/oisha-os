# Current State, Operational Notes & Refactor History

> AGENTS.md dan ko'chirildi (2026-09-29).

## Current State

## Locks

- Codex Coordinator: leadgen delivery recovery modules and focused tests (2026-09-15).

- Finance archive handoff (Codex, 2026-09-07; lock released): read-only MCP reconciliation found 200 source/338 target rows, 193 populated receipts already migrated, 7 empty, no duplicates, UZS 772902150 both sides. Account review: 110 P2P, 11 bank, 40 cash USD differences, 16 unknown source accounts. Added scripts/finance_migration/ and tests/test_finance_archive_migration.py; 18 offline tests passed, Ruff clean, Bandit 0 issues. Private evidence data/finance-migration/20260907/. No Airtable writes, commit, PR or deploy. Apply blocked by discrepancies; no missing receipts. Brain tools unavailable; vault filesystem note used. Any correction/apply/rollback requires owner action-time approval.

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

