# Davomatdan foydalanish qo'llanmasi

2026-10-22. Xodim va administrator uchun. Ko'rsatmalar shu sanadagi repo ekranlari asosida yozilgan; telefon va prod Wi-Fi bilan yakuniy qabul sinovi alohida o'tkaziladi.

## Xodim: birinchi kirish

1. Telefonda `https://oisha.jonbranding.uz/api/attendance/app` sahifasini oching. HTTPS ishlashi kerak.
2. "Telegram bilan kirish" ni bosing. Telegram autentifikatsiyasini o'zingiz yakunlang; kod yoki parolni administratorga yubormang.
3. "Davomatga ulanish" chiqsa, haqiqiy ism-familiyangizni yozib, so'rov yuboring. Rahbar tasdiqlagach sahifani yangilang. "So'rovingiz yuborilgan" holatida qayta-qayta yubormang.
4. Noto'g'ri Telegram hisobiga kirgan bo'lsangiz, HRga bildiring; yangi dublikat xodim yaratishni so'ramang.

## Har kuni kelish va ketish

Ofisda ofis Wi-Fi'siga ulaning. Mobil internet va VPNni o'chiring. "Keldim" ni bir marta bosing va brauzer so'raganda lokatsiyaga ruxsat bering. GPS faqat tugma bosilganda bir marta olinadi; doimiy kuzatuv yo'q. So'rov ofis hududi hamda sozlangan ofis internetining tashqi IP manzili bilan tekshiriladi. Kamera, QR va yuz tekshiruvi talab qilinmaydi.

Yashil xabarni va "Bugun" qismidagi kelish vaqtini tekshiring. Ketayotganda "Ketdim" ni bosing va ketish yozuvi ham paydo bo'lganini tekshiring. Tugma bosilishi yozuv qabul qilinganini o'zi isbotlamaydi. Kutish yoki tarmoq xatosida avval sahifani yangilab bugungi yozuvni ko'ring; keyin zarur bo'lsa qayta urinib ko'ring.

Ekrandagi vaqt Toshkent vaqti. Umumiy grafik 10:00–19:00, 10 daqiqa grace bilan; HR belgilagan shaxsiy va ixtiyoriy kunlar ustun. "Kechikdi", "Erta ketdi", "Ruxsatli", "Tekshiruvda" kabi holatlar faktni bildiradi. Modul jarima yoki ish haqidan ushlab qolishni hisoblamaydi.

## Administrator: hisobni bog'lash

`https://oisha.jonbranding.uz/api/attendance/app/admin` ni Telegram orqali owner/admin hisobida oching. Oddiy xodim HR ma'lumotlarini ko'ra olmaydi.

"Jamoa va grafik" ichidagi ulanish so'rovlarini oching. Telegram egasi va ism-familiyani tekshiring. Xodim bazada bo'lsa, ro'yxatdan aynan o'sha yozuvni tanlang va "Tasdiqlash" ni bosing. "Yangi xodim sifatida" faqat bazada xodim yo'qligi aniqlanganda tanlanadi. Shubhali so'rovni tekshiring yoki "Rad etish" ni bosing. So'ng ro'yxatni qayta ochib, bog'lanish natijasini tekshiring.

Shaxsiy grafikning ish kunlari, boshlanish/tugash va ixtiyoriy kunlarini "Jamoa va grafik" da tekshiring. Shaxsiy o'zgarishni saqlagach, tanlangan xodim grafigini qayta o'qing. Ruxsatli yoki dam olish kunini tegishli sana va sabab bilan kiriting. Grafik va tuzatishlar moliyaviy jarima belgilamaydi.

## Administrator: ofis Wi-Fi'sini belgilash

1. HR panelni ofisda, ofis Wi-Fi'siga ulangan holda oching. VPN va mobil internetni o'chiring.
2. "Sozlamalar" bo'limida "Ofis Wi-Fi'ni shu yerdan belgilash" ni bosing.
3. Sahifani yangilab saqlangan tarmoqni va shu tarmoqqa mos kelish holatini tekshiring. Noto'g'ri tarmoq saqlansa, uni bekor qilib, haqiqiy ofis Wi-Fi'sida qayta belgilang.
4. Internet provayderi public IP ni almashtirsa, ofisda turib qayta belgilang. Wi-Fi nomining bir xil bo'lishi yetarli emas; server tashqi IP ni solishtiradi.

Ofis Wi-Fi'si hali belgilanmaganida mavjud backend GPS bilan ishlashga ruxsat beradi. Wi-Fi nazoratini ishga tushirish uchun bu sozlashni yakunlash shart. IP aniqlanmasa xavfsizlik tekshiruvini chetlab o'tmang; server administratoriga murojaat qiling.

Ofis koordinatasini o'zgartirishda "Ofis joylashuvini shu yerdan belgilash" faqat to'g'ri ofis joyida bosiladi. Bu Wi-Fi belgilashdan alohida sozlama.

## Hisobot va eksport

HR paneldagi "Bugun" bo'limida kunlik holatni ko'ring. "Hisobotlar" da boshlanish va tugash sanasi, kerak bo'lsa xodimni tanlang. "Oylik xulosa" jamlangan soat/daqiqa/kunlarni, "Barcha yozuvlar" esa alohida kelish-ketishlarni beradi. "Ko'rsatish" ni bosing. "Excel" yoki "PDF" orqali yuklang va fayl ochilganini tekshiring.

Hisobot davomat boshlangan kundan oldingi davr uchun davomatni tiklamaydi. Chiqish belgisi yetishmasa, to'liq ish soati deb taxmin qilmang. Tekshiruvdagi va ruxsatli kunlarni HR bilan aniqlashtiring. Eksport xodim ma'lumotlarini saqlaydi; faqat vakolatli kishiga yetkazing.

## Muammolar va yechimlar

| Holat | Amal |
| --- | --- |
| "Lokatsiyaga ruxsat bering" | Brauzerning shu sayt uchun location ruxsatini yoqing, so'ng tugmani qayta bosing. |
| "GPS aniqlanmadi" yoki hududdan tashqari | Telefon lokatsiyasini tekshiring, deraza/ochiq joyga yaqinlashing; ofisda ekaningizni tekshiring. HRga xato vaqtini ayting. |
| "Ofis Wi-Fi'siga ulaning" | Mobil internet/VPNni o'chiring, haqiqiy ofis Wi-Fi'sini tanlang. Public IP o'zgargan bo'lsa HR qayta belgilaydi. |
| `422 office_ip_unknown` | IP serverda aniqlanmadi. HR ofisda ekanini tekshiradi; server administratori faol proxy sarlavhalarini tekshiradi. Bu xodim xatosi bo'lishi shart emas. |
| "Telegram hisobingiz ... bog'lanmagan" | Ulanish so'rovini yuboring; HR mavjud xodimga bog'laydi. |
| "Bu bo'lim uchun HR/admin huquqi kerak" | To'g'ri Telegram hisobiga kiring; huquqni owner tekshiradi. |
| "Avval Keldim belgisini qo'ying" | Bugungi kelish yozuvini tekshiring; yo'qolgan belgi uchun HRga murojaat qiling. |
| "Allaqachon qo'yilgan" | Bugungi yozuvni yangilab tekshiring; yangi dublikat yaratmang. |
| Server javob bermadi yoki internet yo'q | Avval bugungi yozuvni qayta o'qing. Saqlangan bo'lishi mumkin. HRga sana, vaqt va xato matnini yuboring; parol/token yubormang. |
| Excel/PDF yuklanmadi | Sessiya, ruxsat va tanlangan davrni tekshiring; brauzer yuklamalarini ko'ring. Bo'sh faylni tayyor hisobot deb yubormang. |

Server tekshiruvi: `docs/attendance-proxy-audit.md`. Insident dalillari: `docs/attendance-incident-2026-10-22.md`. Payroll API: `docs/attendance-payroll-api.md`. Bu hujjatlardagi o'zgarishlar alohida PRlarda yuritiladi.
