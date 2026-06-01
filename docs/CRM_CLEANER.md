# Oisha CRM Cleaner

AmoCRM da dublikatlarni kamaytirish va keraksiz sdelkalarni AI bilan tasniflash uchun ikkita modul.

## Nima qiladi

### 1. `telegram_phone_enricher.py`
- AmoCRM contactlaridan telefon raqami yo'qlarini topadi.
- Contact nomi, izoh va custom fieldlardan `@username` yoki `t.me/...` qidiradi.
- Telethon userbot orqali Telegram dan raqamni aniqlaydi (`get_entity` + `ImportContactsRequest` zond).
- Topilgan raqamni AmoCRM contactiga `PATCH /contacts/{id}` orqali yozadi.
- AmoCRM o'zining native dedup funksiyasi keyin avtomatik birlashtiradi.
- Hech narsa o'chirilmaydi. Har bir o'zgarish `OISHA_PHONE_ENRICHED` tegi va izoh bilan audit qilinadi.

### 2. `deal_ai_analyzer.py`
- Har aktiv sdelka uchun: lead + contact + Telegram suhbat tarixini yig'adi.
- Gemini yoki Claude ga yuborib, sdelkani 6 ta kategoriyaga ajratadi:
  - `REAL_CLIENT` — haqiqiy mijoz
  - `JUNK` — bekorchi
  - `PERSONAL` — shaxsiy aloqa
  - `SPAM` — spam yoki noto'g'ri raqam
  - `TEST` — ichki test
  - `UNCLEAR` — aniq emas
- Tegishli `OISHA_AI_*` tegini qo'yadi va to'liq tushuntirish izohini yozadi.

### 3. `crm_cleaner_cli.py`
Ikki modulni xavfsiz CLI orqali ishga tushiradi.

## Foydalanish

```bash
# Faqat hisobot (dry-run, hech narsa yozilmaydi)
python -m src.services.core.crm_cleaner_cli --mode enrich --limit 100
python -m src.services.core.crm_cleaner_cli --mode analyze --limit 50 --ai gemini

# AmoCRM ga yozish uchun --apply
python -m src.services.core.crm_cleaner_cli --mode enrich --limit 100 --apply
python -m src.services.core.crm_cleaner_cli --mode analyze --limit 50 --ai claude --apply

# Hammasi birga
python -m src.services.core.crm_cleaner_cli --mode all --limit 100 --apply
```

### Argumentlar
| Bayroq | Ma'no |
|---|---|
| `--mode enrich\|analyze\|all` | Qaysi pipeline ishga tushadi |
| `--limit N` | Tekshiriladigan contact/lead soni |
| `--apply` | Yozish rejimi (default — dry-run) |
| `--ai gemini\|claude` | Sdelka tahlili uchun AI provayder |
| `--messages N` | Har sdelka uchun Telegram xabar oynasi (default 30) |
| `--include-closed` | Yopilgan (won/lost) sdelkalarni ham tekshirish |
| `--force` | Sukunat soatlarini chetlab o'tish |

## Talab qilinadigan env

```
AMOCRM_SUBDOMAIN, AMOCRM_CLIENT_ID, AMOCRM_CLIENT_SECRET
API_ID, API_HASH
TELEGRAM_SESSION_STRING yoki TELEGRAM_SESSION_FILE (default: data/userbot_session.session)
GEMINI_API_KEY yoki ANTHROPIC_API_KEY
```

## Xavfsizlik

- Dry-run standart. `--apply` qo'shilmasa hech narsa AmoCRM ga yozilmaydi.
- Sukunat soatlari (`agent_policy.is_quiet_hours`) — bloklaydi, `--force` bilan chetlab o'tish mumkin.
- Hech narsa o'chirilmaydi, merge qilinmaydi. Faqat tag + izoh.
- Har run JSON hisoboti `reports/crm_cleaner_<mode>_<ts>.json` ga yoziladi.

## Testlash

```bash
python -m pytest tests/test_crm_cleaner.py -q
```

Real AmoCRM yoki Telegramga tegmaydi, hammasi mocklangan. 9 ta test.

## Mantiqiy oqim (Sdelka tozalash)

```
AmoCRM contactlar
   ↓ (phone yo'q?)
@username topish (notes + name + custom fields)
   ↓
Telegram userbot orqali resolve
   ↓
Phone topildi → PATCH AmoCRM contact (PHONE field)
   ↓
AmoCRM dedup native birlashtiradi
   ↓
Aktiv sdelkalar bo'yicha tahlil
   ↓
Telegram suhbat tarixi + lead konteksti
   ↓
AI (Gemini/Claude) → kategoriya + dalil
   ↓
Tag + izoh AmoCRM ga yoziladi
```

## Keyingi qadamlar

- `metrics_daily` jadvaliga statistik integratsiya
- Telegram bot orqali natijalarni ownerga yuborish (Reportagram alternative — Pulse uchun fundament)
- Haftalik scheduled task (`scheduled-tasks__create_scheduled_task`)
