# Twenty CRM: amoCRM bilan parallel ishlash yo'riqnomasi

Holat sanasi: 2026-10-19. amoCRM **asosiy manba** bo'lib qoladi. Twenty faqat o'qiydigan nusxa:
amoCRM → Twenty bir tomonlama. Twenty'dan amoCRM'ga yozish **yo'q** (PR #923 write-back'i alohida
flag bilan, faqat bitim nomi/bosqichi uchun, standart holatda o'chiq).

## Arxitektura

```
amoCRM ──(PR #923 Sync: leads, contacts, tasks, users; checkpoint + lease)──► parallel_crm_entities
amoCRM ──(twenty/notes.py: barcha izoh sahifalari, checkpoint)────────────────► parallel_crm_entities(kind=notes)
parallel_crm_entities ──(twenty/projector.py, twenty_sync_map)──► Twenty REST
MoiZvonki/telefon ──(POST /api/twenty/calls, call_id dedup)──► Twenty note (+ mijozga bog'lash)
```

Ikkinchi mustaqil CRM yaratilmagan: amoCRM'dan o'qish PR #923 mirror'i orqali bitta joyda.

## Ishonchlilik qoidalari

| Holat | Ma'nosi | Keyingi qadam |
|---|---|---|
| `synced` | Twenty yozuvi bor, digest mos | O'zgarmasa yozilmaydi |
| `pending` | Yozish yuborilyapti | Jarayon uzilsa → `uncertain` |
| `uncertain` | Natija noma'lum (timeout/5xx) | Avval `amoId`/`callId` bo'yicha qidiriladi; qidiruv ishlamasa yozilmaydi |
| `failed` | Aniq xato (4xx, ulanish yo'q) | Keyingi o'tishda qayta urinish |
| `blocked` | 5 marta xato | Operator ko'rib chiqadi (`--report-only` → `problems`) |

- O'qishlar (GET) 503/429/ulanish xatosida 3 martagacha qayta urinadi; yozishlar faqat ulanish
  o'rnatilmagan yoki 429 bo'lsa takrorlanadi.
- O'chirishlar tarqatilmaydi: amoCRM'da o'chirilgan yozuv `source_deleted_not_propagated` deb
  hisobotda chiqadi. Arxivlash qarori qo'lda qabul qilinadi.
- Noma'lum bosqich (`unmapped_stage`) yoki mas'ul (`unmapped_owner`) taxmin qilinmaydi.

## Owner bajaradigan sozlashlar (bir martalik)

1. **API kalit:** `https://crm.jonbranding.uz` → Settings → APIs & Webhooks → **+ Create key**.
   Kalitni serverdagi Oisha `.env` faylga yozing: `TWENTY_API_KEY=...`, `TWENTY_API_URL=https://crm.jonbranding.uz`.
2. **Maxsus maydonlar:** Settings → Data model:
   - People, Opportunities, Tasks, Notes → **+ Add field** → Number → nomi `amoId`.
   - Notes → **+ Add field** → Text → nomi `callId`.
3. **Bosqichlar:** Settings → Data model → Opportunities → Stage → amoCRM bosqichlari o'zbekcha
   nomlar bilan. Hozirgi jonli qiymatlar: `NEW, SCREENING, MEETING, PROPOSAL, CUSTOMER` (DB'dan
   tekshirildi). amoCRM `status_id` → Twenty qiymati `TWENTY_STAGE_MAP_JSON` ga yoziladi.
4. **Sotuvchilar:** Settings → Members → **Invite**. Har biri qabul qilgach, amoCRM user ID →
   Twenty workspaceMember ID `TWENTY_MEMBER_MAP_JSON` ga yoziladi. Noma'lum ID qo'yilmaydi.
5. **Ruxsatlar:** Settings → Roles → "Sotuvchi" roli. Twenty v2.48 bazasida
   `rowLevelPermissionPredicate` jadvali bor, lekin "faqat o'z bitimlarini ko'rish" UI'da
   ishlashi **tekshirilmagan**. Ishlamasa, alternativ: sotuvchiga faqat o'z "Mening bitimlarim"
   ko'rinishi (bu xavfsizlik emas, faqat qulaylik). Qabul mezoni 6 shu sababli ochiq.
6. **MoiZvonki webhook:** URL `https://<oisha-api>/api/twenty/calls`, header `X-Webhook-Secret`
   (`TWENTY_CALLS_WEBHOOK_SECRET`). Payload: `call_id, phone, direction(in|out), duration,
   recording_url, manager`. MoiZvonki'ning haqiqiy payload formati bilan mosligi **tekshirilmagan**;
   kerak bo'lsa adapter qo'shiladi.

## Ishga tushirish

```bash
python scripts/twenty_sync.py --report-only          # yozmaydi: manba vs maqsad sonlari
TWENTY_SYNC_ENABLED=1 python scripts/twenty_sync.py   # amoCRM pull + Twenty'ga proyeksiya
```

Natijada `reconcile` har tur uchun `source`, `source_deleted`, `target_synced`, `gap` va
`problems` ro'yxatini beradi. `gap != 0` bo'lsa sababini `problems` dan ko'ring.

## Pilot va ishga tushirish tartibi

1. Sintetik testlar: `python -m pytest tests/test_twenty_sync.py tests/test_parallel_crm.py`.
2. Bitta sotuvchi, faqat uning bitimlari bilan `TWENTY_STAGE_MAP_JSON` / member map; 3 kun parallel.
3. Kunlik `--report-only` gap = 0 va `problems` bo'sh.
4. Keyin 5–6 sotuvchi. amoCRM obunasi pilot muvaffaqiyatli bo'lmaguncha bekor qilinmaydi.

## Backup va tiklash (Contabo, 2026-10-19 sozlandi va sinaldi)

- `/opt/twenty/backup.sh`, cron `30 2 * * *`: `pg_dump` + fayl hajmi, 14 kun saqlanadi,
  `/opt/twenty/backups/`.
- Tiklash sinovi: dump `restore_check` bazasiga tiklandi, `person` soni jonli bilan teng (5 = 5),
  so'ng vaqtinchalik baza o'chirildi.
- To'liq tiklash: `docker compose --env-file twenty-config stop server worker`, so'ng
  `pg_restore --clean -d default <dump>` va konteynerlarni ishga tushirish.

## amoCRM'ga qaytish

amoCRM hech qachon o'chirilmaydi va asosiy manba. Qaytish = `TWENTY_SYNC_ENABLED=0`, sotuvchilar
amoCRM'da ishlashda davom etadi. Twenty'da kiritilgan yangi ma'lumot amoCRM'ga avtomatik
qaytmaydi. Shuning uchun pilot davomida bitimlar amoCRM'da yuritiladi, Twenty esa ko'rish uchun.
