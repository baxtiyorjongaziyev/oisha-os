# Antigravity uchun davom ettirish prompti

Quyidagi topshiriqni Oisha-OS checkoutida davom ettir. Owner Baxtiyorjon JonBranding uchun Oisha ichida sayt va amoCRM bilan ishlaydigan CAPI platformani, AdSinc/capip auditini, dalilli PRD va harness loop bilan tekshirilgan natijani so'ragan. Bu topshiriq real tekshiruv va implementatsiya uchun; avvalgi hisobotlarni joriy holat isboti deb qabul qilma.

## Birinchi vazifa: owner kirishini yakunlash

Owner hozir `Oisha-OS Enterprise — Tizimga kirish uchun Telegram orqali tasdiqlang` ekranini ko'ryapti. Widget bot: jonairobot; origin: https://oisha.jonbranding.uz; return route: /api/auth/telegram/login?next=/api/marketing/capi/console. Telegram autentifikatsiyasini owner o'zi bajaradi. Parol, token yoki kodni chatga so'rama. Kirgach haqiqiy brauzer holatini qayta o'qi: konsol ochildimi, session cookie ishlaydimi, redirect loop yoki 401/403 bormi? Faqat login ekranining ochilishi CAPI ishlayotganini isbotlamaydi.

2026-10-14 Codex qayta tekshirgan lokal HEAD: dc49c165; oldingi commitlar 8fc5f355 (Telegram login redirect va /capi), 4308e699 (Targetolog CAPI automation #876). Bu commitlar mavjudligi production deploy isboti emas. Checkout juda dirty; boshqa ishlarni saqla. Eski Codex tekshiruvidan keyin Antigravity implementatsiyasi, PRD va handofflar qo'shilgan. Shu sabab eski RED testlar yoki eski "deploy qilinmagan" xulosasini joriy fakt sifatida takrorlama.

## Ish boshlash tartibi

- AGENTS.md, CLAUDE.md, docs/oisha-prd.md, docs/agents/three-agent-workflow.md, docs/agents/code-standards.md va .agents/skills/capi-platform/SKILL.md ni o'qi.
- brain_context va kerak bo'lsa brain_search; mavjud vosita bo'lmasa cheklovni yoz. Sirlarni o'qima yoki saqlama.
- Bir checkoutda bir implementer. Faol qulflarni hurmat qil; o'z fayllaringga lock qo'y, tugagach olib tashla. Reviewer kodni o'zgartirmasin.
- Barcha shell buyruqlarini rtk bilan boshlagin. Lokal userbotni ishga tushirma; SKIP_LIVE=1, ALLOW_LOCAL_RUN=0.
- git status/diff va mavjud PR/branchni tekshir; reset, checkout bilan tozalash, stage-all yoki main'ga push qilma.
- scripts/ralph/loop.ps1 ni tekshirmasdan ishga tushirma: oldingi tekshiruvda dirty fayllarni yo'qotadigan checkout buyrug'i bor edi.

## Mavjud implementatsiya va dalillar

Oisha: src/services/core/marketing/capi_platform{,_schema,_store}.py; src/api/routes/capi_platform.py; src/api/templates/capi_platform.html; src/api/security.py; src/services/api_server/core.py. Contract: docs/capi-platform.md. Testlar: tests/test_capi_platform.py, tests/test_capi_platform_hardening.py, tests/test_meta_capi.py va targetolog automation testlari.

Sayt: C:/Users/baxti/projects/jonbranding-web; src/lib/oisha-capi-delivery.ts, analytics-delivery.ts, services/lead-types.ts, submit-form route va adapter testi. Joriy branch/statusni qayta tekshir. Server intake sozlamalari OISHA_CAPI_URL va OISHA_CAPI_INGEST_SECRET; qiymatlarini chiqarmagin. Bir xil event uchun Oisha yo'li tanlanganda parallel direct Meta yuborish bo'lmasin.

Avvalgi Codex lokal tekshiruvi: 83 scoped test; website 422 test va build o'tgan edi. Keyin 4 hardening regressiyasi RED bo'lgan. Keyingi Antigravity handofflari ularning tuzatilganini da'vo qiladi — bugungi run bilan tekshir. Eski full gate: 13 skill mirror tafovuti va src/api/auth.py dagi Bandit B307; ularning hozirgi holati noma'lum.

Haqiqiy Claude Code read-only review avval bajarilgan (o'sha paytdagi Oisha kodi uchun); bu keyingi kodning review'i emas. Website adapter o'sha review qamroviga kirmagan. Codex yordamchi agentlari benchmark va harness tahlilini bajargan. Antigravity bilan o'sha Codex sessiyasida to'g'ridan-to'g'ri agent chat almashinuvi bo'lmagan; bu fayl handoff hisoblanadi.

## Qayta tekshiriladigan xavfsizlik va ishonchlilik shartlari

1. Website bearer source=crm bilan Purchase/QualifiedLead yasay olmasin (403). CRM faqat ishonchli ichki manbadan.
2. Bir event_id bir xil payload bilan idempotent; o'zgargan payload bilan aniq conflict. Dataset va test/live alohida.
3. Doimiy Meta 400 xatosi terminal rejected; vaqtinchalik 429/5xx backoff bilan retry. Expired status API va DBda bir xil.
4. Cookie orqali mutatsiya uchun to'g'ri Origin talab qilinsin; yo'q yoki begona Origin 403. RBAC intake credential'dan alohida.
5. Yangi outbox va legacy capi_events bir CRM hodisasini ikki marta yubormasin. Legacy retry original event_time ni o'zgartirmasin; target provenance noma'lum bo'lsa ko'r-ko'rona replay qilinmasin.
6. Durable enqueue oldin, 202 keyin; atomik lease va stale worker completion himoyasi. Producer receiptgacha nosozlikda hodisa yo'qolish xavfini bahola.
7. Faqat events_received=1 transport qabulini tasdiqlaydi. EMQ, attribution, savdo yoki ROAS o'sishi alohida dalil talab qiladi.
8. Haqiqiy consent, hash qilingan kontaktlar, sirlarning log/UIga chiqmasligi, payload retention/purge, operator audit, rate limit va credential rotation holatini tekshir.
9. Noma'lum qiymatlarni nolga aylantirma. Purchase haqiqiy musbat qiymat va ma'lum valyutaga ega bo'lsin; turli valyutalar bilan ROAS hisoblama.

## Platformalar auditi: tasdiqlangan qamrov va ochiq joylar

Manbalar: https://adsinc.uz/dashboard/projects va https://capip.uz/uz/projects/2f237347-a274-405e-9c08-ab71488eccaf/connections. Oldingi browser audit read-only bo'lgan; yangi holatni qayta ko'r.

AdSinc: 0 loyiha bo'lgani uchun Dashboard/Kampaniyalar/Analitika/Leadlar/Xaridlar/Hisobotlar/Integratsiyalar/Tarif ichki ekranlari ochilmagan. Projects, Workspace, account Settings, til/account menu va loyiha yaratish dialogining ikki qadami ko'rilgan, yaratish bekor qilingan. CRM Attribution 240 000 so'm/oy, Meta Reports 50 000 so'm/oy takliflari UI'da ko'rilgan; bu xarid emas. Biznes turi, biznes modeli va asosiy KPI tanlovlari ko'rilgan. Owner mavjud loyiha yoki demo ochishini aytgan; ochilganini tekshir. Pulli loyiha yaratma.

capip: Connections (Meta, amoCRM, Bitrix24, capiCRM, Telegram, capiVoice), Hisobot (sana/kogorta/taqqoslash/guruhlash), Revenue, Leads filtrlar, Ads va 27 ustun tanlash dialogi, Forms/webhook ko'rsatmalari, Events, Settings, Teams va bo'sh Launch ko'rilgan. CRM ulanmagani uchun Funnel, real lead detail, event retry va kampaniya boshqarish amallari to'liq sinalmagan. Connect/save/archive/invite/subscribe/create/pay kabi mutatsiyalar bajarilmagan. Ulanmagan hisobotlarda nol ko'rsatilishi kuzatilgan. Settings/webhook ekranida secret ko'rinishi mumkin — raw snapshot yoki screenshotni sir bilan saqlama.

Har tugma uchun jadval tuz: sahifa, tugma, holat, read-only bosish natijasi, blok sababi, Oisha talabi. "Ko'rildi", "bosib tekshirildi", "disabled", "autentifikatsiya kerak", "mutatsiya bajarilmadi" ni ajrat. Har bir tugma audit qilindi deb yolg'on yozma.

## PRDni dalil bilan tuzatish

Mavjud docs/oisha-capi-platform-prd.md ni takror yaratma, tekshir va yaxshila. 2026-10-14 Codex o'qiganda unda dalilsiz global #1 reytinglari, aniq EMQ diapazonlari/narxlar, raqib ma'lumotlari shifrlanmasligi haqidagi da'vo va "1.0.0-PROD/tasdiqlangan" yozuvlari bor edi. Birlamchi manba yoki owner tasdig'i bo'lmasa olib tashla yoki tekshirilmagan deb belgilagin. Ichki backend mavjudligi 100% in-house PII degani emas: Meta'ga matching ma'lumoti uzatiladi.

Global yagona eng yaxshi platforma isbotlanmagan. JonBranding uchun Stape Signals Gateway funksional benchmark nomzodi; bu maslahat, o'lchangan global reyting emas. Manbalarni qayta tekshir:
- https://stape.io/helpdesk/documentation/signals-gateway-overview
- https://stape.io/helpdesk/documentation/how-to-configure-signals-gateway
- https://developers.google.com/tag-platform/tag-manager/server-side/intro
- https://support.kommo.com/docs/set-up-meta-conversions-api-capi

Kommo messaging CAPI hujjatini amoCRMning barcha manbalari qo'llab-quvvatlanadi deb talqin qilma. Stape'da native amoCRM connector mavjudligi oldingi auditda tasdiqlanmagan.

PRD asosiy scope: JonBranding ichki ulanishlar, website+CRM event oqimi, diagnostika/retry, stage mapping, lead manbasi va haqiqiy xarajat/tushum dalillariga tayangan hisobot. Billing SaaS, yangi CRM va avtomatik reklama sarfi MVP uchun majburiy emas. Har talabga acceptance ID, ma'lumot manbasi va tekshiruv qo'sh. Yetishmayotgan ma'lumotlar va tashqi bog'liqliklarni yoz.

## Harness loop va yakun

Observe → kichik reja → bir implementer o'zgarishi → fokuslangan behavior test → haqiqiy mustaqil review → tuzatish → full gates → owner kirishi bilan live read-back → handoff. Testni yashil qilish uchun talabni kuchsizlantirma.

Avval CAPI/auth focused suite, Ruff va scoped Bandit; keyin loyiha talabidagi full pytest va full Bandit. Website o'zgarsa verify/build. scripts/harness/run_harness.py ni o'qib, mos holda ishlat; real natijani saqla. Har muvaffaqiyatsizlik sababini o'zgarish yoki oldindan mavjud blocker sifatida ajrat.

Owner autentifikatsiyasidan so'ng brauzerda console, status, RBACni tekshir. Production deploy holatini vakolatli manbadan tekshir. Tashqi test hodisasi yuborishga vakolat mavjudligini aniqlab, sintetik eventni aniq belgilab, Meta Test Events va server receipt bilan tekshir; haqiqiy savdo yozuvi yaratma. Queue, Meta qabul, matching va attributionni alohida ko'rsat.

Yakuniy javob sodda o'zbekcha: bajarildi/qisman/ochiq, PRD/audit fayllari, test dalili, commit/push/merge/deploy/live tekshiruv alohida. docs/agents/handoff-log.md oxiriga qayd qo'sh; brain vositalari mavjud bo'lsa loyiha faktlarini manbasi bilan append va brain_log qil. Tasdiqlanmagan da'volarni boshqa agent nomidan yozma.
