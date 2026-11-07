# Jon Branding — bo‘sh maydonlar auditi

Tekshiruv: 2026-11-06. Barcha 15 jadval va barcha sahifalar o‘qildi. Bo‘sh = yo‘q/null/bo‘sh matn/bo‘sh ro‘yxat. 0 qiymati bo‘sh emas. Checkbox tanlanmaganligi bajarilmagan yoki false bo‘lishi mumkin. Bo‘shlikning o‘zi xato yoki mas’ul aybini isbotlamaydi. Formulalar/rollup/lookup avtomatik maydonlari bu ro‘yxatdan chiqarildi; shartli va texnik maydonlar izohi bilan keltirildi.

## Tranzaksiyalar — 543 yozuv

| Maydon | Bo‘sh | Ulush | Izoh |
|---|---:|---:|---|
| Kurs | 9/543 | 2% | USD bo'lsa, kurs (UZS ga aylantirish uchun). Valyuta USD bo'lganda majburiy. |
| Kategoriya | 2/543 | 0% | Link: moliya kategoriyasi (Moliya kategoriyalari jadvali). Majburiy. |
| Loyiha | 195/543 | 36% | Link: bog'liq loyiha (Loyihalar jadvali). |
| Hujjat | 363/543 | 67% | Ilova (chek, kvitansiya va h.k.). |
| Xodim | 479/543 | 88% | Pul oluvchi xodim yoki freelancer. Ish haqi, bonus va freelancer chiqimlarida majburiy bog‘lanadi; Jamoa daromadi shu linkdan hisoblanadi. |
| [TEXNIK] Oylik P&L link | 2/543 | 0% | Oylik P&L yopilish qatoriga bog‘lash uchun texnik link. Moliyachi forma yoki kundalik ishda ko‘rishi shart emas. |
| [TEXNIK] Cashflow link | 321/543 | 59% | Oylik Cashflow qatoriga bog‘lash uchun texnik link. Moliyachi forma yoki kundalik ishda ko‘rishi shart emas. |
| Izoh | 7/543 | 1% | Izoh/tavsif. Eski jadvaldan migratsiya qilinganlarda manba ko'rsatiladi. |
| Sotuvchi | 487/543 | 90% | Kirimni amalga oshirgan / jalb qilgan sotuvchi (Jamoa linki). Loyiha bog'langan bo'lsa, loyiha sotuvchisi avtomatik olinadi yoki qo'lda tanlanadi. |
| CAC klassi | 539/543 | 99% | Yangi mijoz olib kelish xarajatlarini klassifikatsiya qilish. Full CAC hisobida faqat CACga kiradigan xarajatlarni belgilang. |
| Marketing kanali (xarajat) | 540/543 | 99% | Faqat marketing CHIQIMI uchun: pul qaysi kanalga sarflangani. Kirimda to'ldirilmaydi — kirim kanali mijozdan avtomatik olinadi. |
| Bizniki emas (boj / reklama) | 527/543 | 97% | Bu puldan qanchasi bizniki emas? (mijozning davlat boji yoki reklama budjeti). Hammasi bizniki bo'lsa — bo'sh qoldiring. "Patent davlat boji" kategoriyasida bo'sh qolsa, butun summa avtomatik tranzit hisoblanadi. |
| P&L — Hisobga kiritilmasin | 539/543 | 99% | Shaxsiy pul, kapital, qarz, transfer yoki boshqa P&Lga aloqasiz harakatlar uchun. Cashflow saqlanadi. |
| P&L — Davr sanasi (override) | 540/543 | 99% | Buxgalteriya P&Lda qaysi oyga taalluqli. Bo‘sh bo‘lsa tranzaksiya sanasi ishlatiladi. Rollup oyiga bog‘lash ham mos bo‘lishi shart. |
| P&L — Tuzatish asosi | 500/543 | 92% | Tahrir manbai va tasnifni tekshirish uchun audit izohi; asosiy Tranzaksiya va Izoh maydonlari saqlanadi. |
| Transfer — qabul qiluvchi hisob | 543/543 | 100% | Faqat Transfer uchun: pul keladigan Hisoblar qatori. Bitta hisob tanlanadi. |
| Transfer — qabul qilingan summa | 543/543 | 100% | Faqat turli valyutaga konvertatsiya qilishda qabul qilingan pul, qabul qiluvchi hisob valyutasida. |
| Transfer — qabul Cashflow oyi | 543/543 | 100% | Transfer qabul qiluvchi hisobning shu oyga tegishli Cashflow satri. |
| Moliyaviy mohiyat | 531/543 | 98% | Oddiy xizmat kirim/chiqimidan tashqari operatsiyalar uchun. Tanlanmasa odatiy operatsiya; tranzit, avans va qarz kabi holatlarni alohida yuriting. |
| Majburiyat — tegishli qarz/to‘lov | 540/543 | 99% | To‘lovning debitor/kreditor majburiyatiga aloqasi. Link qo‘yilganda qarz avtomatik kamayadi, shunchaki nomga qarab avtomatik bog‘lash yo‘q. |
| Oylik budjet — bog‘langan qator | 480/543 | 88% | Sana oyi va yagona kategoriya mos keladigan budjet qatori; kelajakda avtomatizatsiya bog‘laydi. Bog‘lanmagan yangi operatsiyalar auditi alohida. |

## Loyihalar — 179 yozuv

| Maydon | Bo‘sh | Ulush | Izoh |
|---|---:|---:|---|
| Xizmat turi | 9/179 | 5% | Loyihaning xizmat turlari (naming, logo, brand guidelines va h.k.). |
| Mijoz nomi | 10/179 | 6% | Link: mijoz (Mijozlar jadvali). |
| Muhim darajasi | 15/179 | 8% | Eisenhower ustuvorlik matritsasi (muhim/shoshilinch). |
| Loyiha bosqichi | 2/179 | 1% | Loyihaning jarayon bosqichi (taklif → ishlab chiqarish → yakunlangan). |
| Start sana | 2/179 | 1% | Loyiha boshlangan sana. |
| END sana | 42/179 | 23% | Loyiha topshirish muddati (deadline). |
| Kelishilgan narx | 15/179 | 8% | Mijoz bilan kelishilgan shartnoma summasi |
| Turi | 15/179 | 8% | Narx valyutasi: UZS yoki USD. |
| Kurs | 20/179 | 11% | USD kursi (loyiha yaratilgan/rejalashtirilgan vaqtdagi). |
| L Xarajatlar | 179/179 | 100% | Link: eski Chiqim jadvalidagi xarajatlar (ESKI, Finance V2'gacha). |
| Kirim link | 179/179 | 100% | Link: eski Kirim jadvalidagi daromadlar (ESKI, Finance V2'gacha). |
| PM | 41/179 | 23% | Canonical PM field. Jamoa jadvaliga link; KPI, workload va reporting shu fieldga tayanishi kerak. |
| Marketing kampaniyalari (BWIB) 2 | 158/179 | 88% | Link: bog'liq marketing kanali/kampaniya (Marketing jadvali). |
| KPI Tracking | 150/179 | 84% | Link: bog'liq KPI Tracking yozuvi. |
| Tranzaksiyalar | 5/179 | 3% | Finance V2: shu loyihaga bog‘langan barcha kirim va chiqim tranzaksiyalar. |
| Pravkalar soni | 156/179 | 87% | Mijoz tomonidan so'ralgan pravka (tuzatish) soni. |
| Maksimal bepul pravka | 156/179 | 87% | Bepul pravka (tuzatish) limiti. |
| Dizayner soatlari | 156/179 | 87% | Sarflangan ish soatlari (1-turi, masalan dizayn). |
| PM va Muloqot soatlari | 156/179 | 87% | Sarflangan ish soatlari (2-turi, masalan boshqaruv). |
| Dizaynerga kelishilgan to‘lov (UZS) | 179/179 | 100% | Qo'lda kiritiladigan xarajat summasi (Tranzaksiyalar hisobga olmasa fallback sifatida). |
| To'lov qabul qilindi (sana) | 175/179 | 98% | Mijoz birinchi to'lovni amalga oshirgan sana — AmoCRM'dan bu Airtable bazaga (PM+moliya) o'tkazish nuqtasi. Bu sana to'ldirilgach loyiha PM ishiga tayyor hisoblanadi. |
| To‘lov majburiyatlari | 179/179 | 100% |  |
| NPS Baho (1-10) | 179/179 | 100% |  |
| Mijoz Fikri (Review) | 179/179 | 100% |  |
| Onboarding Statusi | 179/179 | 100% |  |
| Keyingi Taklif (Upsell) | 179/179 | 100% |  |
| Upsell Holati | 179/179 | 100% |  |
| Jarayon bosqichi (V2) | 20/179 | 11% | Canonical loyiha stage. Tasklar va moliyaviy eslatmalar stage’dan ajratilgan. |
| Sotuvchi | 158/179 | 88% | Loyihani sotgan / yopgan mas'ul sotuvchi (Sales/Closer). Jamoa jadvalidan tanlanadi. |
| Partner | 179/179 | 100% | Loyihani olib kelgan doimiy hamkor. |
| Partner roli | 179/179 | 100% | Shu aniq loyihadagi Partner roli. Manfaatlar to‘qnashuvini nazorat qilish uchun. |
| Partner ulushi (%) | 179/179 | 100% | Shu loyiha uchun kelishilgan ulush. Default 10%; kerak bo‘lsa Partner masterdan tekshiriladi. |
| Partner ulushi yo‘nalishi | 179/179 | 100% | Ajratilgan ulush qayerga yo‘naltiriladi. |
| Mijozga chegirma (%) | 179/179 | 100% | Partner ulushidan mijoz foydasiga berilgan qism. |
| Disclosure | 179/179 | 100% | Partner mijozning vakili/outsource mutaxassisi bo‘lsa, komissiya oshkor qilinganini nazorat qiladi. |
| Partner izoh | 179/179 | 100% |  |
| CAC — birinchi shartnoma (sana) | 179/179 | 100% | Mijozning ilk xizmat sotib olganligi tasdiqlangan loyiha sanasi; boshqa loyihalarda bo‘sh qoladi. |

## Marketing — 8 yozuv

| Maydon | Bo‘sh | Ulush | Izoh |
|---|---:|---:|---|
| Kanal | 6/8 | 75% | Marketing kanali: Instagram, Telegram Ads, SEO, Referal va boshqalar. |
| Maqsad | 6/8 | 75% | Kampaniya maqsadi: awareness, lead generation, retargeting va boshqalar. |
| Natija | 6/8 | 75% | Kampaniyaning umumiy natija holati. |
| Ovchi | 7/8 | 88% | Link: Jamoa jadvalidagi mas'ul xodim (Hunter). |
| Sotuvchi | 7/8 | 88% | Link: Jamoa jadvalidagi mas'ul xodim (Closer). |
| Loyiha | 7/8 | 88% | Link: kampaniyadan kelib chiqqan loyihalar (Loyihalar jadvali). |
| Lidlar soni | 8/8 | 100% | Shu kampaniyadan kelgan lidlar soni. Qo'lda kiriting (amoCRM yoki Instagram statistikasidan). |

## Mijozlar — 105 yozuv

| Maydon | Bo‘sh | Ulush | Izoh |
|---|---:|---:|---|
| Telefon raqami | 4/105 | 4% | Mijozning telefon raqami. |
| Brands | 67/105 | 64% | Mijozga tegishli brend nomlari. Hozircha text field; alohida Brands jadvali yo‘q. |
| Faoliyat turi | 66/105 | 63% | Mijoz biznesining faoliyat yo‘nalishi yoki sohasi. |
| Manzil | 70/105 | 67% | Mijozning manzili yoki joylashuvi. |
| Email | 105/105 | 100% | Mijozning email manzili. |
| Loyihalari | 2/105 | 2% | Link: mijozning loyihalari (Loyihalar jadvali). |
| To‘lov majburiyatlari | 105/105 | 100% |  |
| Marketing kanali | 105/105 | 100% | Mijoz bizga birinchi marta qayerdan kelgan. Sotuvchi mijozni kiritganda bir marta tanlaydi. Loyihalar va tushumlarga avtomatik o'tadi. |
| CAC — 1-sotuv tasdiqlangan (sana) | 105/105 | 100% | Ilk sotuv daliliga ko‘ra. Bo‘sh bo‘lsa avtomatik CAC mijoz sanog‘i faqat baholash bo‘ladi. |
| CAC — oylik P&L bog‘lanishi | 6/105 | 6% | Birinchi to‘lovli loyiha boshlanish oyiga tegishli P&L. Proksi ekanini unutmaslik kerak. |

## Jamoa — 45 yozuv

| Maydon | Bo‘sh | Ulush | Izoh |
|---|---:|---:|---|
| Darajasi | 37/45 | 82% |  |
| Mutaxassislik | 1/45 | 2% |  |
| Aloqa | 37/45 | 82% |  |
| Telegram | 34/45 | 76% |  |
| Loyihalar | 38/45 | 84% |  |
| KPI Tracking | 43/45 | 96% |  |
| Marketing (Hunter) | 44/45 | 98% |  |
| Marketing (Closer) | 44/45 | 98% |  |
| To‘lovlar (Tranzaksiyalar) | 18/45 | 40% | Shu xodimga qilingan barcha to'lovlar — maosh, bonus, freelancer ishi. |
| To‘lov majburiyatlari | 40/45 | 89% |  |
| Oylik oklad (UZS) | 37/45 | 82% | Xodimning belgilangan oylik maoshi. CEO/founder okladi ham shu yerda yuritiladi. Tranzaksiyada 'Ish haqi — oklad' kategoriyasi bilan to‘lanadi. |
| Loyihalar 2 | 41/45 | 91% |  |
| Tranzaksiyalar | 39/45 | 87% |  |
| U-Enter ijara (UZS) | 39/45 | 87% |  |
| AI xarajati (UZS) | 42/45 | 93% |  |
| Moizvonki (UZS) | 41/45 | 91% |  |
| Raqam to‘lovi (UZS) | 40/45 | 89% |  |
| Bonus (UZS) | 41/45 | 91% |  |
| Boshqa xarajat (UZS) | 45/45 | 100% |  |

## KPI Tracking — 3 yozuv

| Maydon | Bo‘sh | Ulush | Izoh |
|---|---:|---:|---|
| Oy | 3/3 | 100% |  |
| Lavozimi | 1/3 | 33% |  |
| Ism Familya | 1/3 | 33% |  |
| Loyihalar | 1/3 | 33% |  |
| Reja (kirim) | 1/3 | 33% |  |

## Moliya kategoriyalari — 22 yozuv

| Maydon | Bo‘sh | Ulush | Izoh |
|---|---:|---:|---|
| Izoh | 9/22 | 41% |  |
| Faol | 7/22 | 32% |  |
| [TEXNIK] Budjet qatorlari | 14/22 | 64% | Oylik budjetdagi Kategoriya fieldining inverse linki. Odatda qo‘lda tahrirlanmaydi. |
| [TEXNIK] Tranzaksiyalar | 4/22 | 18% | Tranzaksiyalar jadvalidagi Kategoriya fieldining inverse linki. Odatda foydalanuvchi qo‘lda tahrirlamaydi. |

## Oylik budjet — 16 yozuv

| Maydon | Bo‘sh | Ulush | Izoh |
|---|---:|---:|---|
| Izoh | 6/16 | 38% |  |
| Fakt (UZS) — qo‘lda | 8/16 | 50% | Hozir qo‘lda kiritiladi. Keyingi bosqichda Finance V2 Tranzaksiyalardan avtomatik olish tavsiya etiladi. |
| Tranzaksiyalar | 9/16 | 56% |  |

## Hisoblar — 4 yozuv

| Maydon | Bo‘sh | Ulush | Izoh |
|---|---:|---:|---|
| Izoh | 4/4 | 100% |  |
| Tranzaksiyalar 2 | 4/4 | 100% |  |
| Balans baholash kursi (UZS/USD) | 4/4 | 100% | USD hisobini UZSda baholash uchun kurs. Har kuni yangilash kerak; tarixiy tranzaksiyalar kursidan alohida. |
| Balans baholash kursi sanasi | 4/4 | 100% |  |

## To‘lov majburiyatlari — 13 yozuv

| Maydon | Bo‘sh | Ulush | Izoh |
|---|---:|---:|---|
| Loyiha | 13/13 | 100% |  |
| Mijoz | 13/13 | 100% |  |
| Xodim | 3/13 | 23% |  |
| Kurs | 13/13 | 100% |  |
| Tranzaksiyalar | 13/13 | 100% |  |
| Tranzaksiyalar 2 | 10/13 | 77% |  |

## Oy yopilishi — 1 yozuv

| Maydon | Bo‘sh | Ulush | Izoh |
|---|---:|---:|---|
| Sana | 1/1 | 100% |  |
| Tranzaksiyalar tekshirildi | 1/1 | 100% |  |
| P&L yopildi | 1/1 | 100% |  |
| Cash Flow yopildi | 1/1 | 100% |  |
| Likvidlik yopildi | 1/1 | 100% | Oy yakunida hisob qoldiqlari, debitor/kreditor va operativ likvidlik tekshirildi. |
| Debitor tekshirildi | 1/1 | 100% |  |
| Kreditor tekshirildi | 1/1 | 100% |  |
| Hujjatlar tekshirildi | 1/1 | 100% |  |
| Rahbar tasdiqladi | 1/1 | 100% |  |

## Oylik P&L — 35 yozuv

| Maydon | Bo‘sh | Ulush | Izoh |
|---|---:|---:|---|
| Tranzaksiyalar | 13/35 | 37% |  |
| Yangi mijozlar soni | 35/35 | 100% | Shu oy birinchi marta Jon Brandingdan xizmat sotib olgan yangi mijozlar soni. Loyihalar soni emas. |
| P&L — Haqiqiy dividend (UZS) | 35/35 | 100% | Faqat real taqsimlangan, tasdiqlangan dividend summasi (qo‘lda). Reja ulushi pul to‘loviga teng emas. |
| Soliq — hisoblangan real (UZS) | 35/35 | 100% | Soliq organi yoki moliyachi hisoblab tasdiqlagan summa. Bo‘sh = tasdiqlanmagan. 0 faqat soliq haqiqatan 0 bo‘lsa. |
| Soliq — tasdiq sanasi | 35/35 | 100% | Hisoblangan soliq va soliq bazasi moliyachi tomonidan tekshirilgan sana. |
| Soliq — tasdiqlangan baza (UZS) | 35/35 | 100% | Qonunchilik va soliq rejimiga mos real soliq bazasi. Bo‘sh bo‘lsa taxminiy P&L daromadi ishlatiladi. |
| Mijozlar | 14/35 | 40% |  |

## Cashflow — oylik — 24 yozuv

| Maydon | Bo‘sh | Ulush | Izoh |
|---|---:|---:|---|
| Oy | 2/24 | 8% |  |
| Hisob | 2/24 | 8% |  |
| Oy boshi qoldiq (UZS) | 12/24 | 50% | Oy boshidagi qoldiq UZS ekvivalentida. |
| Tranzaksiyalar | 7/24 | 29% |  |
| Tranzaksiyalar 2 | 24/24 | 100% |  |
| Oy boshi (hisob valyutasida) | 17/24 | 71% | Barcha hisoblar uchun native summa; USD hisobda dollar, UZS hisobda so‘m. Tasdiqsiz oylar bo‘sh qoldiriladi. |
| Oy boshi manbasi | 16/24 | 67% |  |

## Likvidlik holati — 1 yozuv

| Maydon | Bo‘sh | Ulush | Izoh |
|---|---:|---:|---|
| Bo‘sh qo‘lda maydon topilmadi | — | — | |

## Partnerlar — 1 yozuv

| Maydon | Bo‘sh | Ulush | Izoh |
|---|---:|---:|---|
| Telefon | 1/1 | 100% |  |
| Loyihalar | 1/1 | 100% |  |

