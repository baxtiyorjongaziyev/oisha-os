# Oisha-OS: Kelajak Rivojlanish Yo'l Xaritasi (Roadmap) 🚀

Jon Branding agentligi uchun Oisha-OS tizimini shunchaki API yordamchisidan, jamoani raqamlar asosida boshqaruvchi va mijozlarga eng yuqori darajadagi servisni taqdim etuvchi **Avtonom Operatsion Direktor (AI COO)** darajasiga olib chiqish rejasi.

---

## 📅 Hozirgi Holat (Current Status)
* **AmoCRM & DB Infratuzilmasi:** Barqaror (500 bitim limiti nazoratda).
* **Omni-Agent Infratuzilmasi:** Tayyor (`WebDriver`, `OSDriver`, `MobileProxy` unit testlari yashil).
* **Raqamlar bilan Boshqaruv:** Jamoa KPI, Haftalik hisobot va Deadline control tizimlari real ma'lumotlar bazalariga (AmoCRM + Airtable) to'liq bog'landi.

---

## 🗺 Rivojlanish Bosqichlari (Phases)

### Phase 1: Infratuzilma va CRM Barqarorligi [DONE]
- [x] AmoCRM OAuth 2.0 avtorizatsiya siklidagi uzilishlarni tuzatish.
- [x] **CRM Janitor:** 500 bitim limitidan oshmaslik uchun yo'qotilgan/eski lidlarni avtomat tozalash.
- [x] Terminal va loglarda Unicode/Emoji xatoliklarini tuzatish.

### Phase 2: Savdo Tahlil va Hunter-Setter Engine [DONE]
- [x] Multi-pipeline (Hunter, Closer, Farmer) bitimlar sinxronizatsiyasi.
- [x] **Surgical Missions:** Menejerlar uchun kunlik 3 ta aniq amaliy qadam generatsiyasi.
- **KPI va Analitika:** Savdo qo'ng'iroqlari va suhbatlarini 6 parameter bo'yicha baholash (`call_analyzer.py`).

### Phase 3: Kompyuter va Brauzer Avtomatizatsiyasi (Omni-Agent) [DONE]
- [x] `Playwright` asosidagi Web Driver yaratish (Saytlarda harakatlanish).
- [x] `PyAutoGUI` + `MSS` yordamida desktop darchalarini boshqarish (OS Driver).
- [x] `instagrapi` yordamida Instagram DM orqali xabarlarni o'qish/yuborish va Telegram Userbot wrapper (Mobile Proxy).

### Phase 4: Jamoani Raqamlar bilan Boshqarish (Discipline Enforcer) [IN PROGRESS]
- [x] **Real-time KPI & SLA:** Telegram Admin Botga dynamic KPI (Savdo, loyihalar va moliya reja-fakti) hamda Deadline control integratsiyasi.
- [ ] **SLA Response Tracker:** Telegram guruhlarda va DM da jamoa a'zolarining mijozlarga javob berish tezligini (SLA) o'lchash va kechikishlarni hisobotga kiritish.
- [ ] **Manager Nagger:** Vazifalari kechikayotgan yoki hisobot bermayotgan xodimlarga Oisha tomonidan shaxsiy guruhlarda avtomatik ogohlantirishlar (nudge) yuborish.

### Phase 5: Mijozlar uchun WOW-Service (Customer Experience Concierge) [PLANNED]
- [ ] **Ambassador Journey Automation:** Loyiha topshirilgandan keyin mijozga avtomatik NPS (qoniqish) so'rovnomalarini yuborish va bahoni bazaga saqlash.
- [ ] **Automatic Update Concierge:** Airtable-dagi Loyiha statusi o'zgarganda mijozga chiroyli va tushunarli formatda (nima bitdi, keyingi qadam nima) avtomatik bildirishnoma yuborish.
- [ ] **First 1-Hour WOW Pack:** Yangi lid kelganda, mas'ul menejer mijozga 1 soat ichida javob bermasa, Oisha o'zi mijozga dastlabki brifing va Jon Branding taqdimot paketini jo'natishi.

### Phase 6: To'liq Avtonom Agent (Autonomous Agency) [FUTURE]
- [ ] **Task Auto-Execution:** Oisha desktop drayverlari orqali hisob-fakturalar yaratishi, Airtable guruhlarini ochishi va jamoaga vazifalarni o'zi avtomatik yaratib taqsimlashi.
- [ ] **Voice-to-Task Agent:** Ovozli xabarlar va qo'ng'iroqlardan topshiriqlarni avtomatik ajratib, ularni jamoaning ish rejasiga joylashtirish.
