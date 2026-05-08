# Telegram AI Bot Revolution: Oisha uchun ishlatish xaritasi

Manba: Telegram blogidagi **AI Bot Revolution: 11 New Features** va rasmiy Bot API 10.0 hujjatlari.

## Qisqa xulosa

Telegram yangi imkoniyatlarni uch turga ajratadi:

- **Kod bilan ishlaydiganlar:** Guest Mode, Bot-to-Bot Communication, Streaming Text, Business/Chat Automation, Managed Bot access, personal chat context, poll/reaction API.
- **BotFather yoki Telegram sozlamasi kerak bo'ladiganlar:** Guest Mode, Bot-to-Bot, Business Mode, Bot Management, private topics, Main Mini App.
- **Telegram ilovasi ichida foydalanuvchi funksiyasi:** Custom AI Styles, expanded emoji/sticker search, poll statistics, silent scheduled messages.

Oisha tomonda poydevor qo'shildi:

- `src/services/core/telegram_ai_features.py` raw Bot API 10.0 adapter.
- `/api/telegram/ai-features` endpoint: qaysi imkoniyat kodda tayyor, qaysi biri BotFather'da yoqilganini ko'rsatadi.
- `/webhook/telegram-ai` endpoint: `guest_message` update'ni qabul qilib `answerGuestQuery` orqali javob qaytarishga tayyor.
- `TelegramNotificationAdapter` streaming draft, guest answer va bot-to-bot send metodlariga kengaytirildi.

## 1. Guest Mode

Nima beradi: foydalanuvchi Oisha'ni istalgan chatda `@username` bilan chaqiradi, bot guruh a'zosi bo'lmasa ham bitta xabarga javob beradi.

Oisha ishlatishi:

- Guruhga bot qo'shmasdan tez fakt-check, brif tahlili, javob drafti.
- Oisha faqat tag qilingan xabarni ko'radi, butun chat tarixini emas.

Kod holati:

- `guest_message` parser tayyor.
- `answerGuestQuery` adapter tayyor.
- Webhook endpoint tayyor.

Yoqish:

- BotFather'da Guest Mode yoqiladi.
- Webhook `allowed_updates` ichida `guest_message` bo'lishi kerak.

## 2. Bot-to-Bot Communication

Nima beradi: botlar guruhda yoki business chat orqali bir-biri bilan gaplashadi.

Oisha ishlatishi:

- CRM botdan lead status so'rash.
- Calendar/booking bot bilan uchrashuv band qilish.
- Payment bot bilan to'lov holatini tekshirish.

Xavfsizlik:

- Infinite loop bo'lmasligi uchun dedupe, rate limit va max depth shart.
- Client-facing javoblarda policy engine hali ham qaror beradi.

Kod holati:

- `send_bot_to_bot_message()` adapteri tayyor.
- BotFather'da Bot-to-Bot Communication yoqilishi kerak.

## 3. Streaming Text

Nima beradi: uzun javob tayyorlanayotganda foydalanuvchi “Thinking…” yoki qisman draft ko'radi, keyin yakuniy xabar yuboriladi.

Oisha ishlatishi:

- Katta audit.
- CRM/Airtable bo'yicha chuqur xulosa.
- Negotiation javobining sekin chiqishi foydalanuvchini bezovta qilmasligi.

Kod holati:

- `sendMessageDraft` adapteri tayyor.
- `stream_direct_message()` avval draft, keyin yakuniy `sendMessage` yuboradi.

## 4. Chat Automation in Profiles

Nima beradi: Telegram Business orqali bot shaxsiy profilga ulanadi va ruxsat berilgan chatlarda javob bera oladi.

Oisha ishlatishi:

- Faqat mijoz/lead deb tasniflangan chatlarda yordam.
- Oila/shaxsiy papkadagi yozishmalar mijoz deb qabul qilinmasligi kerak.
- Avtonom javob faqat policy + verifierdan o'tganda.

Kod holati:

- Eski `business_message` handler bor.
- Yangi status endpoint `can_connect_to_business` flagini ko'rsatadi.

Yoqish:

- Telegram: Settings > Chat Automation.
- BotFather'da Business Mode.

## 5. Quick Action Bar

Nima beradi: Business chat tepasida “Manage Bot” ochiladi va botga `/start bizChat<user_chat_id>` deep-link keladi.

Oisha ishlatishi:

- Aynan shu mijoz uchun CRM card, follow-up, task, meeting va javob draftini ko'rsatish.

Kod holati:

- Bu deep-link keyingi bosqichda `/start bizChat...` parseriga ulanadi.

## 6. Managed/Suggested Bots

Nima beradi: bot boshqa botlarni yaratish/boshqarish jarayoniga yordam beradi.

Oisha ishlatishi:

- Har bir mijoz yoki loyiha uchun alohida servis bot.
- Kirishni faqat owner/PM/mijozga cheklash.

Kod holati:

- `getManagedBotAccessSettings` va `setManagedBotAccessSettings` adapterlari tayyor.

Yoqish:

- BotFather MiniApp: Bot Management Mode.

## 7. Starting in Topics / Private Topics

Nima beradi: private chat ichida topic/thread bilan tartiblash.

Oisha ishlatishi:

- Brif
- To'lov
- Feedback
- Fayllar
- Review/Otziv

Kod holati:

- Bot API adapterlari `message_thread_id` ni qo'llaydi.
- BotFather'da topics yoqilganini `/api/telegram/ai-features?live=true` ko'rsatadi.

## 8. Profile Links, Birthdate, Location, Personal Chat Context

Nima beradi: bot ruxsatli profil ma'lumotlarini ko'rishi mumkin.

Oisha ishlatishi:

- Mijoz kontekstini boyitish.
- Tug'ilgan kun yoki location bo'yicha servisni shaxsiylashtirish.
- Personal chatdan oxirgi public/ruxsatli postlarni olish.

Kod holati:

- `getUserPersonalChatMessages()` adapteri tayyor.

Chegara:

- Telegram faqat ko'rishga ruxsat bor ma'lumotni beradi.
- Shaxsiy/oila yozishmalari avtomatik lead deb olinmaydi.

## 9. Monetizing Messages

Nima beradi: Stars, paid media va paid broadcast.

Oisha ishlatishi:

- Pulli mini audit.
- Paid konsultatsiya.
- Premium call analysis.
- Zarurat bo'lsa paid high-throughput broadcast.

Kod holati:

- Poydevor feature matrixda bor; real to'lov flow alohida compliance va narx siyosati bilan ulanadi.

## 10. Poll Limits and Poll Stats

Nima beradi: poll uchun country/subscriber limitlari va statistikalar.

Oisha ishlatishi:

- Jamoa ichki nazorat pollari.
- Kurs/guruh segmentatsiyasi.
- Mijoz feedback pollari.

Kod holati:

- Bot API 10.0 `sendPoll` parametrlarini raw adapter orqali chaqirish mumkin.
- Poll statistikasi Telegram admin UI ichida 100+ ovozdan keyin ko'rinadi.

## 11. Silent Scheduled Messages

Nima beradi: rejalangan xabarlar ovozsiz yetib boradi.

Oisha ishlatishi:

- Kechasi yoki dam olish vaqtida jamoani bezovta qilmasdan reminder yuborish.
- Bot xabarlarida `disable_notification=True` ishlatish.

Chegara:

- Telegram ilovasidagi “schedule silently” foydalanuvchi UI funksiyasi.
- Bot API tomonda real yuborilayotgan xabarda ovozsiz yuborish mavjud.

## 12. Removing Reactions

Nima beradi: admin bot reactionlarni o'chira oladi.

Oisha ishlatishi:

- Team guruhda nojo'ya reactionlarni tozalash.
- Moderatsiya signalini CRM/intizom auditiga qo'shish.

Kod holati:

- `deleteMessageReaction` va `deleteAllMessageReactions` adapterlari tayyor.

## 13. Custom AI Styles

Nima beradi: Telegram AI Text Editor ichida shaxsiy yozish uslubi yaratish.

Oisha ishlatishi:

- Jon Branding tone-of-voice promptlarini jamoa uchun standart qilish.
- Savdo, PM va rahbar postlarini bir xil uslubda yozishga yordam berish.

Chegara:

- Bu Bot API metodi emas, Telegram app ichida qo'lda yaratiladi.
- Oisha promptlarini tayyorlab beradi, foydalanuvchi Telegram Text Editor ichida style qilib saqlaydi.

## 14. Expanded Emoji and Sticker Search

Nima beradi: 100M+ emoji/sticker ichidan AI qidiruv.

Oisha ishlatishi:

- Mijoz bilan samimiy, brendga mos chat uslubini saqlash.
- Juma tabriklari, community postlari va soft communication uchun tez tanlash.

Chegara:

- Bu Telegram ilovasi funksiyasi, server kodi emas.

## Ishga tushirish checklist

1. BotFather'da Guest Mode yoqish.
2. BotFather'da Bot-to-Bot Communication yoqish.
3. BotFather'da Business Mode yoqish.
4. Telegram Settings > Chat Automation orqali Oisha'ni profilga ulash.
5. `TELEGRAM_WEBHOOK_SECRET` secretini qo'yish.
6. Webhookni `/webhook/telegram-ai` ga `allowed_updates` bilan set qilish.
7. `/api/telegram/ai-features?live=true` orqali real flaglarni tekshirish.
8. Guest mention orqali test qilish: `@jonairobot brifni tekshir`.
9. Streaming test: uzun audit javobida draft ko'rinishini tekshirish.
10. Bot-to-bot test: test botga xabar yuborib loop-safeguardni kuzatish.
