# Smart Attendance: yurist tekshiruv ro'yxati

Tekshiruv sanasi: 2026-10-22. Maqsad: davomatdagi shaxsga doir ma'lumotlar oqimini yurist va texnik mas'ul bilan tekshirish. Bu hujjat muvofiqlik tasdig'i emas. Belgilanmagan kataklar bajarilmagan yoki tasdiqlanmagan.

## Amaldagi manba va eski taxminni tuzatish

Rasmiy manba: [O'RQ-547, 02.07.2019, LexUZ amaldagi matni](https://lex.uz/uz/docs/-4396419), 2026-10-22 da ochildi. LexUZ matnida 27¹-modda 2026-03-26 dagi O'RQ-1125 tahririda ko'rsatilgan.

27¹-modda biometrik, genetik va ko'rsatilgan telekommunikatsiya abonenti ma'lumotlarini O'zbekistonda saqlashni talab qiladi. Boshqa ma'lumotlarning xorijda saqlanishi uchun muqobil shartlar sanalgan: teng himoyali davlat, tegishli shartnomaviy/korporativ qoidalar yoki tasdiqlangan xalqaro standartlar. 20-modda reyestr talabini 27¹-moddaning ikkinchi qismiga bog'laydi. Yurist aynan davomat ma'lumotining toifasi, qo'llanadigan shartlar va quyi hujjatlarni tasdiqlashi kerak. Faqat xodim roziligi borligi barcha lokalizatsiya shartlari bajarilganini anglatmaydi.

Shu sabab reja ichidagi eski "barcha O'zbekiston fuqarolari ma'lumoti faqat O'zbekistondagi serverda" jumlasi joriy huquqiy xulosa sifatida ishlatilmaydi. 15-modda transchegaraviy uzatish, 18/21-modda asos va rozilik, 26-modda biometrika, 27/28-modda himoya va maxfiylik, 30/31-modda huquq va majburiyatlar uchun yuristga beriladi.

## Texnik inventar, repo asosida

| Oqim | Repo manbasi | Prod bo'yicha holat |
| --- | --- | --- |
| Xodim ID, ism, Telegram bog'lanishi | `linking.py`, mavjud `employees` | Haqiqiy yozuvlar bu tekshiruvda o'qilmagan |
| Kelish/ketish, vaqt, holat, kechikish va tuzatish | `schema.py`, `service.py`, `summary.py` | Saqlash mamlakati noma'lum |
| Bir martalik GPS: lat/lon, aniqlik, tekshiruv tafsiloti | `service.py:submit_location`, `attendance_verifications` | GPS bazada saqlanadi; doimiy kuzatuv yo'q |
| Ofis public IP va auditdagi request IP | `network.py`, `audit.py` | Loglar va IP retention muddati tekshirilmagan |
| Ulanish/tekshiruv xabarlari | `notifier.py`, setup routes | Telegram manzili va amaldagi yetkazish doirasi tekshirilmagan |
| Excel/PDF va payroll xulosa | `export.py`, `summary.py`; payroll API alohida PR | Yuklangan fayl nusxalari joylashuvi noma'lum |
| Yuz/biometrika | UI'da o'chirilgan; backend adapter mavjud | Yoqish uchun alohida yuridik tekshiruv kerak |

Yuqoridagi Python fayllari `src/services/core/attendance/` ichida, setup routes esa `src/api/routes/attendance_setup_routes.py`. Backenddagi eski QR/kiosk fayllari o'chirilmaydi.

## To'ldiriladigan tekshiruvlar

- [ ] Yurist: davomat maqsadi, ma'lumot toifasi va ishlov berish asosi bo'yicha yozma xulosa tuzsin. Mehnat munosabatlari va lokatsiya tekshiruvining zaruriyatini ko'rib chiqsin.
- [ ] HR: xodimga ko'rsatiladigan xabarnoma, murojaat manzili, e'tiroz/tuzatish yo'li va zarur rozilik tartibini tayyorlasin. Telefonning GPS ruxsatini yuridik rozilikning to'liq dalili deb qabul qilmasin.
- [ ] Texnik mas'ul: Contabo ilova serveri, Turso bazasi va replikalari, zaxira nusxa, monitoring, Telegram va eksport saqlanadigan qurilmalar uchun haqiqiy mamlakatni provayder hujjati bilan aniqlasin. IP geolokatsiya taxmini yetarli emas.
- [ ] Yurist: shu inventar bo'yicha 27¹ va reyestr talablari qo'llanishini hal qilsin; zarur reyestr raqami yoki asoslantirilgan istisnoni qayd etsin.
- [ ] Xarid/texnik mas'ul: tegishli provayder shartnomasi, subpudratchilar va amaldagi xavfsizlik dalillarini taqdim etsin. Yurist chetga uzatish/saqlash asosini tasdiqlasin.
- [ ] HR/texnik mas'ul: GPS tafsiloti, IP, davomat, audit, eksport va backup uchun alohida saqlash muddatlarini belgilasin. Hozir avtomatik o'chirish mexanizmi bor deb taxmin qilinmasin. Append-only audit bilan o'chirish majburiyati qanday yarashishi yozilsin.
- [ ] Texnik mas'ul: xodim faqat o'z yozuvini, HR vakolat doirasida jamoani ko'rishini tekshirsin. Hisobchi uchun davomat ruxsati, eksport nazorati va sobiq xodim kirishini bekor qilish tartibini ko'rsatsin.
- [ ] HR: noto'g'ri GPS, internet yo'qligi, yetishmagan chiqish belgisi va shaxsiy grafik bo'yicha inson ko'rib chiqishi tartibini belgilasin. Faktlardan avtomatik jarima yoki maosh ushlab qolish kiritilmasin.
- [ ] Texnik mas'ul: zaxiradan tiklash, ruxsatsiz ko'rish va eksport tarqalishi holatlari uchun insident tartibini tayyorlasin; yurist xabar berish talablarini aniqlasin.
- [ ] Owner: biometrikani yoqish yoki yangi manzilga ko'chirishdan oldin ushbu inventar va yuridik xulosani yangilasin.

## Dalil reyestri

| Qaror/dalil | Holat | Mas'ul | Hujjat/havola | Tekshiruv sanasi |
| --- | --- | --- | --- | --- |
| Contabo va Turso real saqlash mamlakati | noma'lum | tayinlanmagan | taqdim etilmagan | tekshirilmagan |
| Lokalizatsiya/chetga uzatish asosi | noma'lum | yurist | taqdim etilmagan | tekshirilmagan |
| Reyestr yoki istisno qarori | noma'lum | yurist | taqdim etilmagan | tekshirilmagan |
| Xabarnoma va saqlash siyosati | noma'lum | HR | taqdim etilmagan | tekshirilmagan |
| Yakuniy yuridik xulosa | olinmagan | yurist | taqdim etilmagan | tekshirilmagan |

Kodning testdan o'tishi ushbu kataklarni tasdiqlamaydi. Hujjatni yuristga yuborish bu vazifa davomida bajarilmagan.
