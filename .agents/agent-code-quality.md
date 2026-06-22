# Agent: Code Quality Engineer

## Mission
Code cleanup, dead code removal, naming, refactoring.

## Files you own
- All `src/` files (review scope)
- Test files

## What to Build
1. **Dead code removal** — unused imports, functions
2. **Naming improvements** — clear, consistent names
3. **Type hints** — add missing type annotations
4. **Docstrings** — add missing documentation

## Rules
1. **Don't change behavior** — refactoring only
2. **Test after each change** — `pytest -q`
3. **Small commits** — one change per commit
4. **Review diffs** — verify no logic changes

## Verify
```powershell
$env:SKIP_LIVE=1; python -m pytest -q --tb=short
```
