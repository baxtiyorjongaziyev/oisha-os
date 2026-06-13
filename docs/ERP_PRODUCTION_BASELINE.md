# Oisha ERP Production Baseline

Oisha serverining tirik bo'lishi ERP actionlarini bajarishga tayyor degani emas.

## Tekshiruv endpointlari

- `/healthz`: HTTP runtime tirikligi va asosiy production gate.
- `/readyz`: Oracle runtime avtomatsiya dependency'lari.
- `/api/system/erp-readiness`: ERP actionlarini boshlash uchun barcha real manbalar.

ERP readiness quyidagilarni real tekshiradi:

| Dependency | Tayyor hisoblanishi uchun |
| --- | --- |
| Turso | `SELECT 1` ishlashi va canonical backend aynan `turso` bo'lishi |
| AmoCRM | OAuth bloklanmagan va `check_connection()` muvaffaqiyatli |
| Telegram bot | Bot API orqali `getMe` muvaffaqiyatli |
| Telegram userbot | Telethon client mavjud va authorized |
| Airtable | Base metadata real API orqali olinishi |
| Google Calendar | Primary calendar events API real javob qaytarishi |
| Action queue | Persistent action store query ishlashi |

Birorta dependency ishlamasa:

- endpoint `503` qaytaradi;
- `ready=false` bo'ladi;
- `autonomy_level=A0` bo'ladi;
- `blockers` ichida aniq sabab ko'rsatiladi;
- ERP avtonom actionlari bajarilmasligi kerak.

## Operator tekshiruvi

Oracle VM ichida:

```bash
python scripts/prod/erp_readiness_check.py
```

Boshqa API manzilini tekshirish:

```bash
python scripts/prod/erp_readiness_check.py --url https://oisha.example.com
```

Exit kodlari:

- `0`: ERP actionlari uchun tayyor.
- `1`: endpoint ishladi, lekin dependency blocker mavjud.
- `2`: endpointga ulanib yoki javobni o'qib bo'lmadi.

## Hozirgi avtonomiya chegarasi

ERP readiness to'liq yashil bo'lsa ham hozirgi maksimal daraja `A2`:

- Oisha real manbalarni o'qishi mumkin.
- Oisha ichki CRM/Airtable actionlarini policy va verifier orqali bajarishi mumkin.
- Mijoz bilan to'liq avtonom muzokara keyingi identity, queue, approval va live
  verifier bosqichlari tugamaguncha yoqilmaydi.
