# Hisobchi uchun davomat API

Qaror: 2026-10-22, owner usul tanlashni dasturchiga topshirdi. B varianti tanlandi: Oisha ichidagi API. Sheetsga ikkinchi nusxa yozilmaydi.

## Chaqirish

`GET /api/attendance/payroll/summary?start=YYYY-MM-DD&end=YYYY-MM-DD`

Ixtiyoriy `employee_id` musbat son. Davr ikkala chegara bilan hisoblanadi, ko'pi bilan 366 kun; kelajakdagi yakun sanasi rad etiladi. Sana va kun chegarasi `Asia/Tashkent` bo'yicha.

Hisobchi iste'molchisi mavjud service-token mexanizmi orqali faqat `attendance:read:all` scope bilan murojaat qiladi. `finance:read` yetmaydi. Owner/admin sessiyasi ham o'qiy oladi. API ochiq/public emas. Tokenni URL yoki qo'llanmaga yozmang. Alohida Hisobchi service tokenini yaratish/ulash ushbu kod o'zgarishida bajarilmagan.

## Javob shartnomasi

- `version=1`, `source=attendance.period_summary`, `generated_at`: hosil qilingan vaqt va manba.
- `start`, `end`: so'ralgan davr; `effective_start`: davomat ishga tushgan kundan oldingi kunlar hisoblanmasligi uchun haqiqiy boshlanish.
- `coverage=before_go_live`: davr ishga tushishdan oldin, `rows=[]`; `available`: davomat ma'lumoti mavjud davr.
- `informational_only=true`: bu ish haqi hisoblash natijasi emas.
- `provisional=true`: davr bugunni qamraydi yoki chiqish belgisi yetishmaydi/tekshiruv bor. HR buni aniqlashtirishi kerak. `false` ham yuridik yoki payroll tasdig'i emas.
- `rows`: faol xodimlarning `summary.period_summary()` natijasi. `worked_minutes`, `overtime_minutes`, `late_minutes`, `early_leave_minutes` birligi daqiqa. `worked_hours`, `overtime_hours` ikki kasrgacha yaxlitlangan soat; hisob-kitobda asl daqiqani saqlang. `approved_leave_days` birligi kun. `missing_check_out`, `pending_review` ma'lumot yetarliligi ko'rsatkichlari.

Bazaviy ish haqi, pul miqdori, jarima va ushlab qolish javobda yo'q. GPS va Telegram ID payrollga ko'chirilmaydi. Chiqish belgisi bo'lmasa ishlangan vaqtni taxminiy to'ldirmang. Faol bo'lmagan xodimlar mavjud summary kontrakti bo'yicha chiqmaydi; tarixiy ishdan ketgan xodimlar uchun bu API to'liq payroll ro'yxati emas.

## Hisobchi tomondagi tartib

1. Davrni va ixtiyoriy xodimni tanlang, ruxsatli API orqali o'qing.
2. HTTP statusni tekshiring. `503 attendance_not_configured` yoki boshqa xatoni nol soatga aylantirmang; manba mavjud emas deb belgilang.
3. `coverage`, `effective_start`, `provisional`, `missing_check_out`, `pending_review` ni tekshiring. Noaniq davrni HRga qaytaring.
4. Natijani faqat davomat axboroti sifatida ko'rsating. Summani pulga ko'paytirish yoki maosh jadvalini o'zgartirish ushbu endpointning vazifasi emas.
5. Har o'qish auditda `payroll_summary_viewed` bilan qayd etiladi. Javob `Cache-Control: no-store`; avtomatik tarqatish yoki Sheetsga yozish yo'q.

Cheklov: endpoint va kontrakt tayyorlanishi Hisobchi ishlab turgan iste'molchisi uni chaqirgani yoki ma'lumot uzatilgani isboti emas. Prod integratsiya read-back alohida tekshiriladi.
