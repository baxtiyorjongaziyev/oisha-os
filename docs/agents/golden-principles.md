# Golden Principles

Mexanik, tekshirsa bo'ladigan qoidalar. Agent har ishda ularga amal qiladi; Ralph janitor loop
(`scripts/ralph/PLAN.janitor.md`) ularning buzilishini muntazam qidiradi va tuzatadi.

Qoida qo'shish tartibi: agent bir xil xatoni **2 marta** qilsa → shu yerga qoida yoziladi.
Qoida muhim bo'lsa → hook yoki test bilan majburlanadi (so'z — iltimos, hook — kafolat).

## Tekshiruv

1. "Tayyor" degan qarorni model emas, `pytest` + `bandit` qiladi. Yashil bo'lmasa — commit yo'q.
2. Testni o'tkazish uchun testni o'chirish, `skip` qilish yoki assertni kuchsizlantirish taqiqlanadi.
3. Har bug fix → avval uni qaytaradigan (failing) test, keyin fix.

## Kod

4. Umumiy helper bor bo'lsa — qayta yozilmaydi. Avval `src/services/utils/` va `tool_registry` qidiriladi.
5. Tashqi ma'lumot (AmoCRM, Meta, Telegram, Airtable) chegarada validatsiya qilinadi
   (Pydantic / typed model). Taxminiy `dict["key"]` bilan ichkariga kirilmaydi.
6. Yangi agent `tool_registry.ToolResult` qaytaradi; LLM chaqiruvlari `free_ai_router` orqali.
7. DB yozuvlari faqat `database_pool.py` orqali.
8. Fayl ≤ 400 qator, funksiya ≤ 60 qator (`code-standards.md`).
9. Zerikarli (boring) texnologiya afzal: yangi kutubxona qo'shishdan oldin mavjudi tekshiriladi.

## Xavfsizlik

10. Lokal userbot / Telethon sessiya ochilmaydi (Oracle egasi).
11. Quiet-hours (23:00–07:00 Toshkent) va approval gate'lar chetlab o'tilmaydi.
12. Sirlar kodga, logga, handoff'ga, commitga yozilmaydi.

## Bilim

13. Bilim chatda emas, repoda: qaror → `docs/`, holat → `docs/agents/state-and-history.md`,
    ish tarixi → `docs/agents/handoff-log.md`.
14. `AGENTS.md` va `CLAUDE.md` — xarita. Tafsilot `docs/` ga, xaritada faqat havola.
15. Root papkaga yangi `.md` hisobot qo'yilmaydi → `docs/` yoki `docs/archive/`.
