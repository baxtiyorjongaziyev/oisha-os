# Reveo o'rniga o'zimizning AI Chat Manager — spetsifikatsiya

Manba: reveo.uz/en, /en/ai-chatbot/, /pricing/ (2026-10-27) va owner yuborgan 10 ta
admin panel skrinshoti. Maqsad: SaaS emas, faqat Jon Branding uchun, Oisha-OS ichida.

## 1. Reveo mahsulotlari

| Mahsulot | Nima qiladi | Narx | Biz uchun |
|---|---|---|---|
| AI Chat Manager | Telegram/Instagram/WhatsApp'da 24/7 javob, lid → CRM | $49/oy (500 kontakt) | **Asosiy maqsad** |
| Call Analyze | Qo'ng'iroqni matnga o'girib, mezon bo'yicha baholaydi | $49/xodim | Bizda qisman bor (Moizvonki + call_analytics) |
| Offline Analyze | Sotuvchi badge'i orqali zal suhbatini yozadi | $99/xodim | Kerak emas |

## 2. AI Chat Manager — agent xulqi (saytdan)

- Javob faqat bizning ma'lumotdan: narxlar, xizmatlar, ish vaqti, FAQ, fayllar.
- Rasm va ovozli xabarni tushunadi; video tahlili (alohida yoqiladi, qimmatroq).
- 6 til: mijoz qaysi tilda yozsa, shu tilda javob.
- Follow-up: suhbat to'xtasa, o'zi eslatadi (ko'pi bilan 2 marta).
- Uchrashuv band qiladi, lidni CRM'ga (amoCRM) kontakt + qisqa xulosa + keyingi qadam bilan yozadi.
- **Qat'iy cheklovlar:**
  - katalogda yo'q narxni aytmaydi — operatorga beradi;
  - "men botman" deb sotuvni buzmaydi, lekin so'rasa yashirmaydi;
  - mijoz ma'lumotini uchinchi tomonga bermaydi;
  - operator olgan suhbatga aralashmaydi;
  - shikoyat va bahsni darhol odamga beradi;
  - ish vaqti yoki mavjudlikni o'ylab topmaydi.

## 3. Admin panel (skrinshotlardan)

Menyu: Dashbord · Dialoglar · Zayavkalar · Analitika · Kanallar · Ssenariylar ·
Testlash · O'qitish · Tariflar · Sozlamalar. Tepada: global qidiruv, "AI-yordamchi",
filtr Barchasi / Reklama / Organika. Pastda: "Tizimlar normada, N kanal onlayn".

### 3.1 Dialoglar
- Chapda ro'yxat: avatar + kanal belgisi, ism, oxirgi xabar, vaqt, o'qilmaganlar soni, yulduzcha.
- Filtrlar: Barchasi · Kutmoqda · Javobsiz · Operator; qidiruv; eksport; davr.
- O'ngda chat: sana ajratgichlari, kim yozgani (AI / Operator), o'qildi belgisi.
- Pastda rejim almashtirgich **AI-agent / Operator**, xabar maydoni, fayl, ovoz.
- Tepada: uchrashuv belgilash, mijoz kartasi, menyu.

### 3.2 Zayavkalar
- Kategoriya kartalari: Zayavkalar · Qiziqqan mijozlar · E'tiroz va shikoyatlar ·
  Takliflar · Dojimlar (bugun) · + yangi kategoriya. Har birida "N yangi".
- Ro'yxat kunlar bo'yicha guruhlangan: ism, telefon (yashirilgan), AI yozgan 1 gaplik
  xulosa, status (Ochiq ▾), vaqt, tugmalar "Ishga olish" / "O'zgartirish".
- Filtr: holat, kontakt bor/yo'q, sana, "kunlar bo'yicha".

### 3.3 Analitika
- Davr: 7/14/30 kun, ixtiyoriy; kanal; "Kunlik hisobot 08:00 da Telegram guruhga" toggle.
- KPI: dialoglar, xarid qilmoqchi, zayavkalar (ishlanmagan), konversiya,
  AI o'zi hal qildi %, ish vaqtidan tashqari % (19:00–9:00 + dam olish).
- Sotuv voronkasi: Yozdi → Xarid qiziqishi → Kontakt qoldirdi → Menejer yopdi.
- Suhbat qanday tugadi: AI yopdi / menejer ulandi; AI javob ulushi; javob tezligi;
  jamoaga savollar (javobsiz); shikoyatlar.
- Kunlik grafik, kanal × reklama/organika jadvali.
- Mashhur savollar (top-7), mijoz niyati, AI belgilagan kategoriyalar.
- Heatmap: hafta kuni × soat (Toshkent vaqti), cho'qqi.
- Lid demografiyasi: jins (ism bo'yicha), til, geografiya (telefon kodi).
- AI yuborgan havolalarni kim ochdi (click tracking).

### 3.4 Kanallar
- Ulangan kanal kartasi: @username, Onlayn, AI yoqilgan; toggle'lar
  "AI avto-javob", "Izohlarga javob" + izoh triggerlari.
- Ulash: Instagram (Meta), Telegram (shaxsiy yoki bot), WhatsApp Cloud API,
  Facebook Messenger, TikTok. "Ulanish holati": token muddati.

### 3.5 Sozlamalar → Agent
- **Temp:** javobdagi xabarlar soni, javobdan oldingi pauza (sek), xabarlar orasidagi pauza.
- Video tahlili, proaktiv dojimlar (toggle).
- **Xarakter:** til, agent turi (Muvozanatli...), informativlik 1–5, javob uzunligi 1–5.
- **Konstruktor / Instruksiya matni:** asosiy sotuv maqsadi, offer va narx qoidalari,
  malakalash savollari, menejerga berish qoidalari, ton, xabar uslubi.
- Boshqa bo'limlar: Kompaniya, Jamoa, Bildirishnomalar, Bilimlar bazasi, Postlar,
  Tovarlar, Fayllar, Izohlar, Bloklar, Integratsiyalar.

## 4. Oisha-OS'da bor narsa

| Kerak | Bizda | Holat |
|---|---|---|
| Telegram avto-javob | `services/core/auto_reply_gate.py` | bor, shadow rejimida |
| Instagram DM/izoh | `services/core/instagram_agent.py` | bor |
| LLM | `services/utils/free_ai_router.py` | bor |
| Lid ajratish | `channel_lead_extractor.py`, `leads/lead_classifier.py`, `auto_lead_agent.py` | bor, yagona emas |
| amoCRM yozish | `services/core/crm/*`, `api/routes/simple_crm.py` | bor |
| Yagona dialog jadvali | — | **yo'q** |
| Agent sozlamalari DB'da | — | **yo'q** (env / kod ichida) |
| Zayavka kategoriyalari + xulosa | — | **yo'q** |
| Panel sahifalari | `/api/simple-crm/` namunasi | **yo'q** |

## 5. Bosqichlar

1. **Asos:** `dialogs` + `dialog_messages` jadvallari (Telegram + Instagram yozadi),
   `agent_settings` (3.5 maydonlari), AI zayavka ajratish (kategoriya + 1 gaplik xulosa +
   amoCRM'ga yozish), Dialoglar sahifasi (ro'yxat + chat + AI/Operator rejimi).
2. **Zayavkalar sahifasi** (3.2).
3. **Analitika** (3.3).
4. **Sozlamalar paneli + bilimlar bazasi + follow-up** (3.5).

Shart: avto-javob shadow rejimida qoladi; owner tasdiqlamaguncha mijozga hech narsa
o'zi ketmaydi. 2-bo'limdagi cheklovlar agent promptiga majburiy kiradi.
