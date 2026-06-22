# Agent: Security & Testing

## Mission
Test coverage, security issues, exception handling, va kod sifatini yaxshilash.

## Files you own
- `tests/` — barcha test fayllari
- Pytest config, conftest

## Critical Fixes
1. **`except Exception: pass`** (20+ joy) → `logger.exception(...)` yoki hech bo'lmaganda `logger.warning(...)`
   ```python
   # BEFORE
   except Exception:
       pass
   # AFTER  
   except Exception:
       logger.exception("Failed to X: %s", context_var)
   ```
2. **f-string SQL** (`database.py:682, 998`) → parametrized query
   ```python
   # BEFORE
   await cur.execute(f"SELECT * FROM {table} WHERE id = {user_id}")
   # AFTER
   await cur.execute("SELECT * FROM %s WHERE id = %s", (table, user_id))
   ```

## Tests
1. **Hisobchi tests** — `tests/test_hisobchi*.py` yoz
2. **Security tests** — `test_api_server_security.py` ni boyit
3. **Edge cases** — empty DB, bad input, timeout, concurrent access

## Do NOT touch
- `src/agents/` — domain logic
- `src/services/core/hisobchi_*` — Hisobchi agenti uchun
- `src/services/debug/` — external debug tools

## Bandit Rules
- High issues: 0 (current: 1 — `os_driver.py:149` subprocess shell=True, may convert)
- Low issues: 114 (fix only relevant ones, ignore noise)
- After each batch: `bandit -r src/ -ll -x src/services/debug/`

## Verify
```powershell
$env:SKIP_LIVE=1; python -m pytest -q --tb=short
bandit -r src/ -ll -x src/services/debug/
```
