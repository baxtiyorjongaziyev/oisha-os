# 👸 Oisha-OS: Telegram Lead Sinxronizatsiyasi Qo'llanmasi

Ushbu loyiha "TEZ NATIJA 5" guruhidagi forum mavzularidan a'zolar ma'lumotlarini avtonom tarzda yig'ish va ularni shaxsiy kontaktlaringizga (Telegram va Google Contacts) bezarar sinxronizatsiya qilish uchun mo'ljallangan.

## 🚀 Asosiy Imkoniyatlar
- **Telegram Kontaktlar**: A'zolarni to'g'ridan-to'g'ri shaxsiy kontaktlar ro'yxatiga qo'shish.
- **Google Contacts**: Ism, telefon va AI tomonidan tahlil qilingan biografiyani saqlash.
- **AI Tahlili**: Forumdagi "Ishtirokchilar ma'lumotlari" mavzusini o'qib, foydalanuvchining biznes sohasini aniqlash.
- **Anti-Spam**: Telegram akkauntingizni himoyalash uchun aqlli kutish rejimlari.

---

## 🛠️ Qanday Ishga Tushiriladi?

### 1. Avtomatik Sinxronizatsiya
Botga Telegram orqali quyidagi buyruqni bering (Oisha buni o'zi ham tushunadi):
`Oisha, guruh a'zolarini kontaktlarimga qo'sh.`

Bot fonda quyidagi tegni ishlatadi: `[SYNC_LEADS: topic=7|limit=25]`

### 2. Google Contacts-ni Sozlash
Agar kontaktlar shaxsiy telefoningizda ko'rinishini istasangiz (Service Account emas, shaxsiy @gmail):
1. `credentials.json` faylini loyiha papkasiga joylang.
2. `get_google_token.py` skriptini ishga tushiring.
3. Brauzer orqali ruxsat bering.

---

## 👸 Xavfsizlik Qoidalari (Spamdan Himoya)
Akkauntingiz 10 yillik va juda qadrli bo'lgani uchun tizimga quyidagi cheklovlar o'rnatilgan:
- **Kechikish**: Har bir kontakt qo'shilgandan so'ng **60-120 soniya** pauza qilinadi. 🐢
- **Limit**: Kuniga maksimal **25 ta** yangi kontakt qo'shiladi. 🛑
- **Nomlash**: Barcha kontaktlar oxiriga `TN5 Gr` qo'shiladi, bu ularni oddiy kontaktlardan farqlashga yordam beradi. ✅

---

## 📁 Loyiha Tuzilishi
- `userbot.py`: Asosiy bot xizmati.
- `services/lead_scraper.py`: Ma'lumotlarni yig'ish va sinxronizatsiya qilish "miyasi".
- `gcontacts.py`: Google Contacts bilan ishlash moduli.
- `token.pickle`: Sizning shaxsiy Google ruxsatnomangiz (avtomatik yaratiladi).

---

## 👸 Muammolarni Hal Qilish
Agar kontaktlar qo'shilmasa:
1. `scraped_leads.json` faylini o'chirib, jarayonni noldan boshlang.
2. `python userbot.py` orqali loglarni tekshiring.

> [!TIP]
> Oishaga "Sinxronizatsiya holati qanday?" deb so'rasangiz, u sizga necha kishi qo'shilganini aytib beradi.

---
👸🛡️ **Oisha-OS – Sizning elite biznes yordamchingiz.**
