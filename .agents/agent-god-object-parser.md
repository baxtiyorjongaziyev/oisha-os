# Agent: God Object Parser

## Mission
main.py (2723 lines) ni bosqichma-bosqich parchala. Goal: main.py ~500 lines.

## Do not touch
- `src/agents/`, `src/services/debug/`, `src/legacy/`
- settings.py, context.py, boot.py (Coordinator ga tegishli)
- Testlar (Security ga tegishli)

## Phase 1 — Handlers (`src/handlers/`)
main.py dagi event handler larni alohida fayllarga chiqar:
- `handle_new_message` → `handlers/messages.py`
- `/start`, `/help` etc → `handlers/commands.py` (self_command_handler bilan birlashtir)
- Callback handlerlar → `handlers/callbacks.py`
- Payment handlerlar → `handlers/payments.py`

Har bir handler fayli:
```python
from src.context import app_ctx

async def handle_xxx(event):
    ...
```

## Phase 2 — Commands (`src/commands/`)
`self_command_handler` ni (1000+ lines) parchalash:
- `commands/registry.py` — command → handler mapping
- `commands/admin.py` — admin buyruqlari
- `commands/user.py` — user buyruqlari
- `commands/lead.py` — lead related
- `commands/tools.py` — utility buyruqlar

## Phase 3 — Schedulers (`src/schedulers/`)
Background loop lar va cron job larni chiqarish:
- `schedulers/daily_reports.py`
- `schedulers/night_shift.py`
- `schedulers/evolution.py`

## Rules
1. **Import `app_ctx` from `src.context`, never `import src.main as m`**
2. **Har bir o'zgarishdan keyin test ishlat**: `python -m pytest -q --tb=short`
3. **Bir vaqtda faqat bitta fayl ustida ishla**
4. **main.py dan hech narsa o'chirma — copy/paste qil, keyin o'chir**
5. **Circular import bo'lsa, lazy import ishlat (`from xxx import yyy` funksiya ichida)**

## Verify
```powershell
$env:SKIP_LIVE=1; python -m pytest -q --tb=short
```
