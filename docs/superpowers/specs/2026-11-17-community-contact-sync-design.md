# Community Contact Sync — dizayn

Sana: 2026-11-17 · Holat: owner tasdig'ini kutmoqda

## Maqsad va sabab

Owner Telegram papkasi "Tadbirkorlar" (folder id 13, ~29 superguruh: TEZ NATIJA 2–7,
3 kunlik intensiv kohortlari, soha guruhlari) a'zolarini qo'lda sinxron qilmoqda
(2026-11-17: TN7, 3K7, Toshkent 7 — CSV + Chrome import + local `bulk_add_contacts`).
Maqsad: shu ishni Oisha kunlik avtomatik bajarsin, har odam 6 tizimda bir xil bo'lsin.

## Maqsadlar

- Har a'zo uchun bitta kanonik yozuv (kalit: Telegram user id → telefon), kohort teglari.
- **Ikki tomonlama** sinxron (owner qarori): Google Contacts, AmoCRM, Airtable, Telegram
  contacts dagi tahrir qolganlarga tarqaladi.
- Ko'zgular (faqat yozish): Obsidian `60-Wiki`, GitHub second brain.
- Airtable: faqat to'lagan odamlar.
- Idempotent, dry-run, katta yozuvlarga owner tasdig'i, quiet hours, kunlik jadval.

## Non-goals

- Real-vaqt webhook sinxron (C variant rad etildi).
- Obsidian/GitHub dagi qo'lda tahrirni o'qish.
- A'zolarni guruhdan chiqarish/kontaktni o'chirish (o'chirish hech qachon avtomatik emas).

## Anti-goals (ishlasa ham muvaffaqiyatsizlik)

- Boshqa kohort suffiksli kontaktni qayta nomlash (masalan "TN4 Gr" → "TN7 Gr").
- Konfliktni jimgina hal qilish va ma'lumot yo'qotish.
- Lokal userbot ishga tushirish (`AuthKeyDuplicatedError`).
- Telegram FloodWait'ga urilib akkaunt cheklanishi.
- Uydirma qiymat yozish (AGENTS.md qoida 10): yo'q maydon bo'sh qoladi.

## Cheklovlar

- Telegram o'qish faqat Hetzner userbot (`app_ctx` Telethon klienti) orqali.
- Fayl ≤400 qator, funksiya ≤60 qator → paket.
- DB yozuvlari `database_pool.py` orqali.
- Quiet hours: `agent_policy.py` (23:00–07:00 Tashkent).
- Telegram a'zo telefonlari yashirin — telefon faqat intro postdan.
  Telefon bo'yicha `importContacts` asosan ishlamaydi; username bo'yicha qo'shish ishlaydi.
- O'zbekcha matn qoidasi (ikki tirnoq, `ʻ`/`ʼ`).

## Yondashuvlar

| | Tavsif | Trade-off |
|---|---|---|
| **A (tanlandi)** | Markaziy baza + har tizim uchun snapshot, maydon darajasida 3 tomonlama merge; konflikt → owner | To'liq ikki tomonlama, yo'qotish yo'q; kod va jadval ko'proq |
| B | Har maydonning bitta egasi | Sodda, konfliktsiz; lekin to'liq ikki tomonlama emas |
| C | Webhook real-vaqt | Tez; Telegram/Obsidian'da webhook yo'q, kunlik uchun ortiqcha |

Owner A ni tanladi (2026-11-17).

## Dizayn

### Paket `src/services/core/community_sync/`

| Modul | Vazifa |
|---|---|
| `models.py` | `Person` dataclass, `FIELDS` ro'yxati, naming (`display_name`, suffix, label) |
| `store.py` | Turso jadvallari: `community_people`, `community_memberships`, `community_snapshots`, `community_tg_queue`, `community_conflicts` |
| `collector.py` | Folder 13 dan guruhlar, a'zolar, intro postlar (Telethon, Hetzner) |
| `merge.py` | Sof funksiyalar: identity resolution + 3 tomonlama maydon merge |
| `adapters/google.py`, `adapters/amocrm.py`, `adapters/airtable.py`, `adapters/telegram.py` | `read_all()` / `apply(changes)` — ikki tomonlama |
| `adapters/vault.py`, `adapters/github.py` | Faqat `apply` (ko'zgu) |
| `runner.py` | Kunlik oqim, dry-run, approval, hisobot |
| `cohorts.py` | Guruh nomi → kohort kodi (`TN7`, `3K7`, `T7`, soha) jadvali |

`contact_intro_parser.py` kengaytiriladi (kirill alias, "Isim"/"Исм"), yangi parser yozilmaydi.
`gcontacts.py` ga `update_contact` + `add_to_group` qo'shiladi.

### Kanonik yozuv

Maydonlar: `tg_id`, `username`, `first_name`, `last_name`, `phone`, `company`, `activity`,
`region`, `cohorts[]`, `paid` (Airtable'dan), plus har tizim uchun tashqi id
(`google_resource`, `amo_contact_id`, `airtable_record_id`).

Identity: `tg_id` → normallashgan telefon (`998XXXXXXXXX`) → username. Mos kelmasa — yangi.
Ism bo'yicha avtomatik birlashtirish yo'q (noaniq juftlar owner hisobotiga).

### Naming

- Kontakt nomi: `"Ism Familya <suffix>"`, suffix birinchi (eng eski) kohortdan:
  `TN7 Gr` (TEZ NATIJA 7), `3K7 Gr` (3 kunlik intensiv 7).
- Google label: `TEZ NATIJA 7`, `3K7` va h.k. — har kohort uchun label qo'shiladi.
- Mavjud nomda boshqa `... Gr` suffiks bo'lsa — nom o'zgartirilmaydi, faqat label qo'shiladi.
- Soha guruhlari suffiks bermaydi, faqat teg/label.

### Ikki tomonlama merge (har maydon uchun)

```
base = snapshot[system][field]   # oxirgi sinxronda biz yozgan qiymat
cur  = system.read()[field]
changed = {s: cur_s for s if cur_s != base_s}
0 o'zgarish  -> hech narsa
1 tizim / bir xil qiymat -> kanonikka yoz, boshqalarga tarqat
turli qiymatlar -> community_conflicts ga, owner Telegram tugmasi bilan tanlaydi
```

Telegram collector (intro post) ham manba sifatida qatnashadi; bo'sh qiymat hech qachon
to'ldirilgan qiymatni o'chirmaydi. `cohorts` va `paid` — union/faqat egasi
(`paid` egasi Airtable, `cohorts` egasi collector).

### Telegram contacts drip

`community_tg_queue`: kunlik limit (default 120, sozlanadi), username bo'yicha qo'shish,
FloodWait → `wait_until` saqlanadi, keyingi kunga o'tadi. Telefon faqat username yo'q bo'lsa.

### Kunlik oqim (`runner.py`)

1. Quiet hours / `agent_policy` tekshiruvi.
2. Collect → identity → merge → reja (diff ro'yxati har tizim bo'yicha).
3. `dry_run=True` (default): faqat hisobot owner'ga.
4. Reja hajmi > `bulk_threshold` (default 20 yozuv/tizim) → owner tasdig'i (inline tugma).
   Kichik reja — avtomatik.
5. Apply → snapshot yangilanadi → hisobot + `job_traces`.

Konfiguratsiya env orqali (`COMMUNITY_SYNC_ENABLED`, `_DRY_RUN`, `_FOLDER_ID=13`,
`_TG_DAILY_LIMIT`, `_BULK_THRESHOLD`) — `getattr` himoyasi bilan, `settings.py` ga tegmasdan.

### Ko'zgular

- Obsidian: `60-Wiki/people/<Ism-Familya>.md` (frontmatter + kohortlar), vault yo'li
  `second_brain_sync.resolve_vault_path()`; vault topilmasa — skip, hisobotda.
- GitHub second brain: vault repo'ga commit (mavjud `second-brain-sync` oqimi), alohida qadam.

## Bosqichlar (PR)

1. **PR-1:** models, store, merge, cohorts, parser kengaytmasi, collector, Google + Telegram
   + AmoCRM adapterlari, runner, testlar. Scheduler ulanishi `boot.py` da — Coordinator fayli,
   shuning uchun alohida kichik o'zgarish sifatida AGENTS.md bilan kelishiladi.
2. **PR-2:** Airtable (to'laganlar), Obsidian, GitHub ko'zgulari.

## Quruvchiga qoldirilgan (mening qarorlarim)

- Jadval sxemasi tafsilotlari, adapter ichki API chaqiruvlari.
- Kohort jadvalidagi soha guruhlari kodlari — guruh nomlaridan avtomatik, noma'lumlari hisobotda.
- Default limitlar (120/kun, threshold 20) — owner o'zgartirishi mumkin.
- Test: barcha tashqi API mock; `SKIP_LIVE=1`.
