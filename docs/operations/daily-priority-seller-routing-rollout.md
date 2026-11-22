# DailyPriority: sotuvchi bo‘yicha shaxsiy vazifalar — production release checklist

## Maqsad va chegaralar

Shahnoza, Rayxona va Mumtozmaxal bitta amoCRM loginida ishlaydi. 09:30 dagi Oisha DailyPriority xabari faqat bitimning haqiqiy egasiga borishi kerak. Egasi aniq bo‘lmasa, mijoz maʼlumotini boshqa sotuvchiga yuborish taqiqlanadi.

Bu PR **amoCRM task_notifier umumiy guruh eslatmalarini shaxsiy Telegramga o‘tkazmaydi**. Avvalgi Work sessiyasidagi `delivery.py` kodi hali `main`da yo‘q. Buni alohida release sifatida yakunlash kerak.

## Sourceʼlardan tasdiqlangan holat

- 2026-11-21 brauzerdagi jonli amoCRM `Сделки` sahifasida **Sotuvchi** maydoni mavjud; ko‘rinadigan qiymatlar **Rayxon, Shahnoza, Mumtozmaxal**.
- Har uch sotuvchi uchun saqlangan **faol bitimlar** filtrlari bor; “Nazorat — sotuvchi belgilanmagan” filtri ham bor.
- 2026-10-26 rejada esa **Menejer** maydoni yaratish taklif qilingan. Bu tarixiy reja, real API maydon ID tasdig‘i emas.
- `src/services/core/leads/assignment.py` yangi lidni `sotuvchi:<xodimning to‘liq ismi>` tegi orqali belgilaydi. Qayta biriktirilganda eski teg saqlanib qolishi mumkin.
- UIʼdagi filtr URLʼida `filter[cf][1559389]=empty` ko‘ringan. Bu **Sotuvchi field ID bo‘lishi mumkin, lekin metadata API orqali tasdiqlanmaguncha production parametriga kiritilmasin**.
- 2026-11-20 dagi boshqa dry-run 589 ta ochiq taskni topgan; bu DailyPriority egasini tasdiqlovchi hisobot emas.

## 1. Lokal/CI tekshiruv

```bash
python -m pytest -q tests/test_daily_priority.py tests/test_daily_priority_ownership.py tests/test_probe_daily_priority_seller_routes.py
ruff check src/services/core/daily_priority/ownership.py src/services/core/daily_priority/gatherer.py scripts/prod/probe_daily_priority_seller_routes.py tests/test_daily_priority_ownership.py tests/test_probe_daily_priority_seller_routes.py
```

Repo `AGENTS.md` pre-flight ko‘rsatmalariga muvofiq qolgan tekshiruvlar (security / Uzbek text guard) ham o‘tsin.

## 2. Jonli read-only audit

Serverda amoCRM tokeni va ishchi virtualenv mavjud, kodning shu branchʼi alohida checkoutda sinovdan o‘tgach:

```bash
python scripts/prod/probe_daily_priority_seller_routes.py --max-pages 20
```

Bu skript **CRMʼdagi bitimlar, vazifalar va teglar uchun faqat GET** ishlatadi; Telegram xabar yubormaydi, token/mijoz identifikatorlarini logga chiqarmaydi. Mavjud amoCRM autentifikatsiya yuklagichi tokenni ishga tushishda ichki autentifikatsiya bazasiga sinxronlashi mumkin; bu CRM biznes yozuvlariga tegmaydi. Tokenni HTTP orqali refresh qilish uchun POST avtomatik yuborilmaydi: token yaroqsiz bo‘lsa diagnostika to‘xtaydi.

Hisobotdan tekshiriladiganlar:

1. `verified_seller_fields`: APIʼdan topilgan haqiqiy maydon nomi va IDʼsi. “Sotuvchi” mavjudligi va IDʼsi tasdiqlansin.
2. `verified_seller_leads`: 3 sotuvchi bo‘yicha tasdiqlangan bitimlar soni. Kutilmagan nol chiqsa release to‘xtatiladi.
3. `unassigned_or_conflicting`: maydoni yo‘q, tanib bo‘lmagan yoki qarama-qarshi tegli bitimlar; odam tomonidan tekshiriladi.
4. `truncated`: biror bosqich to‘liq olinmagan bo‘lsa, auditni to‘liq deb hisoblamang.
5. “Kelishuv / Yopish” va arxivdagi “Shartnoma tayyorlanmoqda” status IDʼlari jonli pipelineʼga mosligini tasdiqlang.

## 3. Xavfsiz ishga tushirish

1. Uchtadan kamida bittadan **sintetik yoki maxsus tasdiqlangan** sotuvchi-bitim juftligida ega aniqlanishini tekshirish; haqiqiy mijozning maxfiy maʼlumotini test xabarida ko‘rsatmaslik.
2. API metadataʼda tasdiqlangan raqamlar bilan `DAILY_PRIORITY_SELLER_FIELD_IDS` ni serverdagi maxfiy konfiguratsiyada sozlash (masalan: `id1,id2`; **taxminiy raqam yozilmasin**).
3. `DAILY_PRIORITY_ENABLED=0` orqali DailyPriority xabarlarini vaqtincha to‘xtatish, jarayonni konfiguratsiya bilan qayta ishga tushirish.
4. CI hamda pre-flight yashil, haqiqiy audit qoniqarli, ziddiyatli egaliklar ajratib chiqilganidan keyingina PRʼni `main`ga squash merge qilish va tegishli release jarayonidan chiqarish.
5. Ish vaqtidan oldin owner nazoratida yoqish; Rayxona, Shahnoza va Mumtozmaxalning har biri faqat o‘z bitimidan xabar olganini tekshirish.
6. Mijoz maʼlumoti noto‘g‘ri odamga yuborilsa, **darhol** `DAILY_PRIORITY_ENABLED=0`, jarayonni to‘xtatish va xabar manbasini tekshirish. “Oldingi versiyani qaytarish” ham audit va ehtiyot choralarisiz qilinmasin.

## 4. Eski va yangi teg ziddiyati

- Masalan, bitta leadʼda `sotuvchi:Rayxona Rahimova` va `sotuvchi:Shahnoza Abdijabborova` qolsa, avtomatik tanlash **taqiqlanadi**.
- Eski tegni qaysi birini olib tashlash **jonli amoCRMʼdagi oxirgi tasdiqlangan biriktirishni o‘rganmaguncha avtomatlashtirilmasin**. Boshqa teglar saqlansin.
- Bu PR qayta biriktirish yozuvlarini o‘zgartirmaydi; konfliktlarni reviewʼga yuboradi.

## 5. Qabul mezonlari

- [ ] APIʼda Sotuvchi/Menejer field ID metadata bilan tasdiqlangan.
- [ ] Shaxsiy Telegramga yuborishda boshqa sotuvchi bitimi chiqmaydi.
- [ ] Uchala sotuvchi bo‘yicha test bitimlari aniq taqsimlangan.
- [ ] Ziddiyatli yoki nomaʼlum bitimlar shaxsiy xabarga tushmaydi.
- [ ] CI, xavfsizlik testlari, pre-flight yashil.
- [ ] Joriy versiyada 09:30 DailyPriority ishlashi kuzatilgan.
- [ ] AmoCRM task_notifierʼni shaxsiyga yuborish alohida PRʼda sinovdan o‘tkaziladi.

**Holat:** ishlab chiqish va testlar PR’da. Live read-only tekshiruvni bajarilmagan bo‘lsa bajarildi deb belgilangani yo‘q.


## 6. GitHub orqali keyingi read-only nazorat

PR asosiy branch'ga merge bo'lgach, GitHub Actions sahifasidan **DailyPriority Seller Routing Audit (Read Only)** workflow'ini ochib **Run workflow** ni tanlang; branch: main, max_pages: 20.

Bu workflow Hetzner runner'ida alohida checkout qiladi; production ishchi checkout'iga git stash, git reset, git checkout, API PATCH yoki Telegram send qilmaydi. Faqat agregatsiya natijalari GitHub Actions logida ko'rinadi.

**Muhim:** workflow default branch'da mavjud bo'lmaguncha GitHub Actions interfeysidan Run workflow tugmasi ko'rinmasligi mumkin. Merge oldidan jonli auditni alohida worktree/checkout'da mavjud server virtualenv'i bilan bajaring. Jonli audit o'tmasdan merge qilishni release tasdig'i deb hisoblamang.
