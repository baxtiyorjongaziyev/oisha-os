# Agent: Global → Context Migration

## Mission
main.py va boshqa fayllardagi global variable larni `ApplicationContext` ga ko'chirish.

## Context Pattern
```python
# src/context.py — allaqachon mavjud
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class ApplicationContext:
    db_pool: Optional[object] = None
    bot_client: Optional[object] = None
    # ... yana field lar

app_ctx = ApplicationContext()  # singleton
```

Ishlatish:
```python
from src.context import app_ctx
app_ctx.db_pool = pool  # set
db = app_ctx.db_pool       # get
```

## Migration Steps
1. `main.py` dan barcha global larni top:
   ```powershell
   rg "^\w+\s*=\s*(None|[]|{})$" src/main.py
   ```
2. Har bir globalni `context.py` ga field sifatida qo'sh
3. main.py da `import src.main as m` → `from src.context import app_ctx` ga almashtir
4. `m.some_global` → `app_ctx.some_global`

## Priority
1. `_hisobchi_engine` — Hisobchi AI uchun critical
2. `_db_pool`, `_bot` — core components
3. `_checkpoint_timers`, `_active_sessions` — stateful
4. Qolganlari — low priority, batch

## Rules
1. **Bir vaqtda faqat bitta global ni migratsiya qil**
2. **Har bir o'zgarishdan keyin test ishlat**
3. **Agar `app_ctx` hali mavjud bo'lmasa, `setattr` / `getattr` bilan safe access**
4. **Circular import bo'lsa, `from src.context import app_ctx` ni funksiya ichiga yoz**

## Verify
```powershell
$env:SKIP_LIVE=1; python -m pytest -q --tb=short
```
