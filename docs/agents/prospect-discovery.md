# Oisha potensial mijoz qidiruvi

2026-10-13. Birinchi versiya Telegram-first: xizmatga aniq ehtiyoj yozilgan
postlarni owner ruxsat bergan kanal/superguruhlardan topib, tekshirish navbatiga
saqlaydi. Bu hujjat ishlab chiqilgan xatti-harakatni tushuntiradi; production
deploy yoki real lid topilganini tasdiqlamaydi.

## Owner va menejer oqimi

Oisha userbotining mavjud admin buyruq yo'li, private chat / Saved Messages:

1. `/lead_sources discover` — mavjud dialoglardan ochiq biznes/networking
   kanal va superguruhlarini nom bo'yicha tavsiya qiladi. 250 dialoggacha,
   20 tavsiyagacha; yangi guruhga qo'shilmaydi. Nom manba sifati isboti emas.
2. `/lead_sources add @kanal` yoki `/lead_sources add -100…` — owner
   manbani o'qish mumkinligini tekshirib, allowlistga qo'shadi.
3. `/lead_scan` — hozir skanerlaydi; holat va yangi yozuvlar sonini chiqaradi.
4. `/lead_candidates` — oxirgi 10 potensial mijoz: xizmat, iqtibos, xabar
   havolasi, xabar/tekshiruv vaqti, matnda bo'lsa telefon va keyingi qadam.
5. `/lead_auto on` — restartdan keyin ham saqlanadigan avtomatika. Oracle
   runtime'dagi mavjud channel scout scheduler orqali har soatda, Toshkent
   07:00–23:00 oralig'ida navbat yangilanadi. Default off.
6. `/lead_auto off`, `/lead_sources remove <chat_id>` — to'xtatish/o'chirish.

Admin whitelist navbatni ko'ra oladi; manbalar va avtomatikani faqat owner
o'zgartiradi. Telegram userbotning mavjud authorization gate'i saqlangan.

## Qamrov va dalil

- Har manbada oxirgi 7 kun, ko'pi bilan 200 xabar; limitga yetsa
  `window_limited`, umumiy natija `partial`. To'liq tarix skanerlandi deyilmaydi.
- Branding, qadoqlash, sayt va dizayn + aniq talab so'zlari bir gapda
  bo'lishi kerak. Xizmat sotish, vakansiya va inkor postlari chiqariladi.
- Bu qoida asosidagi saralash; matn noaniq bo'lsa xato musbat/manfiy bo'lishi
  mumkin. Yangi filial haqidagi e'lonning o'zi xarid niyati deb belgilanmaydi.
- Budjet va xarid muddati `None`; qualification `needs_review`.
- Takroriy matn+xizmat hash orqali DB darajasida chiqariladi. Bir postdagi
  turli xizmatlar alohida ehtiyoj bo'lishi mumkin. Bu kompaniya/CRM dublikati
  tekshirildi degani emas; CRM holati `unchecked`.
- Manba xatosi `source_unavailable`, nol lid sifatida ko'rsatilmaydi.
- Navbat `database_pool.py` orqali saqlanadi. Hech qanday sessiya ochilmaydi,
  lokal userbot ishga tushmaydi. Mijozga avtomatik xabar yoki CRM yozuvi yo'q.

## Release tekshiruvi

Focused: `rtk python -m pytest tests/test_prospect_discovery.py -q --tb=short`.
PR oldidan repo pytest va Bandit gate'lari o'tishi shart. Deploydan keyin
Oracle'da source add/read-back, bitta scan, takroriy scan, navbat read-back,
auto on/off va restart persistence tekshiriladi. Test fixture'lari sintetik;
ular operatsion navbatga kiritilmaydi.
