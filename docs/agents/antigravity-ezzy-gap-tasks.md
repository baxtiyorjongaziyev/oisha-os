# Antigravity uchun topshiriq: Ezzy gap-tahlil — qolgan ishlar

> Muallif: Claude Code (2026-10-07). Bog'liq PR: #822 (`claude/ezzy-welcome-page-65zx2k`).
> Ishni boshlashdan oldin: `AGENTS.md`, `CLAUDE.md`, `docs/agents/code-standards.md` ni o'qing.

## Kontekst
Ezzy (app.ezzy.uz — AI'li Cloud PBX) bilan solishtirib, Oisha-OS'dagi bo'shliqlar topildi.

**Allaqachon bor (qayta qurmang):**
| Funksiya | Qayerda |
|---|---|
| Qo'ng'iroq transkripsiyasi + AI baho, webhook'da darhol | `src/services/call_analytics/` (`runner.py`, `scorer.py`), `AMOCRM_CALL_ANALYSIS_ON_WEBHOOK` |
| Tahlildan keyin Telegram xabar | `call_analytics/crm_tasks.py::_notify_telegram_call_analysis` |
| Javobsiz qo'ng'iroq → alert + vazifa | `call_analytics/missed_call_responder.py` (PR #822) |
| Sayt callback vidjeti + UTM | `src/static/callback-widget.js`, `src/api/routes/callback_widget.py`, `src/services/core/leads/callback_request.py` (PR #822) |
| Statik call tracking | `src/services/core/leads/call_tracking.py` (PR #822) |
| Javobsiz/javobli qo'ng'iroq hajmi | `src/services/core/call_events.py` |
| Moliya bo'yicha oddiy tilda savol | `src/services/core/hisobchi_mcp.py` |

**PR #822 ga bog'liqlik:** quyidagi ishlar #822 dagi `missed_call_responder.flatten_note` va webhook o'zgarishlariga tayanadi.
#822 `main` ga merge bo'lmaguncha, branch'ni `claude/ezzy-welcome-page-65zx2k` dan oching.

---

## Vazifa A — Kiruvchi qo'ng'iroqda mijoz kartasi (screen-pop) — USTUVOR

**Maqsad:** mijoz qo'ng'iroq qilganda (gaplashishdan OLDIN) menejerga Telegram'da qisqa karta:
```
📞 Kiruvchi: +998 90 123 45 67
👤 Ali Valiyev — "Logo + brandbook" (lid #12345, etap: Kvalifikatsiya)
💰 Byudjet: 15 mln · Mas'ul: Dilshod
🕘 Oxirgi aloqa: 3 kun oldin — "taklif yuborildi, javob kutilmoqda"
🎯 Manba: instagram (call tracking bo'lsa)
🔗 AmoCRM havolasi
```
Raqam AmoCRM'da topilmasa: "🆕 Yangi raqam — CRM'da yo'q" + 1 bosishda lid ochish taklifi (avtomatik ochmang).

**Asosiy savol — qo'ng'iroq BOSHLANISHI hodisasini qayerdan olamiz (avval aniqlang, kod yozishdan oldin):**
1. Moizvonki webhook'lari (`call.start` / kiruvchi qo'ng'iroq hodisasi) — Moizvonki API hujjatini tekshiring.
   Repo'da `MOIZVONKI_EMAIL/PASSWORD/API_KEY/DOMAIN` sozlamalari bor (`src/settings.py`).
2. AmoCRM `notes[add]` call note qo'ng'iroq TUGAGANDAN keyin keladi — screen-pop uchun kech, ishlatmang.
Agar Moizvonki boshlanish hodisasini bermasa — to'xtang va Owner'ga yozing, taxmin bilan qurmang.

**Talablar:**
- Yangi modul: `src/services/call_analytics/incoming_call_card.py` (≤400 qator, funksiya ≤60 qator).
- Webhook endpoint: `src/api/routes/` ichida, imzo/secret bilan himoyalangan (Moizvonki qanday imzolasa).
  Ochiq endpoint bo'lsa `src/api/security.py::_PUBLIC_PATHS` ga qo'shing va himoyasini route ichida qiling.
- Mijoz ma'lumoti: avval `src/services/customer_360/` (collector — telefon bo'yicha profil yig'adi) ni o'rganing va qayta ishlating;
  yetmasa `AmoCRMSync.find_active_lead_by_phone` va lid/contact o'qish metodlari.
- Karta mas'ul menejerga (AmoCRM responsible → Telegram ID mapping bor-yo'qligini tekshiring), yo'q bo'lsa sotuv guruhiga
  (`leadgen_watchdog.send_admin_alert` namunasi).
- Flag: `INCOMING_CALL_CARD_ENABLED` (default o'chiq), `os.getenv` orqali — `settings.py` coordinator'niki, tegmang.
- Dedup: bitta qo'ng'iroq uchun bitta karta. Quiet hours (`time_utils.is_quiet_hours`) — karta yuborilmaydi.
- Telefon raqami HTML-escape qilinsin. Sirlar log'ga yozilmasin.
- 2 soniyadan oshmasin: AmoCRM so'rovi sekin bo'lsa, avval qisqa karta, keyin tahrirlab to'ldiring.

**Testlar:** `tests/test_incoming_call_card.py` — topilgan lid, yangi raqam, dedup, quiet hours, flag o'chiq,
AmoCRM xatosi (yiqilmasin), webhook imzosi noto'g'ri → 401/403.

---

## Vazifa B — CRM va qo'ng'iroqlar bo'yicha oddiy tilda savol (Telegram)

**Maqsad:** Owner Telegram'da yozadi → Oisha javob beradi:
- "Bu hafta nechta javobsiz qo'ng'iroq bo'ldi, kim ko'p o'tkazib yubordi?"
- "Instagram'dan bu oy nechta lid keldi?"
- "Dilshodning o'rtacha qo'ng'iroq bahosi qancha?"

**Yondashuv (xavfsiz):** erkin SQL generatsiya QILMANG. Oldindan belgilangan, faqat o'qiydigan
"tool"lar to'plami + LLM ulardan birini tanlab parametr beradi (function calling):
- `missed_calls(period, manager?)` ← `call_events`
- `call_quality(period, manager?)` ← `call_analyses`
- `leads_by_source(period, source?)` ← AmoCRM / lid izohlaridagi "Manba:" qatori
- `pipeline_summary(stage?)` ← AmoCRM

**Talablar:**
- Namuna: `src/services/core/hisobchi_mcp.py` (moliya uchun xuddi shu g'oya).
- LLM chaqiruvlari faqat `src/services/utils/free_ai_router.py` orqali.
- Faqat `OWNER_ID` / `WHITELIST_IDS` uchun. Faqat o'qish — hech qanday yozish/o'zgartirish yo'q.
- DB faqat `database_pool.py` orqali.
- Javobda raqam bilan birga manba ko'rsatilsin ("call_events, 1–7 okt"). Ma'lumot yo'q bo'lsa — "ma'lumot yo'q" deb ayting, to'qimang.
- Flag: `CRM_QA_ENABLED` (default o'chiq).

**Testlar:** `tests/test_crm_qa.py` — har bir tool, ruxsatsiz foydalanuvchi rad etiladi, LLM noma'lum tool qaytarsa xavfsiz javob.

---

## Qilinmaydi (bu topshiriqdan tashqari)
- Kiruvchi qo'ng'iroqqa AI ovozli javob — telefoniya provayderi integratsiyasi kerak, alohida qaror.
- Navbat / qo'ng'iroqni o'tkazish — Moizvonki sozlamalarida qilinadi, kod emas.
- `settings.py`, `context.py`, `boot.py` — coordinator fayllari, tegmang.

## Har PR dan oldin (AGENTS.md)
```bash
SKIP_LIVE=1 python -m pytest -q --tb=short
bandit -r src/ -ll
```
- `AGENTS.md` → `## Locks` ga qulf yozing, tugagach o'chiring.
- `docs/agents/handoff-log.md` OXIRIGA yozing: sana/agent, ish, fayllar, tekshiruv dalili, qolgan ish.
- Branch: `feat/<desc>`, commit: `feat(scope): ...`. PR draft bo'lib ochilsin.
