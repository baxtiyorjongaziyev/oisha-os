# Telegram widgetlar (Bot API 10.4) — Oisha, Mr.Jon, Amina uchun reja

Sana: 2026-11-12 · Holat: reja (kod yozilmagan)

## 0. Nima isbotlangan

Raw HTTP prototipi (`@jonairobot`, owner shaxsiy chati) bilan jonli sinovdan oʻtdi:

| Metod | Natija |
|---|---|
| `sendWidget` | OK, Telegramʼda toʻgʻri koʻrindi |
| `editMessageWidgetData` | OK |
| `widget_query` → `answerWidgetQuery` | OK, widget ichida javob chiqdi |
| `sendSharedWidget` / `editSharedWidgetData` | sinalmagan |

aiogram 3.31.0 (eng soʻnggi) va python-telegram-bot 22.8 widget metodlarini bilmaydi → oʻz HTTP klientimiz kerak.

## 1. Cheklovlar (dizaynni belgilaydi)

- **Faqat shaxsiy chat (production).** Guruh, forward, inline — faqat test serverda. Demak guruhga ketadigan hamma narsa (kirim tabriklari, jamoa ritmi, attendance) hozircha matn boʻlib qoladi.
- **HTML ≤ 32 KB, zlib bilan siqilgandan keyin ≤ 4 KB.** Tashqi font/kutubxona yoʻq; bitta kichik CSS, inline SVG.
- **Holat ≤ 1024 bayt** (`chat_data`, `public_data`). Katta maʼlumot widget ichida saqlanmaydi — `TelegramWidget.request()` (1–64 bayt) orqali soʻraladi, javob ≤ 1024 bayt.
- **Har bir soʻrovga 15 soniyada javob.** Uzoq ish (CRM, AI) → darhol "qabul qilindi" javobi, natija `editMessageWidgetData` bilan.
- **Tahrir rate-limit:** xabar yuborish limitiga kiradi; shared widget sekundiga 1 tahrir.
- `copyMessage` widgetni nusxalamaydi.

## 2. Umumiy poydevor (Faza 0)

1. **`src/services/telegram/widget_client.py`** — prototipdan koʻchiriladi (async `httpx`), `ToolResult` qaytaradi, tokenni logga chiqarmaydi.
2. **`src/services/telegram/widget_templates/`** — Jon Branding dizayn tizimi:
   - `base.css` (≤ 1.5 KB): ranglar, tipografiya, karta, jadval, tugma, light/dark (`prefers-color-scheme`).
   - Komponentlar: `kpi_row`, `card_list`, `table`, `progress`, `approve_bar`, `sparkline` (inline SVG).
   - Render funksiyasi + oʻlcham tekshiruvi (32 KB / 4 KB). Limitdan oshsa → avtomatik matn fallback.
3. **Update qabul qilish:** aiogram pollerining `allowed_updates` roʻyxatiga `widget_query`, `shared_widget_query` qoʻshiladi; aiogram ularni tanimagani uchun raw update middleware (`Update.model_extra`) orqali ushlanadi → `widget_router`.
4. **`widget_router`** — `data` formati `<modul>:<amal>:<id>` (≤ 64 bayt), whitelist (`OWNER_ID`, `WHITELIST_IDS`), quiet-hours va `agent_policy` tekshiruvi, 15 s ichida javob.
5. **Feature flag:** `WIDGETS_ENABLED`, modul boʻyicha `WIDGETS_MODULES=reports,approvals,...`. Har widget xatosida matn fallback.
6. **Testlar:** mock transport (prototipdagi kabi), shablon oʻlcham testlari, router testlari. `SKIP_LIVE=1` bilan oʻtadi.

> `settings.py`, `boot.py` — koordinator fayllari; oʻzgartirishdan oldin `AGENTS.md` Locks boʻlimi.

## 3. Oisha (`@jonairobot`, Python core)

Owner/whitelist shaxsiy chatiga ketadigan narsalar widgetga oʻtadi.

### Faza 1 — faqat oʻqiladigan hisobotlar (xavfsiz boshlanish)

| Hozir | Widget | Manba |
|---|---|---|
| Kunlik reja / audit hisobot | KPI qatori + vazifalar roʻyxati, "Batafsil" tugmasi | `enterprise_reporter.py`, `daily_analytics_reporter.py` |
| Dashboard buyrugʻi | Savdo voronkasi, bugungi lidlar, sparkline | `commands/dashboard.py`, `crm_dashboard` |
| Frog vazifalar | Progress bar + vazifalar kartasi | `frog_scheduler.py` |
| Leadgen / Meta holati | Status kartalari (yashil/sariq/qizil) | `leadgen_status_reporter.py`, `meta_health_scheduler.py` |
| Instagram haftalik | KPI + top postlar | `instagram_weekly_reporter.py` |
| Hisobchi boʻshliqlari | Jadval, summa formati | `hisobchi_gap_reporter.py` |
| Qoʻngʻiroq tahlili | Ball + asosiy xatolar | `call_analysis_scheduler.py` |

### Faza 2 — interaktiv (tasdiqlash va harakatlar)

| Oqim | Widget | Xavfsizlik |
|---|---|---|
| Shadow auto-reply qoralamalari | Matn + "Yubor / Tahrirla / Rad et" | `auto_reply_gate` oʻzgarmaydi, faqat UI |
| Telegram-MCP mutatsiya tasdigʻi | Amal tafsiloti + "Tasdiqla / Rad et" | owner-only, mavjud gateway orqali |
| CRM lid kartasi | Lid maʼlumoti + "Bosqichni oʻzgartir / Vazifa qoʻsh" | `agent_policy` approval gate |
| Toʻlovlar / kirim tasdigʻi (shaxsiy) | Summa, mijoz, "Tasdiqla" | quiet-hours |
| Uchrashuv | Vaqt tanlash slotlari | `calendar` |

Har harakat: widget → `request("crm:stage:123")` → router → mavjud handler → `answerWidgetQuery("ok")` → `editMessageWidgetData` bilan yangi holat.

### Faza 4 — shared widgetlar (jonli dashboard)

Bitta "Oisha Command Center" shared widget: `editSharedWidgetData` har 60 s (`cache_time`) yangilanadi; owner uni istalgan chatga qayta yuboradi (`sendSharedWidget`).

## 4. Mr.Jon (`@jon_clawbot`, OpenClaw runtime)

Python core emas — OpenClaw workspace (`deploy/openclaw/workspace`). Shuning uchun:

1. OpenClaw uchun **`send_widget` skill/tool** (`deploy/openclaw/workspace/skills/`) — bir xil HTTP chaqiruv, bir xil shablonlar (shablonlar JSON/HTML sifatida eksport qilinadi, ikkala runtime ishlatadi).
2. Nomzod oqimlar (Mr.Jon — asoschining raqamli egizagi):
   - Agentlik keyslari / portfolio kartalari.
   - Xizmatlar va narx kalkulyatori (widget ichida hisob, `request` bilan soʻrov yuborish).
   - Uchrashuvga yozilish slotlari.
   - Brief yigʻish formasi (qadam-baqadam, holat `chat_data` da).
3. Mijoz bilan muloqot boʻlgani uchun: matn fallback majburiy, widgetlar faqat mijoz botga oʻzi yozgan shaxsiy chatda.

## 5. Amina

Maʼlum: alohida username'li bot, **Hermes** runtime'ida, **Telegram guruhlarida** jamoa aʼzolari bilan ishlaydi. Repoda Amina kodi/konfiguratsiyasi topilmadi; hozir nima yuborishi nomaʼlum.

**Asosiy toʻsiq:** guruhlarda widgetlar productionda ishlamaydi (faqat test server). Shuning uchun Aminaʼning guruh xabarlari hozircha widgetga oʻtkazib boʻlmaydi.

Hozir mumkin boʻlgan yoʻl — **guruhdan shaxsiy chatga koʻprik**:
1. Guruhda qisqa matn + tugma (deep link `t.me/<amina_bot>?start=<payload>`).
2. Jamoa aʼzosi Amina bilan shaxsiy chatga oʻtadi → u yerda widget (shaxsiy vazifalar, hisobot formasi, checklist, soʻrovnoma).
3. Natija guruhga qisqa matn sifatida qaytadi.

Nomzod oqimlar (Amina vazifalari aniqlangach tasdiqlanadi): shaxsiy vazifalar roʻyxati, kunlik hisobot/check-in formasi, soʻrovnoma, shaxsiy KPI kartasi.

Qoʻshimcha: guruhdagi tugma bosilishiga faqat bosgan odamga koʻrinadigan **ephemeral javob** (Bot API 10.4) — widget emas, lekin guruhda shaxsiy maʼlumot koʻrsatishning hozirgi yoʻli.

**Kerak:** Amina Hermes konfiguratsiyasi qayerda (server yoʻli yoki repo), qaysi guruhlarda ishlaydi, qanday xabar/buyruqlari bor. Shundan keyin oqimlar roʻyxati yakunlanadi. Guruh widgetlari productionda yoqilganda — asosiy faza.

## 6. Bosqichlar va tartib

| Faza | Ish | Tayyorlik mezoni |
|---|---|---|
| 0 | Poydevor: klient, shablonlar, router, flag, testlar | testlar yashil, bandit toza, owner chatga demo widget |
| 1 | Oisha hisobotlari (oʻqish) | 3 ta hisobot widgetda, fallback ishlaydi |
| 2 | Oisha tasdiqlash oqimlari | shadow qoralama widget orqali tasdiqlanadi |
| 3 | Mr.Jon skill + 2 oqim | `@jon_clawbot` widget yuboradi va soʻrovga javob beradi |
| 4 | Shared Command Center | jonli yangilanish, rate-limit ichida |
| 5 | Amina | maʼlumot kelgach |
| — | Guruh widgetlari | Telegram productionda yoqqanda |

## 7. Xavflar va ochiq savollar

- **Token:** `@jonairobot` tokeni chatda ochiq koʻrindi → BotFather `/revoke`, Contaboʼdagi `.env` yangilansin.
- **164 update:** jonli sinovda navbatdan olindi, `pending_updates_backup.json` da saqlangan; ular qayta ishlanishi kerakmi — hal qilish kerak. Navbat 164 da turgani poller bu token bilan ishlamayotganini koʻrsatadi — Contabo `oisha.service` tekshirilsin.
- aiogram widget qoʻllab-quvvatlashni qoʻshsa — oʻz klientimizdan unga oʻtish.
- 4 KB siqilgan HTML chegarasi murakkab dizaynni cheklaydi — shablonlar minimal boʻlishi shart.
