# AmoCRM / userbot recovery readiness — Oracle

PR #587/#588 dan keyingi **read-only inventory**. Bu skript credential
yaratmaydi/yangilamaydi, OAuth refresh qilmaydi, Telegram client ochmaydi,
lock olmaydi/bo'shatmaydi, jadval yaratmaydi va servisni restart qilmaydi.

## Ishga tushirish

Faqat tasdiqlangan Oracle operator sessiyasida, servis ishlaydigan foydalanuvchi
va checkout bilan (bu patch tayyorlashda productionga ulanilmadi):

```bash
cd /home/ubuntu/oisha-os
./venv/bin/python scripts/prod/recovery_readiness.py --root .
# Turso SELECT uchun alohida opt-in; credential argumentga yozilmaydi:
./venv/bin/python scripts/prod/recovery_readiness.py --root . --read-turso
```

`.env` o'qiladi; mavjud process environment ustun. Interpolatsiya bajarilmaydi.
Custom service environment/token paths ishlatilsa bu default inventar service
bilan aynan bir xil bo'lmasligi mumkin. Natijada sir qiymatlari, hash, uzunlik,
hostname/PID, fayl yo'llari, HTTP body yoki xom exception chiqmaydi.
Turso sozlangan bo'lsa default `not_checked`; remote xatoda SQLite fallback yo'q.
SQLite faqat `data/bot.db`, `mode=ro`. Turso uchun faqat uch credential/owner
qatoriga fixed SELECT; TLS, timeout, cheklangan response, redirect/retry yo'q.

## Natijani talqin qilish

- **Exit 2, `ready:false` doimiy:** inventar server-side auth, DB yozish imkoniyati
  yoki lock acquisition'ni isbotlamaydi. Uni deploy/start uchun yashil gate qilmang.
- AmoCRM manba tartibi: env JSON (hatto `{}` ham fallbackni to'sadi), fayl,
  raw refresh (faylda refresh bo'lmasa), DB fallback. `selected_differs_from_db`
  eskirgan env/fayl rotatsiya qilingan DB tokenini to'sishi mumkinligini bildiradi;
  qaysi biri amalda yaroqli ekanini isbotlamaydi.
- `refresh_prerequisites` faqat refresh va client sozlamalari mavjudligi.
  `refresh_usability=unverified_no_rotation_performed`: live refresh alohida
  credential mutation bo'lib, bu probe ichida mavjud emas. `future` expiry
  ham token serverda bekor qilinmaganini isbotlamaydi.
- Userbot DB → fayl → env. `valid_shape` faqat StringSession format tekshiruvi;
  login tekshiruvi emas. `shared_with_mcp:true` bo'lsa recovery'ni to'xtating.
- `active_same_host` ham boshqa process egasi bo'lishi mumkin; probe PID'i
  servis PID'i emas. `active_other_host`, `unknown`, `invalid`, `disabled`,
  `bypassed` holatlarida start/force qilmang. `stale`/`absent` ham lock olishga
  ruxsat emas; atomik acquisition faqat servisning o'zida bajariladi.
- `empty_owner_pending_expiry` #588 insert'dagi bo'sh owner va kelajak expiry
  holatini alohida ko'rsatadi. Bu probe lock algoritmini tuzatmaydi yoki
  heartbeat boshqa egani bosmasligini isbotlamaydi.

`probe_failed` yoki DB `unavailable` bo'lsa traceback/secret dump qilmang.
Servis foydalanuvchisi, konfiguratsiya mavjudligi, DB reachability/schema va
host ownership'ni operator tekshirsin. Credential almashtirish, force override,
release, reauth va restart uchun alohida tasdiqlangan recovery tartibi kerak.
Mavjud servisning sanitizatsiyalangan readiness statusi bilan auth holatini
alohida tekshiring; yangi Telethon client bilan tekshirmang.
