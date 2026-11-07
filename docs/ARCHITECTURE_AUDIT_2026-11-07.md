# Oisha-OS arxitektura auditi

## Umumiy baho: 5.5/10

- Asosiy qism yaxshi bo'laklarga ajratilgan: oldingi katta `main.py` bootstrap/orchestration'ga bo'lingan, guardrail'lar va webhook imzolari bor.
- Eng katta xavf xavfsizlikda: `/api/crm/dialer/*` umuman autentifikatsiyasiz ochiq turibdi.
- Ma'lumotlar qatlami mo'rt (bitta umumiy connection, write'larni qayta yuborish, SQLite'ga jim o'tish), background task'lar esa nazoratsiz ishlaydi.

## Kuchli tomonlar

- `main.py` va `boot.py` yupqa facade bo'lib qolgan. Wiring `src/bootstrap/orchestration/` ichida va bosqichlarga bo'lingan.
- Anti-local lock birinchi bo'lib ishga tushadi. AuthKeyDuplicated holati ushlanadi va jarayon yiqilmasdan cheklangan rejimda davom etadi. SIGTERM'da cheklangan drain va ownership lock'ni bo'shatish bor.
- API xavfsizligining asosi to'g'ri qurilgan: global middleware sukut bo'yicha himoyalaydi, `hmac.compare_digest` ishlatiladi, JWT HS256'ga qotirilgan, trusted-proxy header faqat loopback'dan qabul qilinadi. Meta, Moizvonki va Payme webhook'lari sir bo'lmasa so'rovni rad etadi (fail closed). CORS `allow_credentials=False`.
- `AgentPolicyEngine` qoidalari aniq va har qaror tekshiruvlari bilan birga strukturali `PolicyDecision` qaytaradi. `free_ai_router`'da circuit breaker bor.
- Deploy'da import-crash guard va alohida `/healthz` hamda `/readyz` tekshiruvlari bor. PR kodi prod runner'da ishlamaydi. MCP systemd unit'lari himoyalangan (hardened).
- SQLite fallback WAL rejimida ishlaydi. Tayyor `MigrationRunner` bor, faqat hali ishlatilmagan.

## Muammolar (jiddiylik bo'yicha)

### CRITICAL

**1. `/api/crm/dialer/*` autentifikatsiyasiz: lid PII o'qiladi va mijozlarga xabar yuboriladi**
- Fayllar: `src/api/security.py:251`, `src/api/routes/crm_dialer.py`, `src/services/api_server/core.py:183`
- Nima uchun: `/api/crm/dialer/` va `/api/moizvonki/` prefikslari middleware'dan chiqarib qo'yilgan, route'larda esa hech qanday `Depends` yo'q. Internetdagi istalgan odam lidlarning telefon va emaillarini o'qishi, CRM'ni o'zgartirishi va `/inbox/send` orqali real mijozlarga agentlik nomidan, o'zi tanlagan `sender_name` bilan xabar yuborishi mumkin. Bu yo'lda quiet-hours ham, approval ham ishlamaydi. `"*"` CORS bu muammoni brauzer orqali ham kuchaytiradi.
- Tuzatish: prefiks istisnosini olib tashlash va faqat aniq public auth yo'llarini qoldirish. Router darajasida seller-session yoki admin `Principal` dependency qo'shish. Outbound yuborishni `agent_policy` va `auto_reply_gate` orqali o'tkazish. CORS'ni aniq allowlist bilan almashtirish.

### HIGH

**2. Seller PIN login'da rate limit ham, lockout ham yo'q**
- Fayllar: `src/api/routes/crm_auth_routes.py`, `src/services/core/crm/seller_auth.py`, `src/services/api_server/core.py:29`
- Nima uchun: PIN 4 xonali, urinishlar soni hisoblanmaydi, `/sellers` slug'larni autentifikatsiyasiz ochib beradi. Natijada ≤10k so'rov bilan 30 kunlik sessiyani qo'lga kiritish mumkin. Limiter proxy IP (127.0.0.1) bo'yicha ishlaydi, shuning uchun limit hammaga umumiy bo'lib qoladi. Seller'ning telefoni bo'sh bo'lsa, `endswith("")` har qanday raqamga mos keladi.
- Tuzatish: slug va IP bo'yicha lockout qo'shish, PIN'ni uzunroq qilish. uvicorn'da `proxy_headers` va `forwarded_allow_ips=127.0.0.1` ni yoqish. Bo'sh telefonlarni rad etish.

**3. Bitta umumiy libsql connection lock'siz, bir nechta thread'dan ishlatiladi**
- Fayl: `src/database_pool.py:54-144`
- Nima uchun: `asyncio.to_thread` orqali parallel statement'lar bitta handle ustida ishlaydi va `close()` boshqa thread ishlatib turgan handle'ni yopib yuborishi mumkin. Mavjud "stream not found" va panic retry'larining sababi shu bo'lishi ehtimoli bor, lekin bu isbotlanmagan.
- Tuzatish: `asyncio.Lock` qo'shish yoki haqiqiy pool qilish. Handle'ni faqat undan foydalanayotgan chaqiruvlar tugagandan keyin yopish.

**4. Write'lar avtomatik qayta yuboriladi, transaction esa amalda ishlamaydi**
- Fayllar: `src/database_pool.py`, `src/db/turso.py:166-198`
- Nima uchun: INSERT/UPDATE ham 5 martagacha qayta yuboriladi, bu dublikat to'lov va lid qatorlarini keltirib chiqarishi mumkin. commit va rollback global connection'ga ta'sir qiladi. `TursoAdapter.close()` butun jarayonning connection'ini uzib qo'yadi.
- Tuzatish: retry'ni faqat o'qishlar va idempotent deb belgilangan write'lar uchun qoldirish. Connection'ga bog'langan transaction yoki batch API qo'shish. Umumiy pool uchun `close()` hech narsa qilmasin (no-op).

**5. Turso'dan SQLite'ga jim o'tish split-brain yaratadi**
- Fayl: `src/db/connection.py:46-81`
- Nima uchun: Turso bir zum uzilsa, write'lar faqat warning bilan `data/bot.db` ga ketadi va keyin hech qachon Turso bilan solishtirilmaydi.
- Tuzatish: prod'da fail-closed yoki read-only rejimga o'tish. Qaysi backend ishlayotganini `/readyz` da ko'rsatish va alert berish. Agar fallback baribir kerak bo'lsa, outbox orqali Turso'ga replay qilish.

**6. Background loop'lar fire-and-forget: supervisor ham, health signal ham yo'q**
- Fayllar: `src/bootstrap/orchestration/schedulers.py:24-78`, `src/bootstrap/orchestration/boot.py`, `src/bootstrap/orchestration/domain_agents.py`, `src/entrypoint/daemon_tasks.py`
- Nima uchun: taxminan 15 ta loop oddiy `create_task` bilan ishga tushiriladi, na reference saqlanadi, na done-callback qo'yiladi. Bitta loop o'lsa, `/readyz` baribir "online" deydi. Finance, CRM va Instagram hisobotlari jim to'xtab qolishi mumkin.
- Tuzatish: `TaskSupervisor` qo'shish: strong ref saqlash, done-callback'da log yozish, backoff bilan restart qilish, har bir task liveness'ini `/readyz` ga chiqarish.

**7. Userbot kutilmaganda uzilsa graceful shutdown o'tkazib yuboriladi**
- Fayllar: `src/bootstrap/orchestration/boot.py:237-244`, `src/bootstrap/orchestration/drain.py`
- Nima uchun: `graceful_drain` chaqirilmaydi. Ownership lock TTL tugaguncha band qoladi va systemd restart kechikadi. DB yozuvlari ham yarmida uziladi.
- Tuzatish: drain'ni `try/finally` ichida ikkala holatda ham chaqirish va non-zero exit bilan chiqish.

**8. Uchta parallel LLM router bor, ko'p modullar Gemini'ni to'g'ridan-to'g'ri chaqiradi**
- Fayllar: `src/agents/ai_router.py`, `src/agents/router_pkg/`, `src/services/utils/free_ai_router.py`, `src/services/utils/gemini_failover/engine.py`, `src/services/core/advisor_agent.py:42`, `src/services/core/audit_agent.py:37`, `src/agents/core.py:44`
- Nima uchun: 33 ta faylda `genai.Client` bor, `free_ai_router` ni esa faqat 26 tasi ishlatadi. Failover, cost va quota har joyda turlicha ishlaydi. Router barcha exception'larni yutib yuboradi, `ENABLE_PAID_AI_FALLBACK` esa ulanmagan.
- Tuzatish: bitta gateway qoldirish, boshqalarini uning ustidagi yupqa wrapper'ga aylantirish, gateway'dan tashqarida `genai.Client` ni lint bilan taqiqlash. Failover faqat httpx va timeout xatolarida ishlasin.

**9. `AgentPolicyEngine` faqat `MinimalAgentLoop` ichida ishlaydi**
- Fayllar: `src/services/core/agent_policy.py`, `src/services/core/agent_loop.py:63`, `src/services/proactive/formatters.py:183`
- Nima uchun: quiet-hours, yakshanba bloki, approval va sensitive terms faqat proactive yo'lda tekshiriladi. MessageController, scheduler'lar va openclaw_bridge ularni chetlab o'tadi. Bundan tashqari, `auto_master` sukut bo'yicha `True` va mijozga tegishli bo'lmagan action'lar uchun approval va `auto_actions_enabled` tekshiruvlaridan oldin `checks={}` bilan qaytadi, ya'ni audit izi qolmaydi.
- Tuzatish: policy tekshiruvini tool adapter'lar chegarasiga (`tool_adapters_pkg/telegram.py`, `amocrm.py`) ko'chirish. `auto_master=False` qilish yoki uni approval tekshiruvidan keyin qo'llash. `checks` ni har doim to'ldirish.

**10. Prod server ayni paytda self-hosted CI runner ham**
- Fayllar: `.github/workflows/oracle-deploy.yml:83-84`, `instagram-plus-campaign.yml:10,40`, `amocrm-*.yml`, `juma-greeting.yml`, `userbot-vps.yml`
- Nima uchun: soatlik auto-mode Instagram kampaniyasi va AmoCRM job'lari live userbot bilan bitta 8GB serverda ishlaydi. Workflow buzilsa, hujumchi to'g'ridan-to'g'ri prod'ga tushadi. Bu biznes logikasi ilovaning policy va audit tizimidan tashqarida qolgan.
- Tuzatish: biznes cron'larini ilova scheduler'iga yoki systemd timer'larga ko'chirib, policy ostiga olish. Runner'ni faqat deploy uchun qoldirish va past huquqli user ostida ishlatish.

### MEDIUM

**11. Shutdown drain cheksiz loop'larni kutadi**
- Fayllar: `src/entrypoint/daemon_tasks.py:22-68`, `src/bootstrap/orchestration/drain.py:26-32`
- Nima uchun: drain qo'lda yuritiladigan allow-list bo'yicha ishlaydi, `daily_frog`, `channel_scout`, `meta_health` va boshqa loop'lar unda yo'q. Shu sabab har bir deploy to'liq 25 soniya kutadi va pending task'lar cancel qilinmaydi.
- Tuzatish: faqat handler sifatida belgilangan task'larni drain qilish, daemon'larni avval cancel qilish, deadline'dan keyin qolganlarini ham cancel qilish.

**12. `src.main` global namespace sifatida ishlatiladi va ikki marta yuklanadi**
- Fayllar: `src/main.py:20-44`, `src/bootstrap/orchestration/boot.py:32`, `src/schedulers/main_loop/*`, `deploy/oisha.service:15`
- Nima uchun: `python3 src/main.py` bilan ishga tushirilganda `__main__` va `src.main` ikki alohida modul bo'lib qoladi. `m.*` ni o'qiydigan kod doim `None` ko'radi. `crm_and_tasks.py:40` mavjud bo'lmagan `get_surgical_integration` ni import qiladi. `schedulers/main_loop` amalda o'lik kod.
- Tuzatish: global'larni olib tashlash, bog'liqliklarni aniq inject qilish yoki `app_ctx` dan olish. `src/scheduler.py` va `main_loop` ni o'chirish. `src/` ichidan `import src.main` ni taqiqlovchi test qo'shish.

**13. `app_ctx.get_surgical_integration` hech qayerda o'rnatilmaydi**
- Fayllar: `src/commands/crm.py:93`, `src/commands/dashboard.py:49`, `admin_commands.py:74/130/163`, `src/entrypoint/message_event.py`, `src/schedulers/bg_monitor/helpers.py`
- Nima uchun: AmoCRM fallback yo'li `TypeError` bilan yiqiladi yoki job jim o'tkazib yuboriladi.
- Tuzatish: `controllers.surgical_integration.get_surgical_integration` ni to'g'ridan-to'g'ri import qilish va fallback yo'li uchun test yozish.

**14. `ApplicationContext` service-locator God object, `__setattr__` esa async ish boshlaydi**
- Fayl: `src/context.py:46-149`
- Nima uchun: taxminan 45 ta `Any` maydon bor, maydonga qiymat berish env'ni o'qishi va yangi task yaratishi mumkin. Shu tufayli yashirin side effect'lar paydo bo'ladi.
- Tuzatish: SalesCoach o'rnatilishini aniq boot bosqichiga ko'chirish, kontekstni typed sub-context'larga bo'lish.

**15. Pool'ni chetlab o'tadigan taxminan 34 ta raw sqlite connect va o'nlab alohida .db fayllar**
- Fayllar: `src/api/web_auth_store.py:23` (nisbiy yo'l), `src/services/core/crm/dialer_store.py`, `src/services/core/marketing/attribution_store.py`, `src/services/core/leads/lead_source.py` va boshqalar
- Nima uchun: bu ma'lumotlar Turso'ga tushmaydi va backup qilinmaydi. Sync chaqiruvlar event loop'ni bloklaydi.
- Tuzatish: muhim store'larni (auth, attribution, dialer, leads) Database/pool'ga ko'chirish, qolganlarini absolyut data dir bilan ishlaydigan bitta helper orqali o'tkazish, yangi `sqlite3.connect` ni lint bilan taqiqlash.

**16. `MigrationRunner` ishlatilmaydi, sxema tasodifiy `ALTER TABLE` bilan o'zgaradi**
- Fayllar: `src/db/migrations/__init__.py`, `src/db/repositories/base.py:10-20`
- Nima uchun: taxminan 30 ta `ALTER TABLE` bor, xatolar string bo'yicha "benign" deb yutib yuboriladi. Prod'da qaysi sxema versiyasi turgani noma'lum.
- Tuzatish: `MigrationRunner` ni boot'ga ulash, `CREATE`/`ALTER` larni raqamlangan migratsiyalarga ko'chirish, `schema_version` ni `/readyz` da tekshirish.

**17. Moliya ma'lumotlarining egasi aniq emas (Airtable, Sheets, DB)**
- Fayllar: `src/services/core/finance/income_supervisor.py:156-177`, `src/services/core/finance/gsheets/client.py`, `src/schedulers/moliya/moliyachi_sources.py`
- Nima uchun: bir xil faktlar bir nechta tizimga yozilishi mumkin va ular solishtirilmaydi. Bu kodda to'liq tasdiqlanmagan, qisman xulosa.
- Tuzatish: bitta system of record e'lon qilish, qolganlarini bir tomonlama projection qilish va reconciliation tekshiruvi qo'shish.

**18. CI/CD va hujjatlarda hali ham Oracle nomi, prod esa Contabo**
- Fayllar: `CLAUDE.md:240-241,262,304`, `oracle-deploy.yml:29`, `oracle-health.yml`, `oisha-web.yml:35-99`, `juma-greeting.yml:35`
- Nima uchun: `ORACLE_HOST` secret eski IP'ga ishora qilayotgan bo'lishi mumkin. Agentlar va odamlar noto'g'ri serverni nishonga olishi mumkin.
- Tuzatish: secret'ni `PROD_HOST` ga almashtirib, 109.199.100.137 ekanini tasdiqlash. Workflow'lar va runner label'ini qayta nomlash, CLAUDE.md'ni tuzatish.

**19. Systemd unit'lar uch xil, deploy vaqtida qo'shimcha drop-in yoziladi**
- Fayllar: `deploy/oisha.service`, `ops/oisha.service`, `deploy/systemd/oisha-watchdog.service`, `oracle-deploy.yml:387-421`
- Nima uchun: repo source of truth emas, unit `sed` bilan joyida o'zgartiriladi. Bu allaqachon bir marta watchdog nosozligiga olib kelgan.
- Tuzatish: bitta kanonik `deploy/systemd/oisha-os.service` va checked-in drop-in qoldirib, deploy'da `install` bilan o'rnatish. Qolgan unit fayllarini o'chirish.

**20. Ikki xil scheduling tizimi: in-process loop'lar, systemd timer'lar va GHA cron**
- Fayllar: `src/scheduler.py`, `src/schedulers/`, `deploy/systemd/*.timer`
- Nima uchun: nima qachon ishlashini ko'rsatadigan yagona ro'yxat yo'q, gate'lar esa notekis qo'llanadi.
- Tuzatish: har bir job, uning qayerda ishlashi va qaysi gate ostida ekanini ko'rsatuvchi bitta schedule registry yaratish. Oxirgi ishga tushish holatini DB'da saqlash.

**21. Tashqi uptime monitoring yo'q**
- Fayllar: `oracle-health.yml` (faqat `workflow_dispatch`), `deploy/systemd/oisha-watchdog.service`
- Nima uchun: server yoki tarmoq to'liq tushib qolsa hech qanday alert kelmaydi.
- Tuzatish: public `/readyz` ni tashqaridan tekshiradigan scheduled probe qo'shish va Telegram'ga alert yuborish.

**22. Ikki parallel FastAPI qatlami**
- Fayllar: `src/api/`, `src/services/api_server/`
- Nima uchun: auth va dashboard ikki daraxtga bo'lingan. Xavfsizlik uchun muhim fayllar (`oauth.py`, `telegram_seamless_auth.py`, `webhooks.py`) CLAUDE.md'da hujjatlanmagan joyda turibdi.
- Tuzatish: bitta HTTP paketiga birlashtirish va CLAUDE.md'ni yangilash.

**23. Guardrail'larning testlari kam**
- Fayllar: `tests/`, `src/services/core/agent_policy.py`, `src/controllers/message_controller.py`
- Nima uchun: `agent_policy` va `message_controller` uchun alohida test fayli yo'q (faqat `test_agent_action_layer.py` ularga tegadi).
- Tuzatish: quiet-hours chegaralari (23:00/07:00), approval va `auto_reply_gate` rejimlari uchun table-driven testlar yozish.

### LOW

- **Config uch xil usulda o'qiladi.** `settings`, `config.py` shim va to'g'ridan-to'g'ri `os.getenv` (`schedulers.py:26`, `context.py:33`, `runner.py:62-64`). Tuzatish: barcha flag'larni `AppSettings` ga e'lon qilish va `settings.py` dan tashqarida `os.getenv` ni taqiqlash.
- **Boot funksiyasi uzun va protsedural.** Control-plane va bot-only "park-forever" rejimlari SIGTERM handler'dan oldin qaytadi, shuning uchun ularda drain yo'q. API wiring takrorlangan. Tuzatish: boot'ni fazalarga bo'lish va signal handler'ni har qanday branch'dan oldin o'rnatish.
- **API `0.0.0.0:8080` ga bog'langan** (`dashboard.py:392`). Firewall ochiq bo'lsa, Nginx chetlab o'tiladi. Tuzatish: sukut bo'yicha `127.0.0.1`.
- **Legacy `OISHA_API_SECRET` tekshiruvi** (`src/api/auth.py:212-222`). Secret bo'sh bo'lsa, `Bearer ` header admin huquqini beradi. Hozircha bu kodni chaqiradigan joy yo'q, ya'ni xavf yashirin. Tuzatish: bu branch'ni o'chirish.
- **Auth tizimlari to'rt xil** (Principal, OrgContext, seller session, internal-secret). Tuzatish: bitta Principal resolver qoldirish.
- **Meta verify-token** oddiy `==` bilan solishtiriladi (`instagram_routes.py:40`). Tuzatish: `hmac.compare_digest`.
- **Orchestrator nomlari to'qnashadi** (`AgentOrchestrator` va `PipelineOrchestrator`), facade ustiga facade quriladi, negotiation implementatsiyasi ikkita.
- **`ToolResult` deyarli ishlatilmaydi.** Faqat 6 ta fayl unga murojaat qiladi, agentlarning birortasi ham uni qaytarmaydi.
- **`sales_staff_copilot.py` byte-for-byte nusxa** (`src/schedulers/` va `src/services/core/`).
- **No-op `background_crm_audit_task`** hali ham ro'yxatga olingan (`dashboard.py:200-209`, `daemon_tasks.py:45`).
- **Mavjud bo'lmagan `src/services/debug/` va `src/legacy/`** hujjatlarda va bandit `-x` flag'ida hali ham tilga olinadi.
- **`services/core` tekis katalog:** 144 ta modul, taxminan 23.8k qator.
- **Hujjatlar bir-biriga mos kelmaydi:** `ARCHITECTURE.md` bor-yo'g'i 1.5K'lik qoralama. Dockerfile'lar ikkita va ikkalasi ham 3.12, hujjatda esa 3.11 deyilgan. Timer unit'larda `ReadWritePaths` yo'q.
- **Polyglot repo:** ikkita SalesCoach workspace, 34 ta workflow, ularning bir qismi bir martalik.

## Top-5 qadamlar (tartib bilan)

1. **Shu bugun:** dialer va moizvonki istisnosini yopish, `crm_dialer_router` ga auth dependency qo'shish, `/inbox/send` ni policy va gate ostiga olish. CORS `"*"` ni olib tashlash. PIN login'ga lockout qo'shish va `proxy_headers` ni yoqish. API'ni `127.0.0.1` ga bog'lash.
2. **DB xavfsizligi:** `database_pool` ga lock qo'yish, retry'ni faqat o'qishlar uchun qoldirish, haqiqiy transaction API qo'shish. Prod'da SQLite fallback'ni o'chirish (fail-closed) va backend'ni `/readyz` da ko'rsatish.
3. **Runtime ishonchliligi:** `TaskSupervisor` qo'shish (ref, callback, restart, liveness). Userbot uzilganda ham `graceful_drain` chaqirish. Drain'ni handler-tag modeliga o'tkazish. Tashqi `/readyz` probe'ni Telegram alert bilan ulash.
4. **Guardrail'larni markazlashtirish:** `AgentPolicyEngine` ni tool adapter chegarasiga ko'chirish, `auto_master` default'ini tuzatish, policy va `auto_reply_gate` uchun table-driven testlar yozish. LLM chaqiruvlarini bitta gateway'ga birlashtirish.
5. **Ops va hujjat tozaligi:** biznes cron'larini prod runner'dan ilova scheduler'iga ko'chirish. Bitta kanonik systemd unit qoldirish. `ORACLE_HOST` ni `PROD_HOST` ga almashtirish. CLAUDE.md va `ARCHITECTURE.md` ni Contabo haqiqatiga moslab yangilash. `MigrationRunner` ni ishga tushirish.