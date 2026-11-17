# Telethon session egaligi — AuthKeyDuplicated dan saqlanish

## Muammo

```text
❌ Telethon ulana olmadi: The authorization key (session file) was used under
two different IP addresses simultaneously, and can no longer be used.
```

Telegram har bir auth key ni bitta IP ga bog'laydi. O'sha kalit bir vaqtning
o'zida ikki xil IP dan ishlatilsa, Telegram uni **butunlay bekor qiladi** —
`AuthKeyDuplicatedError`. Bu qaytarib bo'lmaydi: yangi session generatsiya
qilinmaguncha na prod userbot, na bironta workflow ishlaydi.

## Kim egasi

| Nima | Session | Egasi |
|---|---|---|
| Prod userbot | `USERBOT_SESSION_STRING` | Hetzner prod VPS (`2.29.198.0`), `oisha.service` (yagona) |
| Telegram MCP gateway | `TELEGRAM_MCP_SESSION_STRING` | Hetzner prod VPS (`2.29.198.0`), alohida kalit |
| One-off skriptlar | `TELEGRAM_ONEOFF_SESSION_STRING` | Hetzner prod VPS (`2.29.198.0`), alohida kalit |

Bitta Telegram akkaunt bir nechta sessiyaga ega bo'lishi mumkin — har biri
alohida auth key. Shuning uchun to'g'ri yechim "navbat bilan ishlatish" emas,
balki **har bir iste'molchiga o'z sessiyasini berish**.

## Nima buzilgan edi

`verify-session.yml` va `qurbon-greeting.yml` GitHub-hosted runner (`ubuntu-latest`)
da prod `USERBOT_SESSION_STRING` bilan Telethon ga ulanardi. Runner ning IP si
Oracle VM dan boshqa — natijada kalit kuyar, keyingi `juma-greeting.yml`
yurishi esa yuqoridagi xato bilan yiqilardi.

Xuddi shu sabab ilgari VPS ↔ Oracle to'qnashuvida ham bo'lgan; shu bois
`userbot-vps.yml` endi faqat "stop-only" (VPS da userbot o'chirilgan).

## Hozirgi qoidalar

1. **Prod kaliti Hetzner prod VPS dan chiqmaydi (`2.29.198.0`).** Telethon kerak bo'lgan har qanday
   workflow prod serverda bajariladi (GitHub runner ko'chirilishi va aniq SSH yo'li tekshirilmagan).
2. **Session tekshiruvi yangi ulanish ochmaydi.** `verify-session.yml` endi VM
   dagi `http://127.0.0.1:8080/readyz/` javobidagi `checks.userbot` ni o'qiydi —
   ya'ni ayni ishlab turgan client holatini.
3. **One-off skriptlar `scripts/telethon_guard.py` dan o'tadi:**
   - `prepare()` — avval atalgan session (`JUMA_SESSION_STRING`,
     `QURBON_SESSION_STRING`, so'ng `TELEGRAM_ONEOFF_SESSION_STRING`), faqat
     ular yo'q bo'lsa prod kaliti;
   - atalgan env prod kaliti bilan **bir xil** bo'lsa, u ham shared deb
     qaraladi — ya'ni `TELEGRAM_ONEOFF_SESSION_STRING` ga prod stringni qo'yib
     guard'ni chetlab o'tib bo'lmaydi;
   - prod kaliti tanlansa, GitHub-hosted runner da ulanish **taqiqlanadi**;
   - `single_flight()` — bitta hostda ikkita one-off skript bir vaqtda
     ulanmaydi;
   - `guarded_connect()` / `guarded_is_authorized()` — kalit kuyganda xom
     traceback o'rniga tiklash yo'riqnomasi egasiga Telegram orqali yuboriladi.
4. **`USERBOT_SESSION_OWNER_HOST` (ixtiyoriy, lekin tavsiya etiladi).**
   Qo'yilsa, prod kaliti faqat shu hostname da ochiladi; boshqa hostda
   `SessionConflictError` beriladi. Hetzner prod serverda (`2.29.198.0`) o'rnating:
   `USERBOT_SESSION_OWNER_HOST=<vm-hostname>` (`hostname` buyrug'i chiqargan
   nom). Bu yagona tekshiruv bo'lib, prod kaliti muhitda ko'rinmagan holatda
   ham ishlaydi — "atalgan env prod bilan bir xilmi" taqqoslashi esa faqat
   ikkala qiymat ham shu hostda ko'ringandagina aniqlay oladi.

`ALLOW_SHARED_USERBOT_SESSION=1` guard'ni o'chiradi — faqat
`sudo systemctl stop oisha.service` qilingandan keyin ishlating.

## Kalit kuyganda tiklash

```bash
# 1. Prod kalitini ushlab turgan hamma jarayonni to'xtatish (Hetzner'da: oisha.service)
sudo systemctl stop oisha.service

# 2. Yangi session
#    Prod serverda auth script orqali yangi session yarating (masalan:
#    <OISHA_DIR>/.venv/bin/python scripts/prod/auth_userbot_on_oracle.py — nom tarixiy)

# 3. Yangi stringni ikkala joyga yozish
#    - GitHub secret (ishlatilsa): USERBOT_SESSION_STRING
#    - Hetzner .env:               <OISHA_DIR>/.env

# 4. Servisni qaytarish va tekshirish
sudo systemctl start oisha.service
curl -s http://127.0.0.1:8080/readyz/ | python3 -m json.tool
```

Tiklagandan so'ng one-off skriptlar uchun **alohida** session oling va uni
`TELEGRAM_ONEOFF_SESSION_STRING` ga qo'ying — shunda prod kaliti hech qachon
ikkinchi marta ochilmaydi.
