# Smart Attendance — Repository audit va implementatsiya rejasi

Holat: **1–4, 6–7-bosqichlar bajarildi** (HR dashboard: hisobot, Excel/PDF, grafik va kunlik belgilar) (ekranlar: /davomat, /davomat/kiosk, /davomat/admin; ofis: 41.3056580, 69.2814659, radius 150 m) (API: /api/attendance/*; EMPLOYEE roli o‘rniga ATTENDANCE_SELF + employees.telegram_id bog‘lanishi) (sxema, GPS, QR, rules engine; ish vaqti 10:00–19:00, grace 10 daq, Du–Sha (owner); Mumtozmaxal: chorshanba dam, yakshanba ish; Ahror: har kuni — shaxsiy grafik admin orqali kiritiladi). Owner qarorlari (2026-10-22): EMPLOYEE roli — ha; Telegram login; bitta ofis; yuz tekshiruvi hozircha yo‘q; GPS+QR o‘tsa avtomatik tasdiq, shubhali holat Telegramga (tasdiqlovchi: OWNER_ID, owner boshqasini aytmaguncha).

## 1. Audit natijalari (manbadan tekshirilgan)

| Soha | Topilgan holat | Manba |
|---|---|---|
| Backend | Python 3.11 + FastAPI, routerlar `src/api/routes/*`, ulanish `src/services/api_server/core.py` (`include_router`) | kod |
| Auth | Telegram login → session JWT (`oisha_token` cookie), Bearer `OISHA_API_SECRET`, service tokenlar | `src/api/auth_service.py`, `src/api/security.py` |
| RBAC | `Role` (owner/admin/seller/targetolog/viewer/service) + `Permission` enum, `require_permissions(...)` dependency, fail-closed | `src/api/rbac.py` |
| Xodimlar | `employees` jadvali (id, telegram_id, name, role, base_salary, is_active, hire_date) | `src/services/core/finance/erp_schema.py` |
| Filiallar (Branches) | **Mavjud emas** | grep: topilmadi |
| HR moduli | **Mavjud emas** (faqat ERP/KPI) | — |
| Payroll | Hisobchi: `advances`, `kpi_scores`, Google Sheets `budget_salary.py` (`add_salary_entry`, `get_salary_summary`) | `services/core/finance/` |
| Ma'lumotlar bazasi | **PostgreSQL emas** — Turso (libsql) + SQLite fallback; migratsiyalar `CREATE TABLE IF NOT EXISTS` ro'yxati ko'rinishida | `database.py`, `erp_schema.py` |
| Frontend | Oisha Python tomonida server-side HTML/statik (`src/static/*.html`, `src/api/templates`). `apps/web` (Next.js) — SalesCoach, boshqa workspace | kod |
| Navigatsiya "HR Management" | Yagona Oisha admin SPA navigatsiyasi yo'q; dashboardlar alohida sahifalar | `src/static/` |

Xulosa: PostgreSQL, Prisma yoki React Native kiritilmaydi — mavjud stekka zid. Modul Python/FastAPI + Turso/SQLite ustida, UI esa mavjud statik dashboardlar uslubida (mobil-first HTML + vanilla JS) quriladi.

## 2. Arxitektura

```
src/services/core/attendance/      # domen (har fayl ≤400 qator)
  schema.py        # 10 jadval + branches/shifts, indekslar, UNIQUE cheklovlar
  geofence.py      # haversine, accuracy/timestamp, fake-GPS risk skori
  qr_tokens.py     # HMAC-SHA256 imzoli, 30s oyna, nonce, bir martalik (qr_challenges)
  face/            # FaceVerifier Protocol + DisabledProvider + MockProvider (faqat test)
  rules.py         # ON_TIME/LATE/EARLY_LEAVE/ABSENT/APPROVED_LEAVE/DAY_OFF/PENDING_REVIEW,
                   # grace period, tungi smena (kesishgan sana), bayram/dam olish
  session_service.py  # holat mashinasi: created→location_ok→qr_ok→face_ok→confirmed
  payroll_export.py   # oylik xulosa (soat, overtime, late min) — jarima HISOBLAMAYDI
  reports.py          # dashboard KPI, XLSX (openpyxl) / PDF eksport
src/api/routes/attendance_routes.py   # /api/attendance/* (spec’dagi 10 endpoint)
src/static/attendance/                # employee.html (mobil), kiosk.html (QR monitor), admin.html
tests/test_attendance_*.py
```

### Ma'lumotlar bazasi (Turso/SQLite)
`attendance_branches`, `geofences`, `attendance_policies`, `attendance_shifts`, `shift_assignments`,
`attendance_sessions`, `attendance_events`, `attendance_verifications`, `qr_challenges`,
`face_enrollments`, `attendance_corrections`, `attendance_audit_logs`.
- `employees.id` ga FK (SQLite’da `PRAGMA foreign_keys`), mavjud jadvalga **tegilmaydi**.
- Duplicate check-in: `UNIQUE(employee_id, work_date, kind)` + `Idempotency-Key`.
- Replay: `qr_challenges.nonce UNIQUE`, `used_at` atomik `UPDATE ... WHERE used_at IS NULL`.
- Parallel so'rovlar: shartli UPDATE (optimistic) — rowcount=0 ⇒ 409.

### Xavfsizlik
- Yangi permissionlar: `attendance:self`, `attendance:read:all`, `attendance:manage`, `attendance:kiosk`.
- Xodim roli: mavjud `Role` enumga `EMPLOYEE` qo‘shish kerak (rbac.py — shared, tasdiq kerak).
- Rate limit (in-process token bucket), pydantic validatsiya, har mutatsiya → audit log.
- Biometrika: xom rasm saqlanmaydi; embedding/template Fernet (`ATTENDANCE_BIOMETRIC_KEY`) bilan shifrlanadi; rozilik (`consent_at`, `consent_version`) bo‘lmasa enrollment yo‘q; retention sozlamasi.
- GPS faqat check-in/out bosilganda bir marta olinadi; doimiy tracking yo‘q.
- Muqobil yo‘l (biometrikasiz): GPS + QR + HR/manager tasdig'i → `PENDING_REVIEW`.

### Face verification — halollik
Repo’da yuz tanish provayderi va kaliti **yo‘q**. Shuning uchun: `FaceVerifier` interfeysi, default `disabled` (face bosqichi `PENDING_REVIEW` beradi), testlar uchun `MockProvider`. Productionga variantlar (tanlov sizda): AWS Rekognition (Face Liveness), Azure Face (Limited Access), FaceTec, yoki o‘z serverda InsightFace. Liveness’ni brauzerda ishonchli qilish cheklangan — kuchli liveness uchun native SDK (FaceTec/AWS Amplify Liveness) tavsiya.

### Payroll
`payroll_export.monthly_summary()` → worked_hours, overtime, late_minutes, early_leave, approved_leave. Hisobchiga **faqat ma'lumot** sifatida uzatiladi; avtomatik jarima/ushlab qolish yo‘q.

### Compliance vazifasi (alohida)
O‘zR "Shaxsga doir ma'lumotlar to‘g‘risida"gi qonun (O‘RQ-547) bo‘yicha **yuristga tekshiruv vazifasi**. 2026-10-22 tuzatish: LexUZ amaldagi matnida 27¹-modda 2026-yilda yangilangan; barcha fuqarolar ma'lumotlari uchun bitta umumiy lokalizatsiya xulosasi qo‘llanmaydi. Ma'lumot toifasi, xorijda saqlash shartlari va reyestr masalasi `docs/attendance-compliance-checklist.md` asosida yuristga beriladi. Contabo/Turso saqlash mamlakati tekshirilmagan, biometrika yoqilmagan.

## 3. Bosqichlar (har biri alohida commit, pre-flight yashil)
1. Schema + migratsiya + testlar
2. Geofence + QR token servis + testlar
3. Session holat mashinasi + rules engine (tungi smena, grace) + testlar
4. API routerlar + RBAC + rate limit + idempotency + testlar
5. Face adapter (disabled/mock) + muqobil oqim
6. Mobil xodim UI + kiosk QR ekrani
7. HR dashboard + XLSX/PDF eksport
8. Payroll export
9. Security review (bandit, threat model), deploy hujjati, `.env.example`, qo‘llanma

## 4. Owner qarorini talab qiladigan savollar
1. `rbac.py` ga `EMPLOYEE` roli qo‘shishga ruxsat (shared fayl)?
2. Xodimlar kirishi: Telegram login (mavjud) yetarlimi?
3. Face provider: hozircha `disabled` + muqobil oqim bilan boshlaymizmi?
4. Filiallar soni va koordinatalari (seed uchun) — yoki UI orqali kiritiladi?
