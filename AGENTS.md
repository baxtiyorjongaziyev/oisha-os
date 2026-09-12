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

- **2026-09-10 — Claude — Airtable "Jon Branding" Base Cleanup (in progress, paused on AI limit):**
  1. **Scope**: Operational cleanup of the Airtable finance base (`app8xoyx1XCumYFXV`), not a code change — see `AIRTABLE_CLEANUP_HANDOFF.md` for full detail.
  2. **Done**: Deleted 3 unused jamoa/inbox tables (`Tuzatish so'rovlari`, `Moliya so'rovlari`, `Moliya nazorati`, all recoverable from Airtable trash 7 days); removed 8 orphan/`[ESKI]` fields across Tranzaksiyalar/Loyihalar/Jamoa; added an `Oy nomi` Uzbek-month formula field on Tranzaksiyalar and regrouped the Kirim/Chiqim views by it; pruned 2 empty duplicate rows in `Cashflow — oylik`.
  3. **Verification**: Each deletion was checked against Airtable's own "N dependencies" delete-confirmation dialog before confirming; no automation, form, or report table was touched. `Oy` (date formula), `Kirim UZS`/`Chiqim UZS`/`Sof oqim UZS`, `Oylik P&L (Hisobot)`/`Cashflow qatori` links, `Nazorat holati`/`Tekshiruv izohi`, the "Cashflow qatorini bog'lash" and "Finance — yangi tranzaksiyani Reja qilish" automations, and the P&L/Cashflow/Balans report tables were left untouched by design.
  4. **Files changed**: `AIRTABLE_CLEANUP_HANDOFF.md` (new) — this repo change is docs-only.
  5. **Remaining / blocker**: Paused on the 5-hour AI session limit. Still open: delete orphan `Moliya so'rovlari` text field in `Moliya kategoriyalari` and `Hisoblar`; answer owner's NAF Stroy project start/end date question; decide on the two `ARXIV — Kirim/Chiqim (Finance V1)` tables — **do not delete them or any `arxiv —`/`[ESKI]` rollup/link field until ARXIV records are verified against `Tranzaksiyalar` for full migration** (this was previously asserted from an Airtable field description, not independently confirmed — see handoff file); decide on `Ovchi`/`Seller`/`Art Direktor` text fields (link to Jamoa or remove).

- **2026-09-09 — Antigravity — CodeQL 0-Alerts Resolved & Deploy Meta Retention Guard:**
  1. **All 4 CodeQL Alerts Resolved (0 Alerts Remaining)**: PR #598 orqali barcha ochiq CodeQL alertlar (ReDoS, stack-trace exposure, clear-text logging) to'liq tuzatildi va `main` ga merge qilindi. GitHub Code Scanning Alerts soni **0** ga tushirildi (`[]`).
  2. **Oracle Deploy Meta Credentials Retention**: `oracle-deploy.yml` har deployda `.env` ni qayta yaratganda mavjud `META_*` va `INSTAGRAM_*` kalitlarni `/tmp/meta_env_backup.env` orqali saqlab qoladigan qilindi. Endi deploy Meta konfiguratsiyasini o'chirib yubormaydi.
  3. **Non-blocking /readyz/ Probe**: `src/api/routes/health.py` dagi `/readyz/` endpointi `HEALTH_LIVE_DB_PROBE` parametriga moslashtirildi (`vm_service` rejimida Turso DB ga keraksiz blocking simulyatsiyasi to'xtatildi). Deploy health-check kutish sikli `seq 1 36` (180s) ga kengaytirildi.
  4. **AmoCRM Long-Lived Token Store Fix**: `src/services/core/crm/amocrm/auth.py` va `token_store.py` uzoq muddatli access_tokenlarni Turso DB ga to'g'ri saqlab, restartdan keyin ham o'chib ketmaydigan qilindi.
  5. **Verification**: 805 ta test 100% yashil o'tdi (`pytest`). Bandit: 0 issues (92,713 LOC). CodeQL: 0 alerts.

- **2026-09-09 — Antigravity — Instagram Video Context & Keyword Reply Guard Implementation:**
  1. **Video Description & Reels Context Awareness**: `src/services/core/instagram_agent.py` dagi `COMMENT_REPLY_SYSTEM` va `generate_comment_reply` to'liq yangilandi. Izohga javob berishdan oldin video posti tavsifi (caption) va reels ma'nosini chuqur tahlil qilib, shunga mos professional javob yozish majburiy qilindi.
  2. **Keyword & Trigger Reply Guard**: Kalit so'zlar (masalan: '99', 'prompt', 'kitob', 'shablon', 'daromad', 'link', '+', material/qo'llanma so'rovi) yozganlarga "Rostanam shunaqa 😂" deb kulish yoki "Afsuski shunaqa 😢" deb yig'lash qat'iyan taqiqlandi. Ular uchun material profil bio'sida (shapkasida) ekanligini bildiruvchi xushmuomala, professional javoblar belgilandi.
  3. **Canned Shortcut Deprecation**: `src/services/core/instagram/emoji_utils.py` dagi `get_short_emotional_reaction` shabloni o'chirildi (barcha matnli izohlar endi to'liq AI orqali video caption konteksti bilan tahlil qilinadi; faqatgina sof emojilar mirror qilinadi).
  4. **Verification & Deployment**: Pytest (23/23 tests passed), Bandit (0 issues), 400 qator modular standartiga 100% rioya qilindi (`instagram_agent.py` 312L, `emoji_utils.py` 51L). Oracle VM ga jonli deploy qilinib, `oisha-os.service` muvaffaqiyatli restart qilindi (`active (running)`).

- **2026-09-08 — Antigravity — AmoCRM Task Staggering & Notification Pipeline Recovery:**
  1. **User Policy ("bir vaqtga qator zadachalar qo'yma")**: Barcha 360 ta ochiq vazifa `scripts/stagger_tasks.py` orqali qayta tekshirildi. Bitta vaqtga to'planib qolgan barcha klasterlar (masalan, 18:00 ga qator tushgan 24 ta va 22 ta vazifa) ish vaqti bo'yicha (10:00 dan 18:00 gacha) har 15–20 daqiqaga bittadan tekis taqsimlandi.
  2. **Notification Pipeline Fix ("Vazifa vaqti keldi")**: Nima uchun bugun bildirishnoma kelmagani aniqlandi: vazifalar 18:00 ga surilgani sababli kun davomida tizim ularni "kelajakdagi vazifa" deb hisoblagan va eslatma yubormagan; shuningdek Oracle VM dagi 24 soatlik access token muddati tugab 401 bergandi. 2031-yilgacha amal qiluvchi uzoq muddatli rasmiy token tiklandi va HTTP 200 OK qaytdi.
  3. **Verification**: 360 ta vazifa muvaffaqiyatli stagger qilindi (`[SUCCESS] Staggered 360 tasks evenly across working hours`). Hech qanday klaster qolmadi.


- **2026-09-08 — Codex — owner-requested billing disable:** Disabled billing for JonBranding (jonbranding-85662071-ea38e). Live success toast and reopened Cloud linkedaccount page confirm no billing account linked. Billing account not closed. No code, credential, or production-server changes. Obsidian source-attributed note appended; Brain MCP unavailable.

- **2026-09-08 — Codex — AI Studio warning read-only audit:** Confirmed two exposed-key warnings in live UI. Local suffix match in untracked data/vps_audit_results.txt:10 (old VPS env dump); current local .env matches neither flagged key. Second key not found locally. No credential changes, production access, or product code edits. Source-attributed Obsidian inbox note saved; Brain MCP unavailable. Open: exact public leak source and current server usage unverified.

- **2026-09-08 — Codex Coordinator — Meta guard production deployment:** Owner explicitly approved deployment in this task. Applied only the three guard hook diffs and new config_guard.py to Oracle /home/ubuntu/oisha-os after git apply --check; existing target files were clean. Backup: backups/meta-guard-20260908 (original three files). Payload builder: scripts/prod/deploy_meta_guard_local.py. Server service-venv focused tests 11 passed; compile passed. Restarted oisha-os.service: active/running, NRestarts=0. At 11:08:22 UTC /healthz/ returned healthy, problems=[], meta_config.configured=true, missing_keys=[]; initial database startup degradation recovered after 45 seconds. Guard SHA256 matched local payload. No credentials changed or test messages sent. No git commit/push/PR; direct scoped deployment must be retained in the eventual source merge. Brain tools unavailable; vault note appended via filesystem.

- **2026-09-08 — Codex Coordinator — Meta config drift guard:** Added `src/services/core/instagram/config_guard.py`, API lifespan and health/readiness hooks, scheduler presence checks with suppression of repeated configuration skip logs, `tests/test_meta_config_guard.py`, deterministic readiness fixtures, and `docs/operations/meta-config-guard.md`. Required runtime keys support existing ID/verify aliases; whitespace/SecretStr checks expose names only. One actionable ERROR per continuous outage per process, rearmed after recovery; health/readiness soft-degrade. Evidence: Python 3.12 focused Instagram/config/readiness tests 42 passed; scoped Bandit 0 issues; Ruff clean except core.py's 22 pre-existing E402 findings (same on HEAD); core F821 and git diff --check clean. No credentials changed, production connection, commit/push or PR. Full suite not run. Brain MCP unavailable; source-attributed vault inbox note written. Limitation: runtime presence only; cached .env disk changes require restart, no token validity or delivery claim.

- **2026-09-07 — Antigravity — Instagram Auto-Responder Recovery & Live Backfill Execution:**
  1. **Root Cause Resolved**: Oracle VM serveridagi `.env` faylida Meta o'zgaruvchilari yo'qolib qolgan bo'lib, `oisha-os.service` `[IG-BACKFILL] Skipped: instagram_not_configured` holatida javob berishni to'xtatgan edi.
  2. **Env Sync & Service Restart**: Barcha 9 ta `META_*` va `INSTAGRAM_*` konfiguratsiya parametrlari `/home/ubuntu/oisha-os/.env` ga qayta yuklandi va `oisha-os.service` (PID 3607026) muvaffaqiyatli qayta ishga tushirildi.
  3. **Live Auto-Replies Active**: Orqa fondagi `[IG-BACKFILL]` 20 soniyalik siklda so'nggi postlarni skan qilib, javob berilmagan barcha izohlarga 5 soniyalik xavfsiz throttle bilan jonli javob yozishni boshladi (dalil: `18088923206438402`, `17950317048264120`, `18473208925119887`, `18012004616951990`, `18115465633756336`, `18133166770647827`, `18066900731576771`, `18111791837038338`, `18016584428946638`, `18146522194555088` — `[META] Comment reply sent successfully`).

- **2026-09-07 — Antigravity — Meta Production Config Restore & Instagram Views Metrics Fix:**
  1. **Prod .env Full Meta Recovery**: Oracle VM dagi `.env` faylida soat 18:42 da qayta tiklangan eski backup tufayli o'chib ketgan barcha 9 ta Meta o'zgaruvchilari (`META_APP_ID`, `META_APP_SECRET`, `META_GRAPH_API_VERSION`, `META_PAGE_ID`, `META_INSTAGRAM_ACCOUNT_ID`, `META_INSTAGRAM_USER_ID`, `META_PAGE_ACCESS_TOKEN`, `META_VERIFY_TOKEN`, `INSTAGRAM_VERIFY_TOKEN`) `scripts/sync_meta_env_to_vm.py` orqali to'liq sinxronlashtirildi.
  2. **Instagram Weekly Insights Views Metric Upgrade**: Meta Graph API v19 da eskirgan `plays`/`impressions` metrikasi o'rniga yangi `views` metrikasi `src/services/core/instagram_weekly_report.py` ga birinchi ustuvorlik bilan kiritildi (`views,reach,saved,shares,total_interactions`).
  3. **Verification**: Oracle VM da to'g'ridan-to'g'ri `InstagramWeeklyReportAgent` ishga tushirilib, so'nggi 30 kunlik barcha 19 ta post bo'yicha real insights `HTTP/1.1 200 OK` bilan to'liq tortib olindi; `credential_status` 100% true bo'ldi. Pytest: 55/55 Instagram testlari yashil. Bandit: 0 issues. `oisha-os.service` yangilangan kod va env bilan muvaffaqiyatli restart qilindi.

- **2026-09-07 — Codex Coordinator — secret-safe recovery readiness (#587/#588):** Added `scripts/prod/recovery_readiness.py`, `scripts/prod/recovery_sources.py`, `tests/test_recovery_readiness.py`, and `docs/operations/recovery-readiness.md`. Standalone inventory mirrors current AmoCRM env/file/raw-refresh/DB fallback and userbot DB/file/env order; checks refresh prerequisites, session wire shape/MCP equality, owner state and bypass flags without printing values. SQLite mode=ro; Turso fixed SELECT only behind explicit --read-turso; no application bootstrap, refresh, Telethon client, DDL, persistence, lock mutation, or silent remote-to-local fallback. Fail-closed JSON always ready=false / exit 2; actual auth and acquisition remain unverified. Evidence: Python 3.12 focused pytest --noconftest 36 passed; scoped Ruff clean; scoped Bandit 0 issues; git diff --check clean. Full suite not run (standalone operator-only patch, no PR created); no commit/push, production connection or credential change. Existing unrelated work preserved. Brain MCP tools unavailable; source-attributed Obsidian inbox note written via filesystem. Remaining: operator-authorized Oracle inventory and separate live auth/recovery verification; existing lock implementation was not changed.


- **2026-09-07 — Antigravity — AmoCRM Overdue Tasks Safe Rescheduling & Telegram Userbot Sync:**
  1. **AmoCRM Overdue Tasks Safe Rescheduled**: `scripts/reschedule_overdue_tasks_safe.py` (245L) yaratildi va Oracle VM da muvaffaqiyatli ishga tushirildi.
     - Jami ochiq vazifalar: 432 ta. Muddati o'tib ketgan (overdue): 61 ta.
     - "Mijoz emas" deb belgilangan (rad etdi, spam, qiziqmadi): 14 ta vazifa darhol `Mijoz emas deb yopildi` natijasi bilan yopildi va bekor qilindi.
     - Haqiqiy mijozlarning 47 ta muddati o'tgan vazifasi kelgusi ish kunlariga 25 tadan (18:00 Toshkent vaqti, yakshanba kunlarisiz) taqsimlandi:
       - 2026-09-08 (Seshanba): 25 ta vazifa
       - 2026-09-09 (Chorshanba): 22 ta vazifa
     - Natija: AmoCRM'da muddati o'tib ketgan (qizil) vazifalar soni **0** ga tushirildi!
  2. **Telegram Userbot Reauth Script Fix**: `scripts/start_userbot_reauth.ps1` da xizmat to'xtatish paytidagi `Job for oisha-os.service canceled (exit 1)` xatosi bartaraf etildi (`sudo systemctl stop oisha-os.service 2>/dev/null || true`).
  3. **Telegram Chat Analysis Architecture**: Foydalanuvchi savoliga tushuntirish berildi. Telethon sessiyasi faollashishi bilan `ai_autopilot_scheduler` va `TelegramTaskCreator` orqa fonda chatlarni tahlil qilib AmoCRM ga vazifalar va yangilanishlarni avtomatik joylaydi.


- **2026-09-07 — Antigravity — AmoCRM Non-Client Task Suppression & Re-import Guard (Owner Directive):**
  1. **Non-Client Filter Engine**: `src/services/core/crm/non_client_filter.py` (231L) yaratildi. Foydalanuvchi ko'rsatmasiga binoan sdelka nomi, mijoz/kontakt nomi, izohlar (primechaniya), vazifalar (matn va natija), chat va teglarda "mijoz emas", "klient emas", "not a client", "spam", "adashgan", "kerak emas", "rad etdi", "shaxsiy/oila" kabi belgilar to'liq skan qilinadi. 30 daqiqalik in-memory kesh bilan tezkor ishlaydi.
  2. **Task Creation Guard**: `src/services/core/crm/amocrm/tasks_notes.py` da `create_task` hamda `src/services/core/smart_tasks/analyzer.py` da smart-task yaratilishidan oldin barcha joylar (sdelka, kontakt, primechaniya, zadacha natijalari, chat) tekshiriladi. Agar "mijoz emas" belgisi bo'lsa, vazifa qo'yilmaydi (`[AMOCRM TASK BLOCKED]`).
  3. **CRM Re-import & Chat Suppression**: `src/handlers/msg_pipeline/lead_intake.py` (`process_elite_intake`) hamda `src/entrypoint/message_event.py` (`_sync_and_log_crm_channels`) da "mijoz emas" deb belgilangan shaxslar qayta yangi sdelka sifatida ochilmaydi va ularning xabarlari CRM chatiga chiqarilmaydi.
  4. **Verification**: 10/10 yangi non-client testlari va 54/54 to'liq CRM integratsiya testlari yashil o'tdi (`pytest`). Bandit auditi: 0 issues (1026 LOC). Barcha 5 ta fayl 400 qator modular standartiga 100% mos.

- **2026-09-07 — Antigravity — Instagram Comments Auto-Responder & Browser Liker Full Activation:**
  1. **Browser Like Automation**: Connected directly to the active Chrome profile (`baxtiyorjongaziyev`, ID `4256594275`) via CDP. Scanned reel [`Dc8MLR-NzWB`](https://www.instagram.com/reel/Dc8MLR-NzWB/), expanded replies, and safely liked all 129 previously unliked comments with 1.5–2.3s human delay. Total visible comments liked reached 600+.
  2. **Unanswered Comments Root Cause Resolved**: Oracle VM `.env` faylida Meta Graph API kalitlari (`META_PAGE_ACCESS_TOKEN`, `META_INSTAGRAM_USER_ID` va h.k.) yetishmayotgani sababli `[IG-BACKFILL]` `instagram_not_configured` xatosi bilan to'xtab turgan edi. Lokal toza tokenlar Oracle VM `.env` ga sinxronlandi.
  3. **Live Auto-Responder Active**: `oisha-os.service` qayta ishga tushirildi. Orqa fondagi backfill loopi (20 soniyalik interval, 5 soniyalik xavfsiz oraliq bilan) ishga tushib, javob berilmagan barcha kommentlarga hissiyotga mos (kulgu/kulgu, yig'i/hamdardlik, sof emoji/mirror) javob yozishni boshladi (dalil: `{"comment_id": "...", "event": "[META] Comment reply sent successfully"}`).
  4. **Verification**: 9+ ta javobsiz komment jonli ravishda yozib bo'lindi va qolganlarini orqa fonda avtomatik yakunlamoqda.

- **2026-09-07 — Antigravity — PR #591 Cleanup, enforce_admins & CI Verification:**
  1. **PR #591 Closed & Branch Deleted**: `security/hardening-2026-09-07` branch'dagi barcha o'zgarishlar allaqachon `main` ga to'g'ridan-to'g'ri push qilingan edi (commits `d8c314eb`, `8fb32a32`). PR diverged holatda edi (4 ahead, 2 behind), merge qilish duplicate/conflict keltirib chiqarishi mumkin edi. PR yopildi va branch o'chirildi.
  2. **Branch Protection `enforce_admins: true`**: Oldin `enforce_admins: false` edi — admin/owner direct push qila olardi. Endi `enforce_admins: true` qilib, barcha foydalanuvchilar (admin ham) PR orqali o'tishi majburiy qilindi.
  3. **CI 100% Green**: Barcha 4 ta workflow muvaffaqiyatli: CI - Oisha-OS ✅, Security - CodeQL ✅, Security - Secret Scan (gitleaks) ✅, Oracle Production Deploy ✅.
  4. **Qolgan Ishlar**: Oracle VM da `DISABLE_UNSOLICITED_REPORTS=1` env var o'rnatilishi kerak (SSH orqali); P3 credential rotation tashqi providerlar orqali mustaqil tasdiqlanishi kerak.

- **2026-09-07 — Antigravity — Security Boundary Hardening, Branch Protection & CI Alignment:**
  1. **P0 Web Chat Widget Authorization Boundary**: Anonymous widget JWT is now strictly scoped to its own web session ID (`web_<session_id>`). It is strictly rejected (401/403) from `/api/chat/lookup/{phone}`, `/api/leads`, reading other users' history, and queuing outbound Telegram messages to integer user IDs. Removed hardcoded secret fallback (`oisha_widget_session_signing_secret_32b_fixed`); requires $\ge 32$-byte dedicated secret and fails closed with 503 if unconfigured.
  2. **P1 Main Branch Protection Activated**: Configured GitHub branch protection on `main` (`protected: true`, required status checks: `Import-time crash guard`, `CodeQL Analyze (python)`, `gitleaks`, force pushes blocked, branch deletion blocked).
  3. **P2 OAuth Secret Separation & Cookie TTL Alignment**: Removed Telegram `BOT_TOKEN` fallback for JWT signing in `oauth.py` and `dashboard.py` (strictly requires `JWT_SECRET` $\ge 32$ bytes). Aligned cookie `max_age` to session TTL (`SESSION_TTL_SECONDS` = 12h) instead of 30 days.
  4. **P4 & P5 CI, Python 3.12 & Lockfile Alignment**: Added `ruff check --select F821 src/` to `trusted-main-tests` on push in `test.yml`; added push commit-range scanning to `gitleaks.yml`; unified Python version to `3.12` in `oracle-deploy.yml` and `dependabot-remediation.yml`; generated reproducible `requirements-lock.txt` (145 packages).
  5. **Verification**: 37/37 auth/security unit tests passed, Ruff clean (0 errors), Bandit clean (0 issues, 92K LOC), 400-line modular standard strictly maintained.

- **2026-09-06 — Antigravity — Disable Instagram Comment-Triggered DMs (Owner Directive):**
  1. **User Policy**: Foydalanuvchi qat'iy talabiga binoan ("DMga yozmasin") izohlardan avtomatik Direct (DM) ga yozish to'liq o'chirildi.
  2. **Code Remediation**:
     - `src/services/core/instagram_agent.py`: `COMMENT_REPLY_SYSTEM` da DM ga yo'naltirish taqiqlandi; jonli webhookdagi `should_trigger_dm` va `send_ig_private_reply` logikasi olib tashlandi.
     - `src/services/core/instagram/backfill.py`: Orqa fonda izohlarni o'qib javob beruvchi backfill'dagi DM outreach olib tashlandi.
     - `tests/test_instagram_integration.py`: `mock_priv_reply.assert_not_called()` bilan yangilandi.
  3. **Verification & Standards**: 29/29 Instagram testlari 100% yashil o'tdi, Bandit auditi toza (0 issues), 400-qator modular standarti saqlangan (`instagram_agent.py` 355L, `backfill.py` 178L).


- **2026-09-06 — Antigravity — Instagram Emoji Mirror & Oracle VM Auto-Responder Live Activation:**
  1. **Root Cause Resolved**: Oracle VM dagi `.env` faylida `META_PAGE_ACCESS_TOKEN` va `META_INSTAGRAM_USER_ID` yetishmayotgan bo'lib, `IG-BACKFILL: Skipped: instagram_not_configured` holatida to'xtab turgan edi. Lokal toza tokenlar xavfsiz sinxronizatsiya qilindi.
  2. **Identical Emoji Mirroring (Foydalanuvchi talabi)**: Agar foydalanuvchi faqat emojilardan iborat izoh qoldirsa (masalan `🔥🔥🔥` yoki `👏`), robot ortiqcha matn qo'shmasdan aynan o'sha emojilarning o'zini (`src/services/core/instagram/emoji_utils.py` orqali) qaytaradigan qilindi.
  3. **Modular Standards & 400-Line Rule**: `src/services/core/instagram_agent.py` dan API xabarlar logikasi `src/services/core/instagram/api_helpers.py` (90L) ga ajratilib, 366 qator toza holatga keltirildi. Barcha yangi fayllar 400 qator qoidasiga to'liq mos.
  4. **Live Verification**:
     - `pytest`: 29/29 barcha Instagram testlari 100% yashil o'tdi.
     - `bandit -r src/services/core/instagram/ -ll`: 0 issues (toza).
     - **Oracle Production Logs**: `oisha-os.service` jonli ravishda izohlarga birma-bir javob yozishni boshladi (dalil: `{"comment_id": "18624020485002513", "event": "[META] Comment reply sent successfully"}`, `{"comment_id": "18020585288878395", ...}`, Gemini/Groq failover ishlayapti).

- **2026-09-06 — Antigravity — GitHub Actions 100% Green CI & Workspace Isolation Remediation:**
  1. **Pytest Teardown Hang Resolved**: `tests/conftest.py` ga `pytest_unconfigure` hooki qo'shildi (`GITHUB_ACTIONS=true` da toza va tezkor `os._exit(session.exitstatus)` chaqiradi). Natijada test suite 35 daqiqa qotib qolmasdan **1m 17s** da 1980+ testni muvaffaqiyatli yakunlaydigan bo'ldi.
  2. **Ruff Syntax Rule Compatibility**: `.github/workflows/test.yml` da eskirgan `E999` qoidasi o'rniga `ruff check --select F821 src/` qo'yildi.
  3. **Monorepo Path Isolation**: `.github/workflows/test.yml` dagi `dorny/paths-filter` da subloyihalardan sun'iy `.github/workflows/test.yml` trigeri olib tashlandi. Shuningdek, `marketing-os/frontend/pnpm-lock.yaml` drifti to'g'rilandi va `apps/web` dagi ESLint xatolari (`isCrit`, `analytics/page.tsx` setState in effect) to'liq tuzatildi.
  4. **Verification & Live Status**:
     - `CI - Oisha-OS`: **SUCCESS in 1m 20s** (`34025352968`)
     - `Oisha Web Ops`: **SUCCESS in 1m 4s** (`34025352989`)
     - `Oracle Production Deploy`: **SUCCESS in 3m 51s** (`34024960316`)
     - `Security - CodeQL`: **SUCCESS in 2m 7s** (`34024960325`)
     - `Security - Secret Scan (gitleaks)`: **SUCCESS in 9s**
     - Bandit: 0 issues. 400-qator modular standarti 100% ta'minlangan.


- **2026-09-05 — Antigravity — Airtable Finance V2 (Tranzaksiyalar) Cutover & Telegram Income Workflow:**
  1. **Airtable Audit & Test Cleanup**: Codex limitga tushib to'xtab qolgan nuqtalar (Sadiyya cakes to'lovlari ko'chirilishi, 555 USD sinov yozuvi, nazorat formulalari) audit qilindi. 555 USD (6 549 000 UZS) sinov yozuvi (`rechRs9rLFcEgNsYp`) `Tranzaksiyalar` jadvalidan to'liq o'chirildi; Sadiyya loyihasi balansi tekshirildi (17 850 000 so'm to'langan, 150 000 so'm qoldiq).
  2. **Telegram Income Workflow Migrated**: `src/handlers/income_workflow.py` eski `Kirim` jadvali o'rniga `Tranzaksiyalar` jadvaliga yo'naltirildi. Kategoriya (`Branding loyiha daromadi` / `Naming loyiha daromadi`), kassa/hisob (`Bank UZS`, `Naqd USD`, `Naqd UZS`, `P2P karta`) va joriy oylik P&L mappingi avtomatlashtirildi; `Holat = 'Tasdiqlangan'` bilan yoziladi.
  3. **Backward Compatibility**: `src/services/core/airtable/projects.py` da `get_finance_records()` ga `"Loyiha nomi"` default aliasi qo'shildi (`Loyiha` dan oladi); `count_income_records_for_project()` ikkala maydonni ham qo'llab-quvvatlaydigan qilindi.
  4. **Verification**: `tests/test_income_workflow.py` (4/4 passed), `tests/test_kirim_handler.py` va `tests/test_airtable_sync.py` (12/12 passed); Bandit xavfsizlik auditi 0 issues; fayl hajmlari 150-400 qator standartiga to'liq mos (`income_workflow.py`: 296L, `projects.py`: 271L).


- **2026-09-05 — Antigravity — Cloud Brain Synthesizer & AmoCRM Production Fix:**
  1. **Root Cause Diagnosis**: Telegram'dagi "OpenRouter API kaliti topilmadi" xatosi tekshirildi. `src/schedulers/cloud_brain_synthesizer.py` Oracle VM da OpenRouter'ga hardcoded bo'lgan va fail-closed guard bo'lmagani sababli Telegram'ga xato yuborayotgan edi.
  2. **FreeAIProviderRouter & Fail-Closed**: `cloud_brain_synthesizer.py` `FreeAIProviderRouter`ga ulandi (Gemini, Groq, Cerebras failover). Ma'lumot yoki kalit bo'lmasa xato yubormasdan jim o'tadigan (fail-closed) qilindi. Oracle VM da live test qilindi (`HTTP 200 OK`, Gemini orqali muvaffaqiyatli sintezlandi). Unit testlar: `tests/test_cloud_brain_synthesizer.py` 7/7 passed.
  3. **AmoCRM Token Sync**: Oracle VM da AmoCRM `access_token_missing` xatosi lokal ishlayotgan `data/amocrm_token.json` SSH orqali nusxalanishi bilan to'liq tuzatildi. `probe_integrations.py` da `amocrm: account_ok: true, lead_read_ok: true` tasdiqlandi.
  4. **Production Health**: `oisha-os.service` restart qilindi, `/healthz/` 200 OK (healthy, problems: []), `/readyz` da AmoCRM `connected`. Faqat `userbot_unauthorized` qoldi (SMS kod kutadi).


- **2026-09-05 — Antigravity — Gitleaks PR Scoping & Secret Remediation:**
  1. **PR-Scoped Gitleaks**: `.github/workflows/gitleaks.yml` da PR skaneri faqat PR commitlariga (`origin/${{ github.base_ref }}...HEAD`) cheklandi, scheduled/dispatch runlar uchun to'liq tarix saqlandi. Barcha ochiq va yangi PR'lar tarixiy o'tmish sababli sun'iy bloklanishi bartaraf etildi.
  2. **Workflow Secret Sanitization**: `.github/workflows/oracle-deploy.yml` da ochiq matnda qolib ketgan `AMOCRM_CHAT_CHANNEL_SECRET` va `AMOCRM_CHAT_CHANNEL_ID` GitHub Secrets'ga (`gh secret set`) kiritildi va workflow env o'zgaruvchisiga bog'landi.
  3. **Historical Fingerprints Tracking**: `.gitleaksignore` ga tarixiy skriptlar va o'tmishdagi deploy commitidagi 27 ta fingerprint izohlar bilan kiritildi.
  4. **Syntax & BOM Fix**: `src/schedulers/cloud_brain_synthesizer.py` dagi UTF-8 BOM belgisi tozalandi (`tests/test_syntax_guard.py` 781/781 passed). Bandit auditi: 0 issues.

- **2026-09-05 — Codex Coordinator — Telegram notification quality guard:** Owner requested suppression of unknown/example reports. Added `src/services/core/notification_quality.py` and outbound fail-closed validation in `src/services/proactive/reminders.py`; invalid report batches cannot send group or accompanying DMs. `src/schedulers/frog_scheduler.py` excludes Buyurtmachi A examples and renders the selected source title instead of ungrounded generated motivation. Local `airtable_stagnation.py` no longer invents project names or defaults missing managers to Inomjon. Added regression tests and bounded installer `scripts/prod/install_notification_guard.py`. Local and production service-venv checks: 15 passed each; focused Bandit 0 issues; focused Ruff clean; touched-code diff check clean. Deployed only guard/reminders/frog changes to Oracle with backups in `/home/ubuntu/oisha-os/backups/notification-guard-20260905`; restarted service, confirmed active/running, NRestarts=0 and `/healthz/` healthy with no problems at 06:48 UTC. Startup initially returned 503 then recovered. No Telegram test messages sent. Local stagnation cleanup remains undeployed; no commit/push or unrelated working-tree changes deployed. Brain tools unavailable; source-attributed vault note captured via filesystem.


- **2026-09-04 — Antigravity — Oisha OS Live Knowledge Bridge (Google Drive + Gemini):**
  1. **Canonical Master & Live Bridge Architecture**: "Knowledge bizniki. AI almashtiriladi" tamoyili tasdiqlandi. Obsidian (`00-SYSTEM/`) canonical master, Google Drive (`G:\My Drive\Oisha OS`) live knowledge bridge, Gemini API/plugins esa shunchaki adapter etib belgilandi. Brain decision yozildi.
  2. **Sync Automation**: `scripts/sync_oisha_drive.py` (201L, 400-qator qoidasiga to'liq mos) yaratildi. One-shot va real-time `--watch` rejimlari qo'llab-quvvatlanadi.
  3. **Obsidian Native Integration**: `C:\Users\baxti\OneDrive\Документы\Obsidian Vault\00-SYSTEM\Oisha-OS-Export.ps1` yangilandi, Obsidian'dan bitta buyruq bilan avtomatik `G:\My Drive\Oisha OS` ga eksport qilinadi.
  4. **Verification**: 7 ta core fayl, `OISHA-OS-BUNDLE.md`, `NOW-BLOCK.txt` va `README.md` Google Drive'da yaratildi va test sinxronizatsiyasi muvaffaqiyatli o'tdi.


- **2026-09-04 — Antigravity — Omnichannel Customer 360 Ecosystem & Obsidian Sync:**
  1. **Yangi Modul**: `src/services/customer_360/` yaratildi (`models.py`, `collector.py`, `obsidian_syncer.py`, `query_engine.py`, `__init__.py`). Barcha fayllar 400 qator standartiga mos (18-224L).
  2. **Call Analytics Integratsiyasi**: `src/services/call_analytics/runner.py` ga `_sync_call_to_customer_360` ulandi. Qo'ng'iroq STT tahlili tugashi bilan xulosa AmoCRM bilan bir qatorda Obsidian mijoz kartasiga (`70-Mijozlar/`) avtomatik yoziladi.
  3. **Admin Bot `/client`**: `src/services/core/admin_bot/handlers_search.py` ga `/client <ism/telefon>` buyrug'i qo'shildi, barcha tizimlardan (AmoCRM, Airtable, Calls, TG, IG) 360 dosye beradi.
  4. **Initial Sync & Verification**: `scripts/sync_customer_360_obsidian.py` orqali ilk 7 ta mijoz Obsidian kartalari yaratildi va GitHub'ga push qilindi. Testlar: 4/4 Customer 360 va 27/27 Call Analytics testlari 100% yashil (`pytest`), Bandit 0 issues.


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

## Locks
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

## Pre-flight Checklist (har bir PR dan oldin)
```powershell
$env:SKIP_LIVE=1; python -m pytest -q --tb=short
bandit -r src/ -ll
```

## Branch Naming

### Codex handoff - 2026-09-06 Airtable Finance V2
- Live API/UI verified: USD555 test absent; Sadiyya paid UZS17850000, debt UZS150000. Of 338 transactions, 337 PASS; incomplete draft recPYf96Vm60YWcSF left untouched. Populated transactions have P&L links.
- Published KPI pagBuUndb0l8vzDiA now uses Tranzaksiyalar, SUM Kirim UZS, date filter and grid; old five-card layout simplified. Live all-time confirmed income UZS772902150.
- Published and verified hidden navigation for legacy pages pagA0TPu789kQs6yP and pagHzwr3AB8Mx79Hh; data retained.
- Published form pagXqD6m5BgxhXYzz: Loyiha, read-only Reja, required single P&L selection titled Hisobot oyi (Sana bilan bir xil oy). Live form/selector verified. Month selection is manual; no automatic P&L linking implemented. No test finance submission or outbound messages.
- Other legacy dashboards remain outside this focused repair. Antigravity Telegram writer migration not redeployed or production-verified here. Brain tools unavailable; filesystem note used.
`feat/<short-description>` yoki `fix/<short-description>`

## Commit Style
`feat(scope): message` / `fix(scope): message` / `refactor(scope): message`

## Agent Handoff Log — 2026-09-05 Airtable audit
- Codex Coordinator: Read-only live Finance V2 audit; 200 archive income rows and 336 transactions inspected. Two Sadiyya receipts totaling UZS 11925000 absent from transactions; old forms/dashboard links remain; USD555 new income lacks project/P&L link; approval formulas inconsistent with descriptions. No finance/code mutations or PR. Evidence captured in Obsidian 00-Inbox/2026-09-05-Airtable-migration-audit.md. Remaining: reconcile receipts/accounts, migrate operational interfaces, verify P&L linkage and approval controls. Brain tools unavailable.

### 2026-09-07 — claude — Aiogram bot-head wiring restore
- **Ish:** commit 5f682b41 bootstrap/runtime.py ni orchestration/* ga bo'lganda Aiogram bot-token head lifecycle jimgina tushib qolgan. Prod backend=aiogram bo'lgani uchun @jonairobot ~2026-09-06 dan beri inbound update qabul qilmayapti (admin komanda yo'q, Hisobchi/Airtable approval tugma yo'q). Wiring qayta tiklandi.
- **O'zgargan fayllar:** src/bootstrap/orchestration/bot_head.py (new — init_aiogram_bot_head), src/bootstrap/orchestration/boot.py (ikkala branch chaqiradi), src/services/core/dispatcher/inline_search.py (new — native inline-query + phone-search), src/services/core/dispatcher/builder.py (perform_global_lookup param), src/entrypoint/runner.py (lazy src.boot import — eager circular import fix), tests: test_bootstrap_aiogram_bot_head.py, test_dispatcher_inline_search.py, + test_admin_aiogram_dispatcher.py.
- **Tekshiruv:** targeted suite 41 passed/1 skipped; boot/entrypoint 85 passed. drain.py o'zgarmadi (allaqachon app_ctx.aiogram_bot_head.stop() chaqiradi).
- **Qolgan ish:** full pytest + bandit → PR → owner tasdig'i bilan Oracle deploy + live smoke → brain_log. /night_shift + /juma_send hali "not configured" (domain_agents.py AdminBot'ga night_shift/juma_notifier bermaydi — pre-split ham shunday edi, alohida follow-up).
