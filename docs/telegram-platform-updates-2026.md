# Telegram Platform Updates 2026 — Oisha-OS uchun eslatma

> Manba: [telegram.org/blog](https://telegram.org/blog) (2026). Bu hujjat Telegram'ning
> so'nggi platforma/Bot API yangiliklarini Oisha-OS kodbazasi holatiga bog'laydi — nima
> allaqachon bor, nima uzilish (gap), va nimani ko'rib chiqish kerak.
>
> Oxirgi yangilangan: 2026-07-20.

## TL;DR

Oisha-OS'ning Telegram AI qatlami (`src/services/core/telegram/telegram_ai_features.py`)
Telegram'ning **2026-yil 7-may "AI Bot Revolution"** e'loniga to'g'ridan-to'g'ri asoslangan:
guest AI mode, bot-to-bot chat, va streaming javoblar allaqachon `src/settings.py`da
bayroqlar bilan qo'llab-quvvatlanadi. Yangi (hali kodda yo'q) imkoniyatlar: **rich text
for bots**, **AI Guardians**, **ephemeral (private) bot replies**, va **Communities**.

## Xususiyatlar × kodbaza holati

| Telegram xususiyati | E'lon | Oisha-OS holati | Bog'liq joy |
|---|---|---|---|
| **Guest AI Bots** (botni a'zo bo'lmagan chatda `@username` bilan chaqirish) | 7-May-2026 | ✅ Bor | `TELEGRAM_AI_GUEST_MODE_ENABLED` (`src/settings.py:54`) |
| **Bot-to-Bot chats** (bot boshqa botga javob beradi) | 7-May-2026 | ✅ Bor | `TELEGRAM_BOT_TO_BOT_ENABLED` (`src/settings.py:56`) |
| **Streaming javoblar** (matn generatsiya bo'lishi bilan oqim) | 7-May-2026 | ✅ Bor | `TELEGRAM_AI_STREAMING_ENABLED` (`src/settings.py:55`), `src/services/core/telegram/streaming.py` |
| **Bots Managed by Bots** (botni bot boshqaradi) | 31-Mar-2026 | ⚙️ Bayroq bor, default off | `TELEGRAM_MANAGED_BOTS_ENABLED` (`src/settings.py:57`) |
| **Rich Text for Bots** (jadval, heading, media carousel, 32K belgigacha) | 11-Iyun-2026 | ❌ Gap | admin/guest bot javoblari |
| **AI Guardians for Groups** (AI moderator, join-request skrining) | 11-Iyun-2026 | ❌ Gap (bizda custom `src/services/core/agent_policy.py` bor) | guruh moderatsiyasi |
| **Ephemeral / private bot replies** (faqat bitta userga ko'rinadigan javob) | 14-Iyul-2026 | ❌ Gap | Hisobchi/xatolik/menyu javoblari |
| **Communities** (guruh+kanallarni birlashtirish) | 14-Iyul-2026 | ❌ Gap | lead scraping struktura |

## Guest AI Bots — muhim maxfiylik chegarasi

Guest mode'da bot **faqat o'zi teg qilingan xabar va unga bergan javoblarni** ko'radi.
Bot chatdagi boshqa a'zolarni yoki boshqa xabarlarni ko'ra olmaydi. Bu bizning
`auto_reply_gate` / `WHITELIST_IDS` modelimiz bilan mos — guest mode kengaytirilsa,
kontekst cheklovini hisobga olish kerak (bot to'liq tarixni ko'rmaydi).

## Ko'rib chiqish arzigulik ish elementlari

1. **Rich Text for Bots** (11-Iyun) — admin/guest bot javoblarini boyroq formatga o'tkazish
   imkoni (jadvallar, heading, collapsible). Bot API rich-text formatlash hujjatiga qarang.
   Foydali joylar: ERP/CRM dashboard javoblari, enterprise reporter, kunlik hisobotlar.
2. **Ephemeral (private) replies** (14-Iyul) — Hisobchi tasdiqlari, xatolik/menyu javoblari
   guruh tarixini to'ldirmasligi uchun private ko'rinishda yuborilishi mumkin. Bu MCP
   approval kartalari va `/kirim`/`/chiqim` javoblarida shovqinni kamaytiradi.
3. **AI Guardians** (11-Iyun) — native join-request skrining bizning manual guruh
   boshqaruvini qisman avtomatlashtirishi mumkin; `src/services/core/agent_policy.py`
   guardrails bilan qanday birga ishlashini baholash kerak.
4. **Ephemeral messages ≠ o'chib ketuvchi user xabarlari** — bu bot-generated private
   javoblar. Shuning uchun lead/finance scraping'ga (message history yo'qolishi) **ta'sir
   qilmaydi** — dastlabki xavotir tasdiqlanmadi.

## Manbalar

- [AI Bot Revolution — 11 New Features (7-May-2026)](https://telegram.org/blog/ai-bot-revolution-11-new-features)
- [Smartwatch Apps, Rich Text for Bots, AI Guardians (11-Iyun-2026)](https://telegram.org/blog/watch-apps-and-more)
- [Communities, Editor, Invisible Messages (14-Iyul-2026)](https://telegram.org/blog/communities-editor-invisible-messages)
- [AI Editor, Mighty Polls, Bots Managed by Bots (31-Mar-2026)](https://telegram.org/blog/ai-editor-mighty-polls-and-more)
- [Telegram Bot API](https://core.telegram.org/bots/api)
