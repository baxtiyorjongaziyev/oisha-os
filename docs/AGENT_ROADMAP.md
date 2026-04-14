# Oisha Agent Roadmap

## Maqsad
Oisha-ni tarqoq botlar va cron-lardan iborat avtomatlashtirish to'plamidan
bitta boshqariladigan, kuzatiladigan va tekshiriladigan AI agentga aylantirish.

## 1-bosqich: Runtime Yagonaligi
- Bitta canonical runtime qoldirish: `main.py`
- Legacy runnerlar (`userbot.py`, eski VM service, alohida workerlar)ni audit qilish
- Tungi avtomatik xabarlar va dublikat schedulerlarni bloklash
- Cloud Run va VM vaqt zonalarini `Asia/Tashkent` ga birxillashtirish

Status:
- `Cloud Run` uchun quiet-hours va timezone guard joriy qilindi
- `VM` dagi legacy `src/main.py` runtime uchun quiet-hours va timezone guard joriy qilindi
- `send_evening_fact_report()` endi quiet-hours ichida va `daily plan` bo'lmaganda Telegramga xabar yubormaydi

## 2-bosqich: Yagona State va Persistence
- `daily_plans`, scheduler state va memory uchun bitta source of truth tanlash
- Local SQLite, VM SQLite, Cloud Run ephemeral disk va Turso orasidagi chalkashlikni yo'qotish
- Job dedupe persistent storage orqali ishlashini kafolatlash

Status:
- Joriy canonical state backend sifatida `data/bot.db` (SQLite) tanlandi
- Runtime health va storage health endpointlari qo'shildi: `/api/system/runtime`, `/api/system/health`
- Job execution audit trail va recent runs endpointi qo'shildi: `/api/system/traces`

Deliverables:
- Scheduler state storage qarori
- Runtime health + storage health endpoint
- Job execution audit trail

## 3-bosqich: Planner / Executor Ajratilishi
- Agentni 3 rolga ajratish:
- Planner: nima qilishni hal qiladi
- Executor: action bajaradi
- Verifier: natijani tekshiradi

Status:
- `src/services/core/agent_loop.py` ichida minimal `Task -> Plan -> Execute -> Verify` sikli qo'shildi
- Daily plan, CRM stagnation va Airtable stagnation pushlari endi agent loop orqali audit log qoldiradi
- Executor va verifier xatolari endi failure reason bilan loglanadi

Deliverables:
- Task object modeli
- Queue / job runner
- Retry va failure reason logikasi

## 4-bosqich: Tool Layer Standartlashuvi
- Telegram, AmoCRM, Airtable, Sheets, Calendar kabi integratsiyalarni adapter qatlamga ko'chirish
- Har bir external action uchun timeout, retry, idempotency va log qo'shish

Status:
- `src/services/core/tool_registry.py` qo'shildi va `ToolResult` schema standartlashtirildi
- `src/services/core/tool_adapters.py` orqali Telegram, AmoCRM va Airtable uchun birlamchi adapter qatlam qo'shildi
- `daily plan`, `sales conversion push` va `PM stage push` oqimlari yangi adapter qatlam orqali ishlaydigan qilindi

Deliverables:
- `tool registry`
- `action result` schema
- external API failure policy

## 5-bosqich: Guardrails
- Quiet-hours
- Manual vs automatic action permissionlari
- Owner approval talab qiladigan actionlar
- Spam, duplicate-send va destructive action bloklari

Status:
- `src/services/core/agent_policy.py` qo'shildi va scheduler actionlari uchun `auto_actions`, `quiet_hours`, `approval_required` gate'lari qo'shildi
- `src/services/core/agent_verifier.py` qo'shildi va notification delivery uchun alohida verifier ishlaydigan qilindi
- `_run_notification_agent()` endi policy -> execute -> verify oqimini alohida log bosqichlari bilan yuritadi

Deliverables:
- policy config
- per-action safety checks
- operator override mode

## 6-bosqich: Observability
- Har bir agent action uchun:
- sabab
- input
- output
- status
- retry
- source runtime

Status:
- API endi runtime source, service name, runtime id va userbot auth holatini ko'rsatadi
- Legacy runtime inventory endpointi qo'shildi: `/api/system/inventory`
- Recent scheduler joblar va agent actionlar dashboard/API uchun tayyorlandi

Deliverables:
- dashboardda agent trace
- VM / Cloud Run source marker
- critical alert stream

## Keyingi Reja
1. VM va Cloud Run ichidagi legacy runnerlarni bosqichma-bosqich o'chirib, faqat `main.py` ni qoldirish
2. Telegram, AmoCRM va Airtable actionlarini bitta adapter qatlamga ko'chirish
3. Owner approval va manual-vs-auto policy guardlarini kuchaytirish
4. Dashboardda agent trace va critical alert stream ni vizual ko'rsatish

## Bugun Bajarilgan Ish
1. Tungi `02:00` dagi spam Cloud Run emas, VM dagi legacy runtime ekanligi isbotlandi
2. VM dagi `/home/baxti/oisha-os` repoga quiet-hours patch tushirildi
3. `oisha.service` restart qilindi va yangi guardlar aktiv holatga keldi
4. API ga runtime, storage, traces va inventory observability endpointlari qo'shildi
5. Canonical state backend sifatida `data/bot.db` tanlanib, runtime contextga chiqarildi
6. Daily plan, sales conversion push va PM stage push oqimlari minimal agent loop bilan loglanadigan qilindi
7. Telegram, AmoCRM va Airtable uchun adapter qatlam qo'shilib, uchta asosiy proactive flow policy/verifier bilan agent layerga ulangani
