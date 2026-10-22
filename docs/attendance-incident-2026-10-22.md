# Davomat deployidan keyingi uzilish tekshiruvi

Tekshiruv: 2026-10-22. Insident oynasi owner xabariga ko'ra 08:45–08:55 UTC, ya'ni Toshkentda 13:45–13:55. Sayt va Next.js javob bermagani, keyin tiklangani owner aytgan ma'lumot. Mustaqil uptime yoki HTTP access jurnali olinmagan.

## Tasdiqlangan dalillar

- [PR #936](https://github.com/baxtiyorjongaziyev/oisha-os/pull/936) 08:38:14 UTC da merge qilingan.
- [Deploy run 39749227796](https://github.com/baxtiyorjongaziyev/oisha-os/actions/runs/39749227796) 08:38:18 UTC da boshlangan. 08:41:28.770 UTC da `SUCCESS: Oisha Oracle production sog'lom` va readiness natijasida `ready:true` qayd etilgan. Bu faqat shu vaqtdagi backend probe; keyingi 10 daqiqaning sog'lomligi emas.
- 08:39:42 UTC da ko'rsatilgan `sites-enabled/oisha.conf` da `/` fallback 8080 backendga yo'nalgan. Shu host uchun umumiy "Next.js alohida, demak backend ta'sir qilolmaydi" xulosasi noto'g'ri bo'lishi mumkin. Hozirgi yuklangan HTTPS konfiguratsiyasi tasdiqlanmagan.
- [Run 39751426332](https://github.com/baxtiyorjongaziyev/oisha-os/actions/runs/39751426332) 08:55:31 UTC da boshlangan, ammo unda `Oracle VM healthy deploy` job **skipped**. Uni servisni qayta ishga tushirib tiklagan deploy deb ko'rsatish mumkin emas.
- Kodda `_ready_db()` birinchi davomat chaqiruvini schema DDL va bootstrap tugaguncha kutdiradi. `_schema_lock` faqat davomat initini ketma-ketlashtiradi; boshqa modullarni himoya qilmaydi.
- `DatabasePool` bitta libsql ulanishini ulashadi. `execute` va `commit` amallari worker threadga chiqariladi, ammo `get_connection()` sinxron. Per-query timeout native threadni to'xtatishni kafolatlamaydi. Driver lock/GIL xatti-harakati yoki Turso kutishi prod dalilisiz insident sababi deb belgilanmaydi.

## Cheklangan tuzatish

FastAPI lifespan endi davomatning mavjud idempotent schema/bootstrap initini so'rovlarni qabul qilishdan oldin bajaradi. Tayyor bo'lgach `_ready_db()` cache orqali qaytadi, birinchi davomat so'rovi migratsiya boshlamaydi. Init davomiyligi sekundda logga yoziladi. Jadval/CHECK cheklovlari va shared pool tranzaksiya modeli o'zgarmaydi.

Buning narxi: API startup davri uzayadi; schema init xatosi ASGI startupni to'xtatadi. Deploy health grace bilan tekshirilishi kerak. Bu shared ulanish contentionini barcha bootstrap xizmatlaridan ajratmaydi. Shu patchni "butun sayt uzilishi tuzatildi" deb atash mumkin emas.

## Sababni aniqlash uchun qolgan dalillar

Vakolatli operator 08:40–09:00 UTC oralig'i uchun quyidagilarni tekshiradi. Loglarda shaxsiy ma'lumot va sirlarni niqoblaydi.

1. `journalctl --utc -u oisha-os -u oisha-web -u nginx --since '2026-10-22 08:40:00 UTC' --until '2026-10-22 09:00:00 UTC'` ichidan restart, timeout, traceback va init vaqtini ajrating.
2. Shu davr kernel jurnalida OOM kill yoki disk/I/O xatosi bo'lganmi tekshiring.
3. Nginx access/error jurnalida hostname, request path, 499/502/504, upstream vaqtlarini davomatning birinchi so'rovi bilan solishtiring.
4. Systemd restart sababi, watchdog probe natijalari, Next.js jarayoni va umumiy CPU/RAM kuzatuvlarini bir vaqt chizig'iga joylashtiring.
5. Faqat sintetik alohida bazada DDL bilan parallel oddiy SELECT va health probe'ni o'lchang; prod bazasida yuk sinovi o'tkazmang.

SSH host kaliti tekshiruvi o'tmagani sabab bu jurnallar olinmadi. Sabab **noma'lum**. Owner aytgan taxminiy 15 sekund va 35 DDL prod benchmark natijasi sifatida qayd etilmadi.
