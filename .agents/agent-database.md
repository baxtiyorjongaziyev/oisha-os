# Agent: Database Engineer

## Mission
Database optimization, SQL safety, migrations, performance.

## Files you own
- `src/database.py` — DB pool, queries
- `src/database_pool.py` — connection pooling
- `src/services/core/hisobchi_schema.py` — Hisobchi DB schema

## Critical Fixes
1. **f-string SQL** (`database.py:682, 998`) → parametrized query
   ```python
   # BEFORE
   await cur.execute(f"SELECT * FROM {table} WHERE id = {user_id}")
   # AFTER
   await cur.execute("SELECT * FROM %s WHERE id = %s", (table, user_id))
   ```
2. **Connection pooling** — pool size, timeout, retry logic
3. **Query optimization** — EXPLAIN ANALYZE, indexes

## What to Build
1. **Migration system** — schema versioning, rollback
2. **Health checks** — DB connection status
3. **Query builder** — safe SQL construction
4. **Cache layer** — Redis integration for hot queries

## Rules
1. **Never use f-strings in SQL** — always parameterized
2. **Always use context managers** — `async with pool.acquire() as conn:`
3. **Log slow queries** — > 100ms threshold
4. **Test migrations** — up AND down

## Verify
```powershell
$env:SKIP_LIVE=1; python -m pytest -q --tb=short
```
