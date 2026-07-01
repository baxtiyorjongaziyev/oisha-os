# Agent: Hisobchi AI Engineer

## Mission
Hisobchi AI tizimini to'liq ishlaydigan holatga keltirish.

## Files you own
- `src/services/core/hisobchi_engine.py`
- `src/services/core/hisobchi_handlers.py`
- `src/services/core/hisobchi_schema.py`
- `src/services/core/hisobchi_card_parser.py`

## Dependencies
- `src/settings.py`: `HISOBCHI_FINANCE_GROUP_ID`, `HISOBCHI_PNL_TOPIC_ID`, etc (already set)
- `boot.py`: `init_hisobchi_tables()` chaqirilishi kerak (Coordinator ga tegishli)
- `main.py`: `_hisobchi_engine` global (Parser ga tegishli)

## Current Problems
1. `init_hisobchi_tables()` hech qayerda chaqirilmaydi → DB table lar yaratilmaydi
2. Hisobchi event handler lari ro'yxatdan o'tmagan
3. `_hisobchi_engine` global variable hali yo'q

## What to do
1. `hisobchi_engine.py` ni tekshir — `_hisobchi_engine` global ga muhtojmi?
2. `hisobchi_handlers.py` — 3 handler (card_bot, finance_reply, voice) ni standalone async function lar qilib yoz
3. `hisobchi_card_parser.py` — card parsing logikasini toza qilib qayta yoz
4. Agar hisobchi test bo'lsa, yoz yoki tuzat

## Do NOT touch
- `boot.py`, `main.py`, `settings.py`, `context.py` — ularni faqat o'zgartirish kerakligini AGENTS.md ga yoz, Coordinator hal qiladi
- `src/agents/` — boshqa agentlar

## Verify
```powershell
$env:SKIP_LIVE=1; python -m pytest -q --tb=short
```
